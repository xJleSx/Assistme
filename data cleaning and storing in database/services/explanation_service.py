import logging
from openai import OpenAI
from config.llm_config import GROQ_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

client = OpenAI(api_key=GROQ_API_KEY, base_url="https://api.groq.com/openai/v1")


def get_diverse_top_products(ranked_products: list, brands_requested: list = None, num_results: int = 5) -> list:
    """
    Ensures diversity among top products:
    - If specific brands are requested, the best product from each appears at the top.
    - Otherwise, picks the best product from each brand present in ranked_products,
      then fills the rest with remaining products.
    - Finally, sorts the diverse list by score descending.
    """
    if not ranked_products:
        return []

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

        forced = list(best_per_brand.values())
        forced.sort(key=lambda x: x.get('score', 0), reverse=True)

        diverse = forced[:]
        seen_ids = {p.get('id') for p in forced if p.get('id') is not None}

        for p in ranked_products:
            if p.get('id') not in seen_ids:
                diverse.append(p)
                seen_ids.add(p.get('id'))
                if len(diverse) >= num_results:
                    break
        diverse.sort(key=lambda x: x.get('score', 0), reverse=True)
        return diverse[:num_results]

    # No specific brands requested: take top product from each brand
    best_per_brand_all = {}
    for p in ranked_products:
        brand = p.get('brand', '').strip()
        if not brand:
            continue
        if brand not in best_per_brand_all or p.get('score', 0) > best_per_brand_all[brand].get('score', 0):
            best_per_brand_all[brand] = p

    brand_top = sorted(best_per_brand_all.values(), key=lambda x: x.get('score', 0), reverse=True)
    diverse = brand_top[:num_results]

    if len(diverse) < num_results:
        seen_ids = {p.get('id') for p in diverse if p.get('id') is not None}
        for p in ranked_products:
            if p.get('id') not in seen_ids:
                diverse.append(p)
                seen_ids.add(p.get('id'))
                if len(diverse) >= num_results:
                    break

    diverse.sort(key=lambda x: x.get('score', 0), reverse=True)
    return diverse[:num_results]


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
    """
    Builds a flexible prompt for the LLM based on the actual products and the user's query.
    """
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

    # Определяем все бренды в списке для инструкции
    brands_in_list = sorted(set(p['brand'] for p in products[:5] if p.get('brand')))
    brands_note = f"IMPORTANT: The product list includes these brands: {', '.join(brands_in_list)}. Do NOT say any brand is missing unless it is truly absent from this list."

    prompt = f"""User query: "{user_query}"

{use_case_hint}{camera_mention}
{brands_note}

Based on the search results, here are the top recommended products:

{products_text}

Please provide a short, helpful explanation (1-2 paragraphs) that:
- Directly answers the user's question.
- Highlights the #1 recommended product and why it stands out.
- If multiple brands are present among the top 3, explicitly compare at least two different brands.
- Mention the most relevant specifications (e.g., battery, camera, display, performance) that support the recommendation.
- **CRITICAL: You MUST mention ALL brands that appear in the product list above, even if they have lower scores.** Do not say a brand is missing if it is present.
- Do NOT assume any use case (like gaming, camera, battery) unless the user explicitly mentioned it or the use_case field is provided above.
- Do NOT make up products that are not in the list.
- Be objective and use the scores and specs as guidance.
- Write in the same language as the user query.

Keep the tone professional and concise.
"""
    return prompt


def generate_explanations(products_for_explanation, all_ranked_products, query: str, brands_requested=None) -> str:
    """
    Generates a natural language explanation for the recommended products.
    """
    if not products_for_explanation and not all_ranked_products:
        return "No products matched your exact criteria. Try adjusting your filters or budget."

    products_for_explanation = get_diverse_top_products(
        all_ranked_products, brands_requested, num_results=6
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