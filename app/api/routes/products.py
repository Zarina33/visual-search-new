"""
Product management endpoints.
"""
from fastapi import APIRouter, HTTPException, status
from typing import List

from app.schemas.product import Product, ProductCreate
from app.db import postgres

router = APIRouter()


@router.post("/products", response_model=Product, status_code=status.HTTP_201_CREATED)
async def create_product(product: ProductCreate) -> Product:
    """
    Create a new product.
    
    Args:
        product: Product data
        
    Returns:
        Created product with ID
    """
    try:
        pg = PostgresClient()
        
        query = """
        INSERT INTO products (external_id, title, description, category, price, currency, image_url, metadata)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """
        
        result = pg.fetch_one(
            query,
            (
                product.external_id,
                product.title,
                product.description,
                product.category,
                product.price,
                product.currency,
                product.image_url,
                product.metadata,
            ),
        )
        
        return Product(**result)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create product: {str(e)}")


@router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str) -> Product:
    """
    Get product by ID.
    
    Args:
        product_id: Product external ID
        
    Returns:
        Product data
    """
    try:
        pg = PostgresClient()
        
        result = pg.fetch_one(
            "SELECT * FROM products WHERE external_id = %s",
            (product_id,),
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return Product(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get product: {str(e)}")


@router.get("/products", response_model=List[Product])
async def list_products(
    skip: int = 0,
    limit: int = 100,
    category: str = None,
) -> List[Product]:
    """
    List products with pagination.
    
    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        category: Filter by category
        
    Returns:
        List of products
    """
    try:
        pg = PostgresClient()
        
        if category:
            query = """
            SELECT * FROM products 
            WHERE category = %s 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
            """
            results = pg.fetch_all(query, (category, limit, skip))
        else:
            query = """
            SELECT * FROM products 
            ORDER BY created_at DESC 
            LIMIT %s OFFSET %s
            """
            results = pg.fetch_all(query, (limit, skip))
        
        return [Product(**result) for result in results]
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list products: {str(e)}")

