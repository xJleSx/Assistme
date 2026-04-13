import logging
import re
from sqlalchemy import text
from schemas.query_schema import StructuredQuery

logger = logging.getLogger(__name__)

SUPPORTED_NUMERIC_KEYS = {
    'battery_capacity', 'display_size', 'refresh_rate', 'ram', 'storage',
    'camera_mp', 'selfie_camera_mp', 'charging_watts', 'weight'
}

def build_product_query(session, structured_query: StructuredQuery):
    base_sql = "SELECT DISTINCT p.id FROM products p "
    joins = []
    where_clauses = []
    params = {}
    
    # Category
    if structured_query.category:
        joins.append("JOIN categories c ON p.category_id = c.id")
        where_clauses.append("c.slug = :category")
        params["category"] = structured_query.category.strip().lower()
    
    # Brands
    if structured_query.brands:
        joins.append("JOIN brands b ON p.brand_id = b.id")
        brand_conditions = []
        for i, brand in enumerate(structured_query.brands):
            param_name = f"brand_{i}"
            brand_conditions.append(f"b.name ILIKE :{param_name}")
            params[param_name] = f"%{brand}%"
        where_clauses.append(f"({' OR '.join(brand_conditions)})")
    
    # Models (explicit model names)
    if structured_query.models:
        model_conditions = []
        for i, model in enumerate(structured_query.models):
            param_name = f"model_{i}"
            model_conditions.append(f"p.name ILIKE :{param_name}")
            params[param_name] = f"%{model}%"
        where_clauses.append(f"({' OR '.join(model_conditions)})")
    
    # Budget
    if structured_query.budget is not None:
        where_clauses.append("p.price <= :budget")
        params["budget"] = structured_query.budget
    
    # Numeric filters (используем product_features вместо product_numeric_specs)
    feature_joins = 0
    for feature_key, condition in structured_query.filters.items():
        if feature_key not in SUPPORTED_NUMERIC_KEYS:
            logger.warning(f"Unsupported feature key '{feature_key}' – skipping")
            continue
        
        feature_joins += 1
        alias = f"f{feature_joins}"
        # Теперь джойнимся к product_features
        joins.append(f"LEFT JOIN product_features {alias} ON p.id = {alias}.product_id AND {alias}.feature_key = :key_{alias}")
        where_clauses.append(f"{alias}.feature_key = :key_{alias} AND {alias}.feature_value_numeric IS NOT NULL")
        params[f"key_{alias}"] = feature_key
        
        op, val = _parse_condition(condition)
        if op and val is not None:
            where_clauses.append(f"{alias}.feature_value_numeric {op} :val_{alias}")
            params[f"val_{alias}"] = val
        else:
            logger.warning(f"Failed to parse condition '{condition}' for feature '{feature_key}'")
    
    if not joins:
        sql = base_sql
    else:
        sql = base_sql + " " + " ".join(joins)
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
    
    logger.debug(f"Executing SQL: {sql} with params: {params}")
    try:
        result = session.execute(text(sql), params).fetchall()
        return [row[0] for row in result]
    except Exception as e:
        logger.error(f"SQL execution error: {e}")
        return []

def _parse_condition(condition: str):
    condition = condition.strip()
    operators = ['>=', '<=', '!=', '>', '<', '=']
    for op in operators:
        if condition.startswith(op):
            val_str = condition[len(op):].strip()
            try:
                val_str = re.sub(r'[^\d.-]', '', val_str)
                return op, float(val_str)
            except ValueError:
                return None, None
    try:
        val_str = re.sub(r'[^\d.-]', '', condition)
        return '>=', float(val_str)
    except ValueError:
        return None, None