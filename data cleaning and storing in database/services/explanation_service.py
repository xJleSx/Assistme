import logging
from openai import OpenAI
from config.llm_config import GROQ_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")


def get_diverse_top_products(
    ranked_products: list,
    brands_requested: list = None,
    models_requested: list = None,
    num_results: int = 5,
    max_per_brand: int = 2               # <-- новый параметр
) -> list:
    """
    Формирует разнообразный список топ-продуктов.

    - Если указаны конкретные модели, возвращаются только они (без ограничений).
    - Если указаны бренды, сначала включаются лучшие продукты каждого запрошенного бренда,
      затем остальные продукты с учётом max_per_brand.
    - Иначе выбираются лучшие продукты разных брендов, затем оставшиеся с учётом max_per_brand.

    :param ranked_products: список продуктов со скором
    :param brands_requested: список запрошенных брендов
    :param models_requested: список запрошенных моделей
    :param num_results: желаемое количество результатов
    :param max_per_brand: максимальное количество продуктов одного бренда в выдаче
    :return: отфильтрованный и отсортированный список продуктов
    """
    if not ranked_products:
        return []

    # Если запрошены конкретные модели, возвращаем только их без диверсификации
    if models_requested:
        model_matches = []
        for p in ranked_products:
            product_name = f"{p.get('brand', '')} {p.get('name', '')}".lower()
            for model in models_requested:
                if model.lower() in product_name:
                    model_matches.append(p)
                    break
        if model_matches:
            model_matches.sort(key=lambda x: x.get('score', 0), reverse=True)
            return model_matches[:num_results]

    # Счётчики брендов для ограничения max_per_brand
    brand_counts = {}

    def can_add_product(p):
        brand = p.get('brand', '').strip()
        if not brand:
            return True
        return brand_counts.get(brand, 0) < max_per_brand

    result = []
    seen_ids = set()

    # Шаг 1: если указаны бренды, добавляем лучший продукт каждого из них
    if brands_requested:
        best_per_brand = {}
        for p in ranked_products:
            brand = p.get('brand', '').strip()
            if not brand:
                continue
            for req in brands_requested:
                if req.lower() in brand.lower() or brand.lower() in req.lower():
                    brand_key = req
                    if brand_key not in best_per_brand or p.get('score', 0) > best_per_brand[brand_key].get('score', 0):
                        best_per_brand[brand_key] = p
                    break

        forced = sorted(best_per_brand.values(), key=lambda x: x.get('score', 0), reverse=True)
        for p in forced:
            brand = p.get('brand', '').strip()
            result.append(p)
            seen_ids.add(p.get('id'))
            brand_counts[brand] = brand_counts.get(brand, 0) + 1

    # Шаг 2: добавляем оставшиеся продукты с учётом max_per_brand
    for p in ranked_products:
        if len(result) >= num_results:
            break
        if p.get('id') in seen_ids:
            continue
        if not can_add_product(p):
            continue
        result.append(p)
        seen_ids.add(p.get('id'))
        brand = p.get('brand', '').strip()
        if brand:
            brand_counts[brand] = brand_counts.get(brand, 0) + 1

    # Если всё ещё не хватает до num_results, добавляем продукты с игнорированием лимита
    if len(result) < num_results:
        for p in ranked_products:
            if len(result) >= num_results:
                break
            if p.get('id') in seen_ids:
                continue
            result.append(p)
            seen_ids.add(p.get('id'))
            brand = p.get('brand', '').strip()
            if brand:
                brand_counts[brand] = brand_counts.get(brand, 0) + 1

    result.sort(key=lambda x: x.get('score', 0), reverse=True)
    return result[:num_results]


def _clean_numeric_value(feature_key: str, value: float) -> float:
    """Apply sanity limits to numeric specs."""
    if feature_key == "refresh_rate" and value > 240:
        return None
    if feature_key == "battery_capacity" and value > 20000:
        return None
    if feature_key == "display_size" and value > 20:
        return None
    return value


