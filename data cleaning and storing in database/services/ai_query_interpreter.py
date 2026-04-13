import json
import logging
import re
import hashlib
from openai import OpenAI
from config.llm_config import GROQ_API_KEY, LLM_MODEL, get_redis_client, CACHE_TTL
from schemas.query_schema import StructuredQuery

logger = logging.getLogger(__name__)

client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")

BRAND_MAPPING = {
    'iphone': 'Apple',
    'apple': 'Apple',
    'samsung': 'Samsung',
    'xiaomi': 'Xiaomi',
    'oppo': 'Oppo',
    'oneplus': 'OnePlus',
    'realme': 'Realme',
    'vivo': 'Vivo',
    'motorola': 'Motorola',
    'google': 'Google',
    'pixel': 'Google',
    'asus': 'Asus',
    'sony': 'Sony',
}

SUPPORTED_NUMERIC_FEATURES = {
    'battery_capacity', 'display_size', 'refresh_rate', 'ram', 'storage',
    'camera_mp', 'selfie_camera_mp', 'charging_watts', 'weight'
}


def _get_cache_key(query: str) -> str:
    """Генерирует ключ для Redis на основе запроса и модели."""
    raw = f"{LLM_MODEL}:{query.strip().lower()}"
    return f"llm:query:{hashlib.md5(raw.encode('utf-8')).hexdigest()}"


def _parse_llm_response(content: str, query: str) -> StructuredQuery:
    """Парсит ответ LLM и нормализует данные."""
    if content.startswith("```json"):
        content = content[7:]
    if content.endswith("```"):
        content = content[:-3]
    data = json.loads(content)
    
    if 'brands' in data and data['brands']:
        normalized_brands = []
        for b in data['brands']:
            b_lower = b.lower()
            normalized_brands.append(BRAND_MAPPING.get(b_lower, b))
        data['brands'] = list(set(normalized_brands))
    else:
        data['brands'] = []
    
    if 'models' not in data:
        data['models'] = []
    
    # Clean filters
    if 'filters' in data and isinstance(data['filters'], dict):
        cleaned = {}
        for key, val in data['filters'].items():
            if key not in SUPPORTED_NUMERIC_FEATURES:
                continue
            val_str = str(val)
            if key == 'charging_watts' and (val_str == '>=0' or val_str == '<=0' or val_str == '0'):
                continue
            if not any(op in val_str for op in ['>=', '<=', '>', '<', '=']):
                val_str = f">={val_str}"
            cleaned[key] = val_str
        data['filters'] = cleaned
    else:
        data['filters'] = {}
    
    return StructuredQuery(**data)


def fallback_parse(query: str) -> StructuredQuery:
    query_lower = query.lower()
    
    category = "mobile"
    if "watch" in query_lower:
        category = "watch"
    elif any(w in query_lower for w in ['tablet', 'tab', 'pad']):
        category = "tablet"
    
    budget_match = re.search(r'(?:under|below|<=|max|budget)[\s:]*(\d+)', query_lower)
    if not budget_match:
        budget_match = re.search(r'(\d+)\s*(?:rupees|inr|dollars|usd|eur)', query_lower)
    budget = int(budget_match.group(1)) if budget_match else None
    
    use_case = None
    if any(w in query_lower for w in ['game', 'gaming', 'play']):
        use_case = 'gaming'
    elif any(w in query_lower for w in ['camera', 'photo', 'photography', 'picture', 'selfie']):
        use_case = 'camera'
    elif any(w in query_lower for w in ['battery', 'power', 'long battery', 'endurance']):
        use_case = 'battery_life'
    elif any(w in query_lower for w in ['multimedia', 'media', 'movie', 'video', 'stream']):
        use_case = 'multimedia'
    elif any(w in query_lower for w in ['compact', 'small', 'light', 'pocket']):
        use_case = 'compact'
    
    brands = []
    for key, mapped in BRAND_MAPPING.items():
        if key in query_lower:
            if mapped not in brands:
                brands.append(mapped)
    
    models = []
    brand_pattern = '|'.join(re.escape(k) for k in BRAND_MAPPING.keys())
    model_matches = re.findall(rf'\b(?:{brand_pattern})\s+([\w\s\d]+?)(?=\s+(?:vs|and|or|$))', query_lower, re.IGNORECASE)
    for m in model_matches:
        models.append(m.strip())
    compare_match = re.search(r'compare\s+(.+?)\s+and\s+(.+?)(?:\s|$)', query_lower)
    if compare_match:
        models.append(compare_match.group(1).strip())
        models.append(compare_match.group(2).strip())
    
    filters = {}
    
    bat_match = re.search(r'(?:battery|mah)[\s:]*(\d+)', query_lower)
    if bat_match:
        filters['battery_capacity'] = f">={bat_match.group(1)}"
    
    disp_upper = re.search(r'(?:under|below|max|less than|<=)\s*(\d+\.?\d*)\s*inch', query_lower)
    disp_lower = re.search(r'(?:over|above|min|>=|at least)\s*(\d+\.?\d*)\s*inch', query_lower)
    disp_exact = re.search(r'(\d+\.?\d*)\s*inch', query_lower)
    if disp_upper:
        filters['display_size'] = f"<={disp_upper.group(1)}"
    elif disp_lower:
        filters['display_size'] = f">={disp_lower.group(1)}"
    elif disp_exact and 'under' not in query_lower and 'below' not in query_lower:
        filters['display_size'] = f">={disp_exact.group(1)}"
    elif "big screen" in query_lower:
        filters['display_size'] = ">6"
    
    ram_match = re.search(r'(\d+)\s*gb\s*ram', query_lower)
    if ram_match:
        filters['ram'] = f">={ram_match.group(1)}"
    
    store_match = re.search(r'(\d+)\s*gb\s*storage', query_lower)
    if not store_match:
        store_match = re.search(r'(\d+)\s*gb(?=\D|$)', query_lower)
    if store_match:
        filters['storage'] = f">={store_match.group(1)}"
    
    refresh_match = re.search(r'(\d+)\s*hz', query_lower)
    if refresh_match:
        filters['refresh_rate'] = f">={refresh_match.group(1)}"
    
    cam_match = re.search(r'(\d+)\s*mp\s*camera', query_lower)
    if cam_match:
        filters['camera_mp'] = f">={cam_match.group(1)}"
    
    charge_match = re.search(r'(\d+)\s*w\s*charging', query_lower)
    if charge_match:
        filters['charging_watts'] = f">={charge_match.group(1)}"
    
    weight_upper = re.search(r'(?:under|below|less than|<=)\s*(\d+)\s*g', query_lower)
    if weight_upper:
        filters['weight'] = f"<={weight_upper.group(1)}"
    elif 'lightweight' in query_lower or 'light' in query_lower:
        filters['weight'] = "<=180"
    
    return StructuredQuery(
        category=category,
        budget=budget,
        use_case=use_case,
        brands=brands,
        models=models,
        filters=filters
    )


