"""
Use-case weights — только реальные числовые фичи из feature_extractor.
"""
import logging
from sqlalchemy.dialects.postgresql import insert as pg_insert
from database.models import UseCaseWeight

logger = logging.getLogger(__name__)

USE_CASE_PROFILES = {
    "gaming": {
        "refresh_rate": 0.25,
        "ram": 0.25,
        "display_size": 0.15,
        "battery_capacity": 0.15,
        "charging_watts": 0.10,
        "cpu_generation": 0.10,
    },
    "camera": {
        "camera_mp": 0.10,           # сильно снижено – мегапиксели не главное
        "has_ois": 0.25,             # оптическая стабилизация критична
        "selfie_camera_mp": 0.10,
        "display_size": 0.10,
        "refresh_rate": 0.05,
        "battery_capacity": 0.05,
        "charging_watts": 0.05,
        "storage": 0.05,
        "cpu_generation": 0.15,      # процессор важен для обработки фото
        "weight": 0.10,              # лёгкий телефон удобнее держать при съёмке
    },
    "battery_life": {
        "battery_capacity": 0.45,
        "charging_watts": 0.25,
        "display_size": 0.10,
        "refresh_rate": 0.10,
        "weight": 0.10,
    },
    "multimedia": {
        "display_size": 0.35,
        "refresh_rate": 0.25,
        "storage": 0.15,
        "battery_capacity": 0.10,
        "ram": 0.10,
        "charging_watts": 0.05,
    },
    "compact": {
        "weight": 0.40,
        "display_size": 0.25,
        "battery_capacity": 0.15,
        "camera_mp": 0.10,
        "storage": 0.10,
    },
}


def insert_use_case_weights(session) -> int:
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
        stmt = stmt.on_conflict_do_update(
            index_elements=["use_case", "feature_key"],
            set_={"weight": stmt.excluded.weight}
        )
        session.execute(stmt)
        session.commit()
    count = len(values_to_insert)
    logger.info(f"Inserted/Updated {count} use-case weight entries across {len(USE_CASE_PROFILES)} profiles")
    return count