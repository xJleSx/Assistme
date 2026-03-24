import logging
from sqlalchemy import text
from schemas.query_schema import StructuredQuery

logger = logging.getLogger(__name__)

def build_product_query(session, structured_query: StructuredQuery):
    """
    Build and execute a SQL query based on the StructuredQuery object.
    Returns a list of product IDs.
    """
    
    # Base query
    base_sql = "SELECT p.id FROM products p "
    joins = []
    where_clauses = []
    params = {}
    
    # 1. Category Filter
    if structured_query.category:
        joins.append("JOIN categories c ON p.category_id = c.id")
        where_clauses.append("c.slug = :category")
        params["category"] = structured_query.category.strip().lower()
        
    # 2. Budget Filter
    # Our data model might not have price as a numeric column natively stored for easy filtering,
    # as prices are stored in 'MISC_Price' text usually.
    # We will skip strict SQL pricing for now or use the 'price' feature if extracted.
    # Note: price wasn't listed in the available_features above explicitly, but if we had a price feature:
    if structured_query.budget:
        # Assuming we eventually parse price into a numeric feature 'price_eur' or similar. 
        # For now, we will add an optional feature filter if it existed, or skip.
        pass
        
    # 3. Features Filters
    feature_joins = 0
    for feature_key, condition in structured_query.filters.items():
        feature_joins += 1
        alias = f"f{feature_joins}"
        joins.append(f"JOIN product_numeric_specs {alias} ON p.id = {alias}.product_id")
        where_clauses.append(f"{alias}.spec_key = :key_{alias}")
        params[f"key_{alias}"] = feature_key
        
        # Parse the condition (e.g., ">4500", "<=200", "=8")
        op, val = _parse_condition(condition)
        if op and val is not None:
            where_clauses.append(f"{alias}.numeric_value {op} :val_{alias}")
            params[f"val_{alias}"] = val
        else:
            logger.warning(f"Failed to parse condition '{condition}' for feature '{feature_key}'")

    # Combine everything
    sql = base_sql
    if joins:
        sql += " " + " ".join(joins)
    if where_clauses:
        sql += " WHERE " + " AND ".join(where_clauses)
        
    logger.debug(f"Executing SQL: {sql} with params: {params}")
    
    # Execute query
    result = session.execute(text(sql), params).fetchall()
    return [row[0] for row in result]

def _parse_condition(condition: str):
    """Extract operator and value from condition string (e.g. '>=120' -> ('>=', 120.0))"""
    condition = condition.strip()
    
    operators = ['>=', '<=', '!=', '>', '<', '=']
    
    for op in operators:
        if condition.startswith(op):
            val_str = condition[len(op):].strip()
            try:
                return op, float(val_str)
            except ValueError:
                return None, None
                
    # If no operator is found, assume equals
    try:
        return '=', float(condition)
    except ValueError:
        return None, None
