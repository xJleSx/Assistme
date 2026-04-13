from typing import Optional, Dict, List
from pydantic import BaseModel, Field

class StructuredQuery(BaseModel):
    category: Optional[str] = Field(None, description="Category like 'mobile', 'tablet', or 'watch'")
    budget: Optional[int] = Field(None, description="Maximum budget in the local currency")
    use_case: Optional[str] = Field(None, description="Use case like 'gaming', 'camera', 'battery', 'multimedia', 'compact'")
    brands: List[str] = Field(default_factory=list, description="Brand names to filter, e.g., ['iPhone', 'Samsung']")
    models: List[str] = Field(default_factory=list, description="Specific model names mentioned by user")  # <-- Добавлено: список моделей
    filters: Dict[str, str] = Field(default_factory=dict, description="Feature constraints mapping, e.g. {'battery_capacity': '>4500'}")

class SearchRequest(BaseModel):
    query: str