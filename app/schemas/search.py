"""
Search schemas for visual search API.
"""
from pydantic import BaseModel, Field, ConfigDict, field_serializer
from typing import List, Optional
from decimal import Decimal


class SearchResult(BaseModel):
    """Результат поиска одного товара."""
    product_id: str = Field(..., description="Internal product ID")
    external_id: str = Field(..., description="External product ID")
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    category: Optional[str] = Field(None, description="Product category")
    price: Optional[Decimal] = Field(None, description="Product price")
    currency: Optional[str] = Field(None, description="Currency code")
    image_url: Optional[str] = Field(None, description="Product image URL")
    similarity_score: float = Field(..., ge=0.0, le=1.0, description="Similarity score (0.0-1.0)")
    
    @field_serializer('price')
    def serialize_price(self, price: Optional[Decimal], _info):
        return float(price) if price is not None else None


class SearchResponse(BaseModel):
    """Ответ API поиска."""
    query_time_ms: int = Field(..., description="Query execution time in milliseconds")
    results_count: int = Field(..., description="Number of results returned")
    results: List[SearchResult] = Field(default=[], description="Search results")


class TextSearchRequest(BaseModel):
    """Запрос текстового поиска."""
    query: str = Field(..., min_length=1, max_length=500, description="Search query text")
    limit: int = Field(default=10, ge=1, le=50, description="Maximum number of results")
    min_similarity: float = Field(default=0.0, ge=0.0, le=1.0, description="Minimum similarity threshold")

