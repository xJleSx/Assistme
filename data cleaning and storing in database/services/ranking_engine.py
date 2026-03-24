import logging
from services.comparison_service import rank_by_use_case

logger = logging.getLogger(__name__)

def rank_products(product_ids: list, use_case: str):
    """
    Ranks the provided products using the predefined use case weights.
    Wraps the existing rank_by_use_case from comparison_service.
    """
    if not use_case:
        # If no use case provided, just return in original order by scoring 0
        from services.product_service import get_product_specs
        results = []
        for pid in product_ids:
            try:
                specs = get_product_specs(pid)
                results.append({
                    "id": pid,
                    "name": specs.get("name"),
                    "brand": specs.get("brand"),
                    "category": specs.get("category"),
                    "score": 0,
                    "details": specs.get("features", {})
                })
            except Exception as e:
                logger.error(f"Error fetching product {pid}: {e}")
        return results
        
    try:
        return rank_by_use_case(product_ids, use_case)
    except Exception as e:
        logger.error(f"Error ranking products by use case '{use_case}': {e}")
        return []
