"""
Use case weights — seeds ranking weight profiles for different use cases.
"""
import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert
from database.models import UseCaseWeight

logger = logging.getLogger(__name__)

# Use-case weight profiles
USE_CASE_PROFILES = {
    "gaming": {
        "gpu": 0.25,
        "chipset": 0.20,
        "refresh_rate": 0.20,
        "ram": 0.15,
        "battery_capacity": 0.10,
        "display_size": 0.10,
    },
    "camera": {
        "camera_mp": 0.30,
        "selfie_camera_mp": 0.15,
        "display_type": 0.15,
        "storage": 0.15,
        "chipset": 0.15,
        "battery_capacity": 0.10,
    },
    "battery_life": {
        "battery_capacity": 0.40,
        "charging_watts": 0.25,
        "display_size": 0.15,
        "refresh_rate": 0.10,
        "weight": 0.10,
    },
    "multimedia": {
        "display_size": 0.25,
        "display_type": 0.20,
        "refresh_rate": 0.15,
        "storage": 0.15,
        "battery_capacity": 0.15,
        "ram": 0.10,
    },
    "compact": {
        "weight": 0.30,
        "display_size": 0.25,
        "battery_capacity": 0.20,
        "camera_mp": 0.15,
        "storage": 0.10,
    },
}


def insert_use_case_weights(session) -> int:
    """
    Insert all use-case weight profiles.
    
    Returns:
        Number of weight entries inserted
    """
    values_to_insert = []
    
    for use_case, weights in USE_CASE_PROFILES.items():
        for feature_key, weight in weights.items():
            values_to_insert.append({
                "use_case": use_case,
                "feature_key": feature_key,
                "weight": weight,
            })
    
    if values_to_insert:
        stmt = pg_insert(UseCaseWeight).values(values_to_insert)
        stmt = stmt.on_conflict_do_nothing(index_elements=["use_case", "feature_key"])
        session.execute(stmt)
        session.commit()
    
    count = len(values_to_insert)
    logger.info(f"Inserted {count} use-case weight entries across {len(USE_CASE_PROFILES)} profiles")
    return count