def _build_explanation_prompt(products: list, user_query: str, use_case: str = None) -> str:
    product_lines = []
    for idx, p in enumerate(products[:5], 1):
        line = f"{idx}. {p['brand']} {p['name']} (Score: {p.get('score', 0):.2f})"
        product_lines.append(line)
        details = p.get('details', {})
        if details:
            spec_items = []
            for k, v in list(details.items())[:4]:
                val = v.get('value', 'N/A')
                if isinstance(val, (int, float)):
                    cleaned = _clean_numeric_value(k, val)
                    if cleaned is None:
                        continue
                    val = cleaned
                spec_items.append(f"{k}: {val}")
            if spec_items:
                product_lines.append(f"   Key specs: {', '.join(spec_items)}")

    products_text = "\n".join(product_lines)

    use_case_hint = ""
    if use_case:
        use_case_hint = f"The user is interested in the use case: **{use_case}**. "
    else:
        use_case_hint = "The user did not specify any particular use case. Do not assume one."

    camera_mention = ""
    if "camera" in user_query.lower() or "photo" in user_query.lower():
        camera_mention = "The user specifically cares about camera quality. Please comment on camera specs if available."

    brands_in_list = sorted(set(p['brand'] for p in products[:5] if p.get('brand')))
    brands_note = f"IMPORTANT: The product list includes these brands: {', '.join(brands_in_list)}. Do NOT say any brand is missing unless it is truly absent from this list."

    prompt = f"""User query: "{user_query}"

{use_case_hint}{camera_mention}
{brands_note}

Based on the search results, here are the top recommended products:

{products_text}

Please provide a short, helpful explanation (1-2 paragraphs) that:
- Directly answers the user's question.
- Highlights the #1 recommended product and EXPLAINS WHY it stands out. **YOU MUST MENTION AT LEAST 2-3 KEY SPECIFICATIONS (e.g., battery capacity, camera MP, display size/refresh rate, processor) for the top product, using the actual numbers from the "Key specs" lines.**
- Compare the top product with at least one runner-up, mentioning a specific advantage or disadvantage.
- Mention the most relevant specifications that support the recommendation.
- Do NOT use vague phrases like "well-rounded specifications" or "good balance". Be specific.
- Keep the tone professional and concise.
"""
    return prompt


def generate_explanations(products_for_explanation, all_ranked_products, query: str,
                         brands_requested=None, models_requested=None) -> str:
    """
    Generates a natural language explanation for the recommended products.
    """
    if not products_for_explanation and not all_ranked_products:
        return "No products matched your exact criteria. Try adjusting your filters or budget."

    # Используем max_per_brand=2 для разнообразия, но разрешаем до двух устройств одного бренда
    products_for_explanation = get_diverse_top_products(
        all_ranked_products,
        brands_requested,
        models_requested,
        num_results=6,
        max_per_brand=2
    )

    use_case = None
    query_lower = query.lower()
    if any(w in query_lower for w in ['game', 'gaming', 'play']):
        use_case = 'gaming'
    elif any(w in query_lower for w in ['camera', 'photo', 'photography', 'picture']):
        use_case = 'camera'
    elif any(w in query_lower for w in ['battery', 'power', 'long battery', 'endurance']):
        use_case = 'battery_life'
    elif any(w in query_lower for w in ['multimedia', 'media', 'movie', 'video', 'stream']):
        use_case = 'multimedia'
    elif any(w in query_lower for w in ['compact', 'small', 'light', 'pocket']):
        use_case = 'compact'

    prompt = _build_explanation_prompt(products_for_explanation[:5], query, use_case)

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful electronics expert. Never assume a use case unless explicitly asked. Always mention ALL brands that appear in the provided product list, even if they have low scores. Do not claim a brand is missing if it is present."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.6,
            max_tokens=650
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating explanation: {e}. Using fallback.")
        return "Based on your query, here are the top recommendations from the database."