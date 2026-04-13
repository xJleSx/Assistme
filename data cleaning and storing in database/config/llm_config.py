import os
import logging
from dotenv import load_dotenv
import redis

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", os.getenv("OPENAI_API_KEY", ""))
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

# Кэш включён по умолчанию, можно отключить через переменную окружения
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "true").lower() in ("true", "1", "yes")
CACHE_TTL = int(os.getenv("CACHE_TTL", "3600"))  # 1 час по умолчанию

_redis_client = None


def get_redis_client():
    """
    Возвращает клиент Redis, если кэширование включено и соединение установлено.
    При недоступности Redis возвращает None и логирует предупреждение.
    """
    global _redis_client
    if not CACHE_ENABLED:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        _redis_client = redis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            db=REDIS_DB,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2
        )
        # Проверка соединения
        _redis_client.ping()
        logger.info("Connected to Redis at %s:%s", REDIS_HOST, REDIS_PORT)
    except (redis.ConnectionError, redis.TimeoutError) as e:
        logger.warning("Redis unavailable, caching disabled: %s", e)
        _redis_client = None
    return _redis_client