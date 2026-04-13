import logging
from services.comparison_service import rank_by_use_case
from services.product_service import get_product_specs
from sqlalchemy import text
from config.db_config import get_session

logger = logging.getLogger(__name__)

# Глобальный кэш min/max значений для ускорения
_global_min_max_cache = None

def _get_global_min_max():
    """Получает min/max для всех числовых фич из product_features одним запросом."""
    global _global_min_max_cache
    if _global_min_max_cache is not None:
        return _global_min_max_cache
    session = get_session()
    try:
        query = text("""
            SELECT feature_key, MIN(feature_value_numeric) as mn, MAX(feature_value_numeric) as mx
            FROM product_features
            WHERE feature_value_numeric IS NOT NULL
            GROUP BY feature_key
        """)
        rows = session.execute(query).fetchall()
        min_max = {}
        for row in rows:
            min_max[row.feature_key] = (row.mn, row.mx)
        _global_min_max_cache = min_max
        return min_max
    except Exception as e:
        logger.error(f"Error fetching global min/max: {e}")
        return {}
    finally:
        session.close()

def calculate_base_scores_batch(product_ids: list) -> dict:
    """
    Вычисляет базовый скор для списка продуктов одним пакетным запросом.
    Возвращает словарь {product_id: score}
    """
    if not product_ids:
        return {}
    
    min_max = _get_global_min_max()
    if not min_max:
        return {pid: 0.0 for pid in product_ids}
    
    placeholders = ", ".join([f":p{i}" for i in range(len(product_ids))])
    params = {f"p{i}": pid for i, pid in enumerate(product_ids)}
    
    session = get_session()
    try:
        query = text(f"""
            SELECT pf.product_id, pf.feature_key, pf.feature_value_numeric
            FROM product_features pf
            WHERE pf.product_id IN ({placeholders})
              AND pf.feature_value_numeric IS NOT NULL
        """)
        rows = session.execute(query, params).fetchall()
        
        # Группируем значения по продуктам
        prod_values = {}
        for row in rows:
            pid = row.product_id
            if pid not in prod_values:
                prod_values[pid] = {}
            prod_values[pid][row.feature_key] = row.feature_value_numeric
        
        scores = {}
        for pid in product_ids:
            values = prod_values.get(pid, {})
            total_normalized = 0.0
            count = 0
            for key, val in values.items():
                if key in min_max:
                    mn, mx = min_max[key]
                    if mx > mn:
                        if key == "weight":
                            normalized = 1.0 - (val - mn) / (mx - mn)
                        else:
                            normalized = (val - mn) / (mx - mn)
                        total_normalized += normalized
                        count += 1
            scores[pid] = total_normalized / count if count > 0 else 0.0
        
        # Для продуктов без фич ставим 0
        for pid in product_ids:
            if pid not in scores:
                scores[pid] = 0.0
        return scores
    except Exception as e:
        logger.error(f"Error calculating batch scores: {e}")
        return {pid: 0.0 for pid in product_ids}
    finally:
        session.close()

def rank_products(product_ids: list, use_case: str):
    if not product_ids:
        return []
    
    if not use_case:
        scores = calculate_base_scores_batch(product_ids)
        results = []
        for pid in product_ids:
            try:
                specs = get_product_specs(pid)
                results.append({
                    "id": pid,
                    "name": specs.get("product", {}).get("name", "Unknown") if specs else "Unknown",
                    "brand": specs.get("product", {}).get("brand", "Unknown") if specs else "Unknown",
                    "category": specs.get("product", {}).get("category", "") if specs else "",
                    "score": scores.get(pid, 0.0),
                    "details": {}
                })
            except Exception as e:
                logger.error(f"Error fetching product {pid}: {e}")
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
    
    try:
        ranked = rank_by_use_case(product_ids, use_case)
        formatted = []
        for r in ranked:
            formatted.append({
                "id": r.get("product_id"),
                "name": r.get("name"),
                "brand": r.get("brand"),
                "score": r.get("score", 0),
                "details": r.get("details", {})
            })
        return formatted
    except Exception as e:
        logger.error(f"Error ranking products by use case '{use_case}': {e}")
        return []