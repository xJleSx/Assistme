"""
Numeric extractor — extracts numeric values from specification text using regex.
Now inserts into product_features and updates Product.price and price_currency.
"""
import re
import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert
from database.models import ProductFeature, Product
from config.currency_config import get_currency_from_text

logger = logging.getLogger(__name__)

EXTRACTION_RULES = [
    # Battery capacity
    {
        "columns": ["BATTERY_Type"],
        "spec_key": "battery_capacity",
        "pattern": r"(\d+)\s*mAh",
        "group": 1,
    },
    # Display size
    {
        "columns": ["DISPLAY_Size"],
        "spec_key": "display_size",
        "pattern": r"([\d.]+)\s*inches",
        "group": 1,
    },
    # Weight
    {
        "columns": ["BODY_Weight"],
        "spec_key": "weight",
        "pattern": r"([\d.]+)\s*g\b",
        "group": 1,
    },
    # Camera MP
    {
        "columns": ["MAIN_CAMERA_Single", "MAIN_CAMERA_Dual", "MAIN_CAMERA_Triple", "MAIN_CAMERA_Quad"],
        "spec_key": "camera_mp",
        "pattern": r"(\d+)\s*MP",
        "group": 1,
    },
    # Selfie camera MP
    {
        "columns": ["SELFIE_CAMERA_Single", "SELFIE_CAMERA_Dual"],
        "spec_key": "selfie_camera_mp",
        "pattern": r"(\d+)\s*MP",
        "group": 1,
    },
    # Resolution height
    {
        "columns": ["DISPLAY_Resolution"],
        "spec_key": "resolution_height",
        "pattern": r"\d+\s*x\s*(\d+)\s*pixels",
        "group": 1,
    },
    # Resolution width
    {
        "columns": ["DISPLAY_Resolution"],
        "spec_key": "resolution_width",
        "pattern": r"(\d+)\s*x\s*\d+\s*pixels",
        "group": 1,
    },
    # Refresh rate
    {
        "columns": ["DISPLAY_", "DISPLAY_Type"],
        "spec_key": "refresh_rate",
        "pattern": r"(?<!\d)(\d+)\s*Hz(?!\s*x)",
        "group": 1,
    },
    # RAM
    {
        "columns": ["MEMORY_Internal"],
        "spec_key": "ram",
        "pattern": r"(\d+)\s*GB\s*RAM",
        "group": 1,
    },
    # Storage
    {
        "columns": ["MEMORY_Internal"],
        "spec_key": "storage",
        "pattern": r"(\d+)\s*GB(?!\s*RAM)",
        "group": 1,
    },
    # Charging watts
    {
        "columns": ["BATTERY_Charging"],
        "spec_key": "charging_watts",
        "pattern": r"(\d+)\s*W\b",
        "group": 1,
    },
    # Screen-to-body ratio
    {
        "columns": ["BODY_"],
        "spec_key": "screen_to_body_ratio",
        "pattern": r"~?([\d.]+)\s*%\s*screen-to-body",
        "group": 1,
    },
    # Thickness
    {
        "columns": ["BODY_Dimensions"],
        "spec_key": "thickness",
        "pattern": r"([\d.]+)\s*mm\b",
        "group": 1,
    },
    # Price
    {
        "columns": ["MISC_Price"],
        "spec_key": "price",
        "pattern": r"(\d+(?:\.\d+)?)\s*(?:EUR|USD|INR|£|€|$|₹)",
        "group": 1,
    },
    # Aperture (f-number)
    {
        "columns": ["MAIN_CAMERA_Single", "MAIN_CAMERA_Dual", "MAIN_CAMERA_Triple", "MAIN_CAMERA_Quad", "MAIN_CAMERA_Features"],
        "spec_key": "aperture",
        "pattern": r"f/(\d+\.?\d*)",
        "group": 1,
    },
]


def extract_numeric_specs(session, product_id: int, row_data: dict) -> int:
    values_to_insert = []
    seen_keys = set()
    
    for rule in EXTRACTION_RULES:
        if rule["spec_key"] in seen_keys:
            continue
        
        for col in rule["columns"]:
            if col not in row_data:
                continue
            
            value = row_data[col]
            if value is None or str(value).strip() == "" or str(value).lower() == "nan":
                continue
            
            text = str(value)
            match = re.search(rule["pattern"], text, re.IGNORECASE)
            if match:
                try:
                    numeric_val = float(match.group(rule["group"]))
                    
                    values_to_insert.append({
                        "product_id": product_id,
                        "feature_key": rule["spec_key"],
                        "feature_value_numeric": numeric_val,
                        "feature_value_text": None,
                    })
                    seen_keys.add(rule["spec_key"])
                    
                    if rule["spec_key"] == "price":
                        product = session.query(Product).get(product_id)
                        if product:
                            product.price = numeric_val
                            product.price_currency = get_currency_from_text(text)
                    
                    break
                except (ValueError, IndexError):
                    continue
    
    if values_to_insert:
        stmt = pg_insert(ProductFeature).values(values_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["product_id", "feature_key"])
        session.execute(stmt)
    
    return len(values_to_insert)