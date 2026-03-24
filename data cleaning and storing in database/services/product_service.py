"""
Product service — structured spec retrieval (GSM Arena style display).
"""
import logging
from sqlalchemy import text
from config.db_config import get_session

logger = logging.getLogger(__name__)


def get_product_specs(product_id: int) -> dict:
    """
    Get all specs for a product, structured by section and field.
    
    Returns:
        {
            "product": {"id": 1, "name": "...", "brand": "...", "category": "..."},
            "sections": [
                {
                    "name": "DISPLAY",
                    "fields": [
                        {"name": "Type", "display_name": "Type", "value": "Super Retina XDR OLED"},
                        {"name": "Size", "display_name": "Size", "value": "6.1 inches"},
                    ]
                },
                ...
            ]
        }
    """
    session = get_session()
    try:
        query = text("""
            SELECT 
                p.id AS product_id,
                p.name AS product_name,
                b.name AS brand_name,
                c.name AS category_name,
                ss.name AS section_name,
                ss.display_order AS section_order,
                sf.name AS field_name,
                sf.display_name,
                sf.display_order AS field_order,
                psv.value
            FROM product_spec_values psv
            JOIN products p ON p.id = psv.product_id
            JOIN brands b ON b.id = p.brand_id
            JOIN categories c ON c.id = p.category_id
            JOIN spec_fields sf ON sf.id = psv.field_id
            JOIN spec_sections ss ON ss.id = sf.section_id
            WHERE p.id = :product_id
            ORDER BY ss.display_order, sf.display_order
        """)
        
        rows = session.execute(query, {"product_id": product_id}).fetchall()
        
        if not rows:
            return None
        
        first = rows[0]
        result = {
            "product": {
                "id": first.product_id,
                "name": first.product_name,
                "brand": first.brand_name,
                "category": first.category_name,
            },
            "sections": []
        }
        
        current_section = None
        for row in rows:
            if current_section is None or current_section["name"] != row.section_name:
                current_section = {
                    "name": row.section_name,
                    "fields": []
                }
                result["sections"].append(current_section)
            
            current_section["fields"].append({
                "name": row.field_name,
                "display_name": row.display_name or row.field_name,
                "value": row.value,
            })
        
        return result
    finally:
        session.close()


def get_products_by_category(category_slug: str) -> list:
    """Get all products in a category."""
    session = get_session()
    try:
        query = text("""
            SELECT p.id, p.name, p.slug, p.model_code, p.url,
                   b.name AS brand_name, p.release_date
            FROM products p
            JOIN brands b ON b.id = p.brand_id
            JOIN categories c ON c.id = p.category_id
            WHERE c.slug = :slug
            ORDER BY p.name
        """)
        rows = session.execute(query, {"slug": category_slug}).fetchall()
        return [dict(row._mapping) for row in rows]
    finally:
        session.close()


def search_products(query_str: str) -> list:
    """Search products by name."""
    session = get_session()
    try:
        query = text("""
            SELECT p.id, p.name, p.slug, b.name AS brand_name, c.name AS category_name
            FROM products p
            JOIN brands b ON b.id = p.brand_id
            JOIN categories c ON c.id = p.category_id
            WHERE LOWER(p.name) LIKE :q
            ORDER BY p.name
            LIMIT 50
        """)
        rows = session.execute(query, {"q": f"%{query_str.lower()}%"}).fetchall()
        return [dict(row._mapping) for row in rows]
    finally:
        session.close()


def print_product_specs(product_id: int):
    """Print specs in GSM Arena style format."""
    data = get_product_specs(product_id)
    if not data:
        print(f"No product found with ID {product_id}")
        return
    
    p = data["product"]
    print(f"\n{'='*60}")
    print(f"  {p['brand']} {p['name']} ({p['category']})")
    print(f"{'='*60}")
    
    for section in data["sections"]:
        print(f"\n  {section['name']}")
        print(f"  {'-'*40}")
        for field in section["fields"]:
            display = field["display_name"] or field["name"]
            print(f"    {display:.<25} {field['value']}")
