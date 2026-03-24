"""
Feature extractor — normalizes specs into structured features for filtering/ranking.
"""
import re
import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert
from database.models import ProductFeature

logger = logging.getLogger(__name__)

# Feature mapping rules
# Each rule defines: source columns, feature_key, extraction type, and regex
FEATURE_RULES = [
    # --- Numeric features ---
    {
        "columns": ["BATTERY_Type"],
        "feature_key": "battery_capacity",
        "type": "numeric",
        "pattern": r"(\d+)\s*mAh",
    },
    {
        "columns": ["DISPLAY_Size"],
        "feature_key": "display_size",
        "type": "numeric",
        "pattern": r"([\d.]+)\s*inches",
    },
    {
        "columns": ["BODY_Weight"],
        "feature_key": "weight",
        "type": "numeric",
        "pattern": r"([\d.]+)\s*g\b",
    },
    {
        "columns": ["MAIN_CAMERA_Single", "MAIN_CAMERA_Dual", "MAIN_CAMERA_Triple", "MAIN_CAMERA_Quad"],
        "feature_key": "camera_mp",
        "type": "numeric",
        "pattern": r"(\d+)\s*MP",
    },
    {
        "columns": ["SELFIE_CAMERA_Single", "SELFIE_CAMERA_Dual"],
        "feature_key": "selfie_camera_mp",
        "type": "numeric",
        "pattern": r"(\d+)\s*MP",
    },
    {
        "columns": ["MEMORY_Internal"],
        "feature_key": "ram",
        "type": "numeric",
        "pattern": r"(\d+)\s*GB\s*RAM",
    },
    {
        "columns": ["MEMORY_Internal"],
        "feature_key": "storage",
        "type": "numeric",
        "pattern": r"(\d+)\s*GB(?!\s*RAM)",
    },
    {
        "columns": ["DISPLAY_", "DISPLAY_Type"],
        "feature_key": "refresh_rate",
        "type": "numeric",
        "pattern": r"(\d+)\s*Hz",
    },
    {
        "columns": ["BATTERY_Charging"],
        "feature_key": "charging_watts",
        "type": "numeric",
        "pattern": r"(\d+)\s*W\b",
    },
    {
        "columns": ["PLATFORM_Chipset"],
        "feature_key": "cpu_generation",
        "type": "numeric",
        "pattern": r"Gen\s*(\d+)",
    },
    # --- Text features ---
    {
        "columns": ["DISPLAY_Type"],
        "feature_key": "display_type",
        "type": "text",
        "pattern": None,  # Take full value
    },
    {
        "columns": ["PLATFORM_CPU"],
        "feature_key": "processor",
        "type": "text",
        "pattern": None,
    },
    {
        "columns": ["PLATFORM_Chipset"],
        "feature_key": "chipset",
        "type": "text",
        "pattern": None,
    },
    {
        "columns": ["PLATFORM_GPU"],
        "feature_key": "gpu",
        "type": "text",
        "pattern": None,
    },
    {
        "columns": ["PLATFORM_OS"],
        "feature_key": "os",
        "type": "text",
        "pattern": None,
    },
    {
        "columns": ["COMMS_Bluetooth"],
        "feature_key": "bluetooth",
        "type": "text",
        "pattern": None,
    },
    {
        "columns": ["COMMS_NFC"],
        "feature_key": "nfc",
        "type": "text",
        "pattern": None,
    },
    {
        "columns": ["COMMS_USB"],
        "feature_key": "usb_type",
        "type": "text",
        "pattern": None,
    },
    {
        "columns": ["NETWORK_Technology"],
        "feature_key": "network_technology",
        "type": "text",
        "pattern": None,
    },
    {
        "columns": ["BODY_SIM"],
        "feature_key": "sim_type",
        "type": "text",
        "pattern": None,
    },
    {
        "columns": ["FEATURES_Sensors"],
        "feature_key": "sensors",
        "type": "text",
        "pattern": None,
    },
]


def extract_features(session, product_id: int, row_data: dict) -> int:
    """
    Extract normalized features from a product's raw spec data.
    
    Returns:
        Number of features inserted
    """
    values_to_insert = []
    seen_keys = set()
    
    for rule in FEATURE_RULES:
        if rule["feature_key"] in seen_keys:
            continue
        
        for col in rule["columns"]:
            if col not in row_data:
                continue
            
            value = row_data[col]
            if value is None or str(value).strip() == "" or str(value).lower() == "nan":
                continue
            
            text = str(value).strip()
            
            if rule["type"] == "numeric" and rule["pattern"]:
                match = re.search(rule["pattern"], text, re.IGNORECASE)
                if match:
                    try:
                        numeric_val = float(match.group(1))
                        values_to_insert.append({
                            "product_id": product_id,
                            "feature_key": rule["feature_key"],
                            "feature_value_numeric": numeric_val,
                            "feature_value_text": None,
                        })
                        seen_keys.add(rule["feature_key"])
                        break
                    except (ValueError, IndexError):
                        continue
            
            elif rule["type"] == "text":
                values_to_insert.append({
                    "product_id": product_id,
                    "feature_key": rule["feature_key"],
                    "feature_value_numeric": None,
                    "feature_value_text": text,
                })
                seen_keys.add(rule["feature_key"])
                break
    
    if values_to_insert:
        stmt = pg_insert(ProductFeature).values(values_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["product_id", "feature_key"])
        session.execute(stmt)
    
    return len(values_to_insert)
