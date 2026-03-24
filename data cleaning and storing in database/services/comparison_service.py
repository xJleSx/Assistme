"""
Comparison service — multi-product comparison and use-case ranking.
"""
import logging
from sqlalchemy import text
from config.db_config import get_session

logger = logging.getLogger(__name__)


def compare_products(product_ids: list) -> dict:
    """
    Compare multiple products side by side.
    
    Returns:
        {
            "products": [
                {"id": 1, "name": "iPhone 16", "brand": "Apple"},
                {"id": 2, "name": "Galaxy S25", "brand": "Samsung"},
            ],
            "sections": [
                {
                    "name": "DISPLAY",
                    "fields": [
                        {
                            "name": "Type",
                            "display_name": "Type",
                            "values": {1: "Super Retina XDR OLED", 2: "Dynamic AMOLED 2X"}
                        },
                    ]
                }
            ]
        }
    """
    if not product_ids:
        return None
    
    session = get_session()
    try:
        placeholders = ", ".join([f":p{i}" for i in range(len(product_ids))])
        params = {f"p{i}": pid for i, pid in enumerate(product_ids)}
        
        # Get product info
        prod_query = text(f"""
            SELECT p.id, p.name, b.name AS brand_name, c.name AS category_name
            FROM products p
            JOIN brands b ON b.id = p.brand_id
            JOIN categories c ON c.id = p.category_id
            WHERE p.id IN ({placeholders})
        """)
        prod_rows = session.execute(prod_query, params).fetchall()
        
        products = []
        for row in prod_rows:
            products.append({
                "id": row.id,
                "name": row.name,
                "brand": row.brand_name,
                "category": row.category_name,
            })
        
        # Get all spec values
        spec_query = text(f"""
            SELECT 
                ss.name AS section_name,
                ss.display_order AS section_order,
                sf.name AS field_name,
                sf.display_name,
                sf.display_order AS field_order,
                psv.product_id,
                psv.value
            FROM product_spec_values psv
            JOIN spec_fields sf ON sf.id = psv.field_id
            JOIN spec_sections ss ON ss.id = sf.section_id
            WHERE psv.product_id IN ({placeholders})
            ORDER BY ss.display_order, sf.display_order
        """)
        spec_rows = session.execute(spec_query, params).fetchall()
        
        # Build comparison structure
        sections = {}
        for row in spec_rows:
            if row.section_name not in sections:
                sections[row.section_name] = {
                    "name": row.section_name,
                    "order": row.section_order,
                    "fields": {}
                }
            
            sec = sections[row.section_name]
            if row.field_name not in sec["fields"]:
                sec["fields"][row.field_name] = {
                    "name": row.field_name,
                    "display_name": row.display_name or row.field_name,
                    "order": row.field_order,
                    "values": {}
                }
            
            sec["fields"][row.field_name]["values"][row.product_id] = row.value
        
        # Convert to sorted lists
        sorted_sections = sorted(sections.values(), key=lambda s: s["order"])
        result_sections = []
        for sec in sorted_sections:
            sorted_fields = sorted(sec["fields"].values(), key=lambda f: f["order"])
            result_sections.append({
                "name": sec["name"],
                "fields": [{
                    "name": f["name"],
                    "display_name": f["display_name"],
                    "values": f["values"]
                } for f in sorted_fields]
            })
        
        return {
            "products": products,
            "sections": result_sections,
        }
    finally:
        session.close()


def rank_by_use_case(product_ids: list, use_case: str) -> list:
    """
    Rank products by a use-case profile using weighted scoring.
    
    Returns:
        List of products sorted by score (descending):
        [{"product_id": 1, "name": "...", "score": 0.85, "details": {...}}, ...]
    """
    session = get_session()
    try:
        # Get weights for this use case
        weight_query = text("""
            SELECT feature_key, weight
            FROM use_case_weights
            WHERE use_case = :use_case
        """)
        weight_rows = session.execute(weight_query, {"use_case": use_case}).fetchall()
        weights = {row.feature_key: row.weight for row in weight_rows}
        
        if not weights:
            logger.warning(f"No weights found for use case: {use_case}")
            return []
        
        placeholders = ", ".join([f":p{i}" for i in range(len(product_ids))])
        params = {f"p{i}": pid for i, pid in enumerate(product_ids)}
        
        # Get numeric features for these products
        feat_query = text(f"""
            SELECT pf.product_id, p.name, b.name AS brand_name,
                   pf.feature_key, pf.feature_value_numeric
            FROM product_features pf
            JOIN products p ON p.id = pf.product_id
            JOIN brands b ON b.id = p.brand_id
            WHERE pf.product_id IN ({placeholders})
              AND pf.feature_value_numeric IS NOT NULL
        """)
        feat_rows = session.execute(feat_query, params).fetchall()
        
        # Collect features per product
        product_features = {}
        product_info = {}
        for row in feat_rows:
            if row.product_id not in product_features:
                product_features[row.product_id] = {}
                product_info[row.product_id] = {
                    "name": row.name,
                    "brand": row.brand_name,
                }
            product_features[row.product_id][row.feature_key] = row.feature_value_numeric
        
        # Find min/max for normalization
        all_values = {}
        for pid, feats in product_features.items():
            for key, val in feats.items():
                if key not in all_values:
                    all_values[key] = []
                all_values[key].append(val)
        
        min_max = {}
        for key, vals in all_values.items():
            min_max[key] = (min(vals), max(vals))
        
        # Calculate scores
        results = []
        for pid in product_ids:
            if pid not in product_features:
                continue
            
            feats = product_features[pid]
            score = 0.0
            details = {}
            
            for feature_key, weight in weights.items():
                if feature_key in feats:
                    val = feats[feature_key]
                    mn, mx = min_max.get(feature_key, (0, 1))
                    
                    # Normalize to 0-1 (higher is generally better, except weight)
                    if mx > mn:
                        if feature_key == "weight":
                            # Lower weight is better
                            normalized = 1.0 - (val - mn) / (mx - mn)
                        else:
                            normalized = (val - mn) / (mx - mn)
                    else:
                        normalized = 0.5
                    
                    weighted = normalized * weight
                    score += weighted
                    details[feature_key] = {
                        "value": val,
                        "normalized": round(normalized, 3),
                        "weight": weight,
                        "weighted_score": round(weighted, 3),
                    }
            
            results.append({
                "product_id": pid,
                "name": product_info.get(pid, {}).get("name", "Unknown"),
                "brand": product_info.get(pid, {}).get("brand", "Unknown"),
                "score": round(score, 4),
                "details": details,
            })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results
    finally:
        session.close()


def print_comparison(product_ids: list):
    """Print a comparison table in terminal."""
    data = compare_products(product_ids)
    if not data:
        print("No products to compare")
        return
    
    products = data["products"]
    header = f"{'':>30}"
    for p in products:
        header += f" | {p['brand']} {p['name']:>25}"
    
    print(f"\n{'='*len(header)}")
    print(header)
    print(f"{'='*len(header)}")
    
    for section in data["sections"]:
        print(f"\n  {section['name']}")
        print(f"  {'-'*60}")
        for field in section["fields"]:
            line = f"    {field['display_name']:>26}"
            for p in products:
                val = field["values"].get(p["id"], "—")
                line += f" | {str(val)[:25]:>25}"
            print(line)