def interpret_query(user_query: str) -> StructuredQuery:
    """
    Интерпретирует запрос пользователя с помощью LLM, с кэшированием через Redis.
    При недоступности LLM или ошибке кэша использует fallback-парсер.
    """
    redis_client = get_redis_client()
    cache_key = _get_cache_key(user_query)
    
    # Попытка получить из кэша
    if redis_client:
        try:
            cached = redis_client.get(cache_key)
            if cached:
                logger.info("Cache hit for query: %s", user_query[:50])
                data = json.loads(cached)
                return StructuredQuery(**data)
        except Exception as e:
            logger.warning("Redis read error: %s", e)
    
    prompt = f"""You are an electronics search query parser.
Convert the user query into structured JSON.

User Query:
"{user_query}"

Extract the following:
- category: one of "mobile", "tablet", "watch". Default "mobile" if unsure.
- budget: integer (amount in local currency, if mentioned). Use null if not present.
- use_case: one of "gaming", "camera", "battery_life", "multimedia", "compact". Use null if not clear.
- brands: list of brand names as they appear in the query (e.g., "iPhone" → "Apple", "Samsung", "Xiaomi"). Use standard names: Apple, Samsung, Xiaomi, Oppo, OnePlus, etc.
- models: list of specific model names mentioned (e.g., "iPhone 15 Pro", "Galaxy S23", "14 Ultra"). Only include if explicitly stated.
- filters: dictionary of feature constraints. Available numeric features: battery_capacity, display_size, refresh_rate, ram, storage, camera_mp, selfie_camera_mp, charging_watts, weight.
  For all numeric features, use ">=" operator for minimum requirements (e.g., ">=4500" for battery, ">=120" for refresh rate, ">=8" for RAM, ">=128" for storage).
  For weight and display_size, use "<=" operator when the user asks for something compact or smaller (e.g., "under 6 inches" → display_size: "<=6").
  Do NOT use "=" operator for thresholds. Do NOT include units (just numbers).
  Do NOT create filters for "wireless charging" – it is not a numeric feature.

Return JSON only, adhering to the schema:
{{
  "category": "mobile",
  "budget": 50000,
  "use_case": "gaming",
  "brands": ["Apple", "Samsung"],
  "models": ["iPhone 15 Pro", "Galaxy S23"],
  "filters": {{
    "battery_capacity": ">=4500",
    "refresh_rate": ">=120",
    "weight": "<=180"
  }}
}}

Just return the JSON block, no markdown formatting.
"""
    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs only raw JSON. Always use '>=' for minimums, '<=' for maximums (weight, size). Never include units. Never create filters for 'wireless charging'."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=512
        )
        content = response.choices[0].message.content.strip()
        result = _parse_llm_response(content, user_query)
        
        # Сохраняем в кэш
        if redis_client:
            try:
                redis_client.setex(cache_key, CACHE_TTL, result.model_dump_json())
                logger.info("Cached result for query: %s", user_query[:50])
            except Exception as e:
                logger.warning("Redis write error: %s", e)
        
        return result
    except Exception as e:
        logger.error(f"Error interpreting query: {e}. Using fallback parser.")
        return fallback_parse(user_query)