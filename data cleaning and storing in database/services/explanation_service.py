import logging
from openai import OpenAI
from config.llm_config import GROQ_API_KEY, LLM_MODEL

logger = logging.getLogger(__name__)

# Use OpenAI client but pointed to Groq's API structure
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

def generate_explanations(products, query: str) -> str:
    """
    Generate an explanation for why the products were recommended based on the user's query.
    """
    if not products:
        return "No products matched your exact criteria. Try adjusting your filters or budget."
        
    # Format product list for the prompt
    product_lines = []
    for p in products[:5]: # Only explain the top 5 to save tokens
        product_lines.append(f"- {p['brand']} {p['name']} (Score: {p.get('score', 0):.2f})")
        
    product_list_str = "\n".join(product_lines)
    
    prompt = f"""User query: "{query}"

Recommended products:
{product_list_str}

Explain why these products are recommended.
Keep explanation concise, engaging, and in 1-2 paragraphs. Mention the top 1 or 2 products explicitly and explain how their specs match the user's use case or constraints.
"""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful and knowledgeable electronics expert assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=256
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error generating explanation: {e}")
        return "These products were selected based on your desired features and use case rankings."
