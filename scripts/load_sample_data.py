"""
Script to load sample product data for testing.
"""
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.postgres import PostgresClient
from app.db.qdrant import QdrantClient
from app.models.clip_model import CLIPModel
from app.utils.image_processing import download_image, process_image


def load_sample_products():
    """Load sample products into the database."""
    
    sample_products = [
        {
            "external_id": "prod_001",
            "title": "Modern Sofa",
            "description": "Comfortable modern sofa for living room",
            "category": "furniture",
            "price": 599.99,
            "currency": "USD",
            "image_url": "https://example.com/sofa.jpg",
        },
        {
            "external_id": "prod_002",
            "title": "Wooden Dining Table",
            "description": "Elegant wooden dining table",
            "category": "furniture",
            "price": 799.99,
            "currency": "USD",
            "image_url": "https://example.com/table.jpg",
        },
        {
            "external_id": "prod_003",
            "title": "Sports Car",
            "description": "High-performance sports car",
            "category": "vehicles",
            "price": 45000.00,
            "currency": "USD",
            "image_url": "https://example.com/car.jpg",
        },
    ]
    
    print("Connecting to PostgreSQL...")
    pg_client = PostgresClient()
    
    print("Creating tables...")
    pg_client.create_tables()
    
    print("Inserting sample products...")
    for product in sample_products:
        try:
            query = """
            INSERT INTO products (external_id, title, description, category, price, currency, image_url)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (external_id) DO UPDATE
            SET title = EXCLUDED.title,
                description = EXCLUDED.description,
                category = EXCLUDED.category,
                price = EXCLUDED.price,
                currency = EXCLUDED.currency,
                image_url = EXCLUDED.image_url
            """
            
            pg_client.execute(
                query,
                (
                    product["external_id"],
                    product["title"],
                    product["description"],
                    product["category"],
                    product["price"],
                    product["currency"],
                    product["image_url"],
                ),
            )
            print(f"  ✓ Inserted {product['external_id']}")
            
        except Exception as e:
            print(f"  ✗ Failed to insert {product['external_id']}: {e}")
    
    pg_client.close()
    print("\nSample data loaded successfully!")


def initialize_qdrant():
    """Initialize Qdrant collection."""
    
    print("Connecting to Qdrant...")
    qdrant_client = QdrantClient()
    
    print("Creating collection...")
    qdrant_client.create_collection(recreate=True)
    
    print("Qdrant collection initialized successfully!")


if __name__ == "__main__":
    print("=" * 60)
    print("Loading Sample Data for Visual Search Project")
    print("=" * 60)
    print()
    
    load_sample_products()
    print()
    initialize_qdrant()
    
    print()
    print("=" * 60)
    print("Setup complete!")
    print("=" * 60)

