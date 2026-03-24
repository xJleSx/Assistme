"""
Numeric extractor — extracts numeric values from specification text using regex.
"""
import re
import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert
from database.models import ProductNumericSpec

logger = logging.getLogger(__name__)

# Extraction rules: (spec_key, regex_pattern, group_index)
# Each rule maps a spec column pattern to a numeric key
EXTRACTION_RULES = [
    # Battery capacity: "Li-Ion 4005 mAh" → 4005
    {
        "columns": ["BATTERY_Type"],
        "spec_key": "battery_capacity",
        "pattern": r"(\d+)\s*mAh",
        "group": 1,
    },
    # Display size: "6.1 inches" → 6.1
    {
        "columns": ["DISPLAY_Size"],
        "spec_key": "display_size",
        "pattern": r"([\d.]+)\s*inches",
        "group": 1,
    },
    # Weight: "169 g" → 169
    {
        "columns": ["BODY_Weight"],
        "spec_key": "weight",
        "pattern": r"([\d.]+)\s*g\b",
        "group": 1,
    },
    # Camera MP from main camera columns
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
    # Resolution height: "1170 x 2532 pixels" → 2532
    {
        "columns": ["DISPLAY_Resolution"],
        "spec_key": "resolution_height",
        "pattern": r"\d+\s*x\s*(\d+)\s*pixels",
        "group": 1,
    },
    # Resolution width: "1170 x 2532 pixels" → 1170
    {
        "columns": ["DISPLAY_Resolution"],
        "spec_key": "resolution_width",
        "pattern": r"(\d+)\s*x\s*\d+\s*pixels",
        "group": 1,
    },
    # Refresh rate: "120Hz" or "120 Hz"
    {
        "columns": ["DISPLAY_", "DISPLAY_Type"],
        "spec_key": "refresh_rate",
        "pattern": r"(\d+)\s*Hz",
        "group": 1,
    },
    # RAM: "256GB 8GB RAM" → 8
    {
        "columns": ["MEMORY_Internal"],
        "spec_key": "ram",
        "pattern": r"(\d+)\s*GB\s*RAM",
        "group": 1,
    },
    # Storage: "256GB 8GB RAM" → 256, or "128GB" → 128
    {
        "columns": ["MEMORY_Internal"],
        "spec_key": "storage",
        "pattern": r"(\d+)\s*GB(?!\s*RAM)",
        "group": 1,
    },
    # Charging watts: "120W wired" or "25W" → number
    {
        "columns": ["BATTERY_Charging"],
        "spec_key": "charging_watts",
        "pattern": r"(\d+)\s*W\b",
        "group": 1,
    },
    # Screen-to-body ratio: "~86.4%" → 86.4
    {
        "columns": ["BODY_"],
        "spec_key": "screen_to_body_ratio",
        "pattern": r"~?([\d.]+)\s*%\s*screen-to-body",
        "group": 1,
    },
    # Thickness from dimensions: "7.8 mm thickness"  
    {
        "columns": ["BODY_Dimensions"],
        "spec_key": "thickness",
        "pattern": r"([\d.]+)\s*mm\b",
        "group": 1,
    },
]


def extract_numeric_specs(session, product_id: int, row_data: dict) -> int:
    """
    Extract numeric values from a product's raw spec data.
    
    Returns:
        Number of numeric specs inserted
    """
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
                        "spec_key": rule["spec_key"],
                        "numeric_value": numeric_val,
                    })
                    seen_keys.add(rule["spec_key"])
                    break  # Found a match, move to next rule
                except (ValueError, IndexError):
                    continue
    
    if values_to_insert:
        stmt = pg_insert(ProductNumericSpec).values(values_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["product_id", "spec_key"])
        session.execute(stmt)
    
    return len(values_to_insert)
