import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from schemas.query_schema import SearchRequest
from services.ai_query_interpreter import interpret_query
from services.query_builder import build_product_query
from services.ranking_engine import rank_products
from services.explanation_service import generate_explanations
from config.db_config import get_session
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

def get_db():
    db = get_session()
    try:
        yield db
    finally:
        db.close()

@router.post("/ai-search")
def ai_search(request: SearchRequest, db: Session = Depends(get_db)):
    """
    AI-powered search endpoint:
    1. Interpret natural language query to structured JSON
    2. Build SQL and fetch product IDs
    3. Rank products by use-case
    4. Generate LLM explanation
    """
    try:
        # Step 1: Interpret Query
        logger.info(f"Interpreting query: {request.query}")
        structured_query = interpret_query(request.query)
        logger.info(f"Structured JSON: {structured_query.model_dump()}")
        
        # Step 2: Build SQL & Retrieve Product IDs
        product_ids = build_product_query(db, structured_query)
        logger.info(f"Candidate product IDs found: {len(product_ids)}")
        
        if not product_ids:
            return {
                "query": request.query,
                "parsed_intent": structured_query.model_dump(),
                "results": [],
                "reason": "No products found matching those exact filters. Try loosening constraints."
            }
            
        # Step 3: Rank Products
        # Rank top 50 to avoid massive latency
        top_ids = product_ids[:50]
        ranked_products = rank_products(top_ids, structured_query.use_case)
        
        # Return top 10 results
        top_results = ranked_products[:10]
        
        # Step 4: Generate Explanation
        explanation = generate_explanations(top_results, request.query)
        
        # Format the final response
        formatted_results = []
        for p in top_results:
            formatted_results.append({
                "product": f"{p['brand']} {p['name']}",
                "score": round(p.get("score", 0), 2),
                "id": p.get("id")
            })
            
        return {
            "query": request.query,
            "parsed_intent": structured_query.model_dump(),
            "results": formatted_results,
            "reason": explanation
        }
        
    except Exception as e:
        logger.error(f"Error processing AI search: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="An error occurred processing your query.")
