import logging
from services.comparison_service import rank_by_use_case
from services.product_service import get_product_specs
from sqlalchemy import text
from config.db_config import get_session

logger = logging.getLogger(__name__)

def calculate_base_score(product_id: int) -> float:
    """
    Calculate a basic overall score for a product based on all available numeric specs.
    Uses min-max normalization across all products for each feature, then averages.
    """
    session = get_session()
    try:
        query = text("""
            SELECT spec_key, numeric_value
            FROM product_numeric_specs
            WHERE product_id = :pid AND numeric_value IS NOT NULL
        """)
        rows = session.execute(query, {"pid": product_id}).fetchall()
        if not rows:
            return 0.0
        
        all_values = {}
        for key in [r.spec_key for r in rows]:
            q = text("SELECT numeric_value FROM product_numeric_specs WHERE spec_key = :key AND numeric_value IS NOT NULL")
            vals = [v[0] for v in session.execute(q, {"key": key}).fetchall()]
            if vals:
                all_values[key] = (min(vals), max(vals))
        
        total_normalized = 0.0
        count = 0
        for row in rows:
            key = row.spec_key
            val = row.numeric_value
            if key in all_values:
                mn, mx = all_values[key]
                if mx > mn:
                    if key == "weight":
                        normalized = 1.0 - (val - mn) / (mx - mn)
                    else:
                        normalized = (val - mn) / (mx - mn)
                    total_normalized += normalized
                    count += 1
        
        return total_normalized / count if count > 0 else 0.0
    except Exception as e:
        logger.error(f"Error calculating base score for product {product_id}: {e}")
        return 0.0
    finally:
        session.close()

def rank_products(product_ids: list, use_case: str):
    if not product_ids:
        return []
    
    if not use_case:
        results = []
        for pid in product_ids:
            try:
                specs = get_product_specs(pid)
                base_score = calculate_base_score(pid)
                results.append({
                    "id": pid,
                    "name": specs.get("product", {}).get("name", "Unknown"),
                    "brand": specs.get("product", {}).get("brand", "Unknown"),
                    "category": specs.get("product", {}).get("category", ""),
                    "score": base_score,
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