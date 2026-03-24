from fastapi import FastAPI
from api.search_routes import router as search_router
import uvicorn
import logging

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Electronics Comparison AI Search",
    description="AI-powered search and recommendation API",
    version="1.0.0"
)

app.include_router(search_router, prefix="/api")

@app.get("/")
def health_check():
    return {"status": "ok", "message": "API is running."}

if __name__ == "__main__":
    uvicorn.run("api_main:app", host="0.0.0.0", port=8000, reload=True)
