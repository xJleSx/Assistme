import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from schemas.query_schema import SearchRequest
from services.ai_query_interpreter import interpret_query
from services.query_builder import build_product_query
from services.ranking_engine import rank_products
from services.explanation_service import generate_explanations, get_diverse_top_products
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
    AI-powered search endpoint.
    """
    try:
        logger.info(f"Interpreting query: {request.query}")
        structured_query = interpret_query(request.query)
        logger.info(f"Structured JSON: {structured_query.model_dump()}")
        
        product_ids = build_product_query(db, structured_query)
        logger.info(f"Candidate product IDs found: {len(product_ids)}")
        
        if not product_ids:
            return {
                "query": request.query,
                "parsed_intent": structured_query.model_dump(),
                "results": [],
                "reason": "No products found matching those exact filters. Try loosening constraints."
            }
            
        # === ИСПРАВЛЕНИЕ ===
        # Раньше было [:50] → только Apple. Теперь ранжируем ВСЕ кандидаты
        top_ids = product_ids                          # ← КЛЮЧЕВОЕ ИЗМЕНЕНИЕ
        ranked_products = rank_products(top_ids, structured_query.use_case)
        
        # Гарантируем присутствие запрошенных брендов
        top_results = get_diverse_top_products(ranked_products, structured_query.brands, num_results=10)
        
        explanation = generate_explanations(
            top_results,
            ranked_products,          # полный список для diversity
            request.query,
            structured_query.brands
        )
        
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