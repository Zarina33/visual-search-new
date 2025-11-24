"""
Product schemas.
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime
from decimal import Decimal


class ProductBase(BaseModel):
    """Base product schema."""
    external_id: str = Field(..., description="External product ID")
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    category: Optional[str] = Field(None, description="Product category")
    price: Optional[Decimal] = Field(None, description="Product price")
    currency: Optional[str] = Field(None, description="Currency code")
    image_url: Optional[str] = Field(None, description="Product image URL")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class ProductCreate(ProductBase):
    """Schema for creating a product."""
    pass


class Product(ProductBase):
    """Schema for product with database fields."""
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="Database ID")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Update timestamp")

