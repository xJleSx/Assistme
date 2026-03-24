import json
import logging
from openai import OpenAI
from config.llm_config import GROQ_API_KEY, LLM_MODEL
from schemas.query_schema import StructuredQuery

logger = logging.getLogger(__name__)

# Use OpenAI client but pointed to Groq's API structure
client = OpenAI(
    api_key=GROQ_API_KEY,
    base_url="https://api.groq.com/openai/v1"
)

def interpret_query(user_query: str) -> StructuredQuery:
    """
    Use LLM to interpret a user's natural language query and convert to structured JSON.
    """
    prompt = f"""You are an electronics search query parser.
Convert the user query into structured JSON.

User Query:
"{user_query}"

Extract the following:
category (mobile, tablet, watch)
budget (amount in local currency, as an integer)
use_case (gaming, camera, battery, multimedia, compact)
filters (feature constraints mapping feature names to SQL operators and values)

Return JSON only, adhering to the following JSON schema:
{{
 "category": "mobile",
 "budget": 50000,
 "use_case": "gaming",
 "filters": {{
   "battery_capacity": ">4500",
   "refresh_rate": ">=120"
 }}
}}

Available features:
battery_capacity
display_size
refresh_rate
ram
storage
camera_mp
charging_watts
weight
processor
gpu_score
cpu_score

Just return the JSON block, no markdown formatting.
"""

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that outputs only raw JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=256
        )
        content = response.choices[0].message.content.strip()
        
        # Remove markdown ticks if the model generates them
        if content.startswith("```json"):
            content = content[7:]
        if content.endswith("```"):
            content = content[:-3]
            
        data = json.loads(content)
        return StructuredQuery(**data)
        
    except Exception as e:
        logger.error(f"Error interpreting query: {e}")
        # Return an empty structured query as fallback
        return StructuredQuery(filters={})
