#!/usr/bin/env python3
"""
Example script demonstrating database module usage.

This script shows how to:
1. Create products in PostgreSQL
2. Store embeddings in Qdrant
3. Search for similar products
4. Log search queries
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import (
    init_db,
    get_session,
    create_product,
    get_product_by_external_id,
    get_products,
    update_product,
    log_search,
    QdrantManager,
)


async def example_1_basic_product_operations():
    """Example 1: Basic product CRUD operations."""
    print("\n" + "="*60)
    print("EXAMPLE 1: Basic Product Operations")
    print("="*60)
    
    async with get_session() as session:
        # Create a product
        print("\n1. Creating a product...")
        product = await create_product(session, {
            "external_id": "example_prod_001",
            "title": "Comfortable Red Sofa",
            "description": "A beautiful 3-seater sofa in red fabric",
            "category": "furniture",
            "price": 599.99,
            "currency": "USD",
            "image_url": "https://example.com/sofa.jpg",
            "product_metadata": {
                "color": "red",
                "material": "fabric",
                "seats": 3,
                "dimensions": "200x90x85 cm"
            }
        })
        print(f"✅ Created product: {product.external_id} (ID: {product.id})")
        
        # Get product by external_id
        print("\n2. Retrieving product by external_id...")
        retrieved = await get_product_by_external_id(session, "example_prod_001")
        print(f"✅ Retrieved: {retrieved.title}")
        print(f"   Price: {retrieved.price} {retrieved.currency}")
        print(f"   Category: {retrieved.category}")
        
        # Update product
        print("\n3. Updating product price...")
        updated = await update_product(session, product.id, {
            "price": 499.99,
            "product_metadata": {
                "color": "red",
                "material": "fabric",
                "seats": 3,
                "dimensions": "200x90x85 cm",
                "on_sale": True,
                "discount": 100.00
            }
        })
        print(f"✅ Updated price: {updated.price} {updated.currency}")
        print(f"   On sale: {updated.product_metadata.get('on_sale')}")


async def example_2_batch_product_creation():
    """Example 2: Create multiple products."""
    print("\n" + "="*60)
    print("EXAMPLE 2: Batch Product Creation")
    print("="*60)
    
    products_data = [
        {
            "external_id": "example_prod_002",
            "title": "Modern Blue Chair",
            "category": "furniture",
            "price": 149.99,
            "currency": "USD",
        },
        {
            "external_id": "example_prod_003",
            "title": "Wooden Dining Table",
            "category": "furniture",
            "price": 799.99,
            "currency": "USD",
        },
        {
            "external_id": "example_prod_004",
            "title": "Leather Office Chair",
            "category": "furniture",
            "price": 299.99,
            "currency": "USD",
        },
    ]
    
    print(f"\nCreating {len(products_data)} products...")
    
    async with get_session() as session:
        for product_data in products_data:
            product = await create_product(session, product_data)
            print(f"✅ Created: {product.external_id} - {product.title}")


async def example_3_qdrant_operations():
    """Example 3: Qdrant vector operations."""
    print("\n" + "="*60)
    print("EXAMPLE 3: Qdrant Vector Operations")
    print("="*60)
    
    # Initialize Qdrant manager
    print("\n1. Initializing Qdrant...")
    qdrant = QdrantManager()
    
    # Create collection
    print("\n2. Creating collection...")
    await qdrant.create_collection(vector_size=512, distance="Cosine")
    
    # Get collection info
    info = await qdrant.get_collection_info()
    print(f"✅ Collection: {info['name']}")
    print(f"   Vector size: {info['vector_size']}")
    print(f"   Distance: {info['distance']}")
    print(f"   Vectors count: {info['vectors_count']}")
    
    # Create sample embeddings (in real scenario, these would come from CLIP model)
    print("\n3. Adding sample embeddings...")
    product_ids = [
        "example_prod_001",
        "example_prod_002",
        "example_prod_003",
        "example_prod_004"
    ]
    
    # Simulate embeddings (normally from CLIP model)
    # For demo, we'll create simple vectors
    import random
    random.seed(42)
    vectors = [[random.random() for _ in range(512)] for _ in range(4)]
    
    payloads = [
        {"title": "Comfortable Red Sofa", "category": "furniture"},
        {"title": "Modern Blue Chair", "category": "furniture"},
        {"title": "Wooden Dining Table", "category": "furniture"},
        {"title": "Leather Office Chair", "category": "furniture"},
    ]
    
    await qdrant.upsert_vectors(product_ids, vectors, payloads)
    print(f"✅ Added {len(product_ids)} vectors")
    
    # Search for similar products
    print("\n4. Searching for similar products...")
    query_vector = vectors[0]  # Use first product as query
    
    results = await qdrant.search_similar(
        query_vector=query_vector,
        top_k=3,
        score_threshold=0.0
    )
    
    print(f"✅ Found {len(results)} similar products:")
    for i, result in enumerate(results, 1):
        print(f"   {i}. {result['payload']['title']}")
        print(f"      ID: {result['id']}")
        print(f"      Similarity: {result['score']:.4f}")
    
    # Close connection
    qdrant.close()


async def example_4_search_logging():
    """Example 4: Log search queries."""
    print("\n" + "="*60)
    print("EXAMPLE 4: Search Query Logging")
    print("="*60)
    
    async with get_session() as session:
        print("\n1. Logging image search...")
        log1 = await log_search(session, {
            "query_type": "image",
            "product_id": "example_prod_001",
            "similarity_score": 0.95,
            "results_count": 10,
            "search_time_ms": 150
        })
        print(f"✅ Logged image search (ID: {log1.id})")
        
        print("\n2. Logging text search...")
        log2 = await log_search(session, {
            "query_type": "text",
            "product_id": "example_prod_002",
            "similarity_score": 0.87,
            "results_count": 5,
            "search_time_ms": 85
        })
        print(f"✅ Logged text search (ID: {log2.id})")


async def example_5_complete_workflow():
    """Example 5: Complete workflow - Add product with embedding and search."""
    print("\n" + "="*60)
    print("EXAMPLE 5: Complete Workflow")
    print("="*60)
    
    # Step 1: Create product in PostgreSQL
    print("\n1. Creating product in PostgreSQL...")
    async with get_session() as session:
        product = await create_product(session, {
            "external_id": "example_prod_005",
            "title": "Gray Sectional Sofa",
            "description": "Large L-shaped sectional sofa",
            "category": "furniture",
            "price": 1299.99,
            "currency": "USD",
            "image_url": "https://example.com/sectional.jpg",
            "product_metadata": {"color": "gray", "type": "sectional"}
        })
        print(f"✅ Product created: {product.external_id}")
    
    # Step 2: Generate and store embedding
    print("\n2. Storing embedding in Qdrant...")
    qdrant = QdrantManager()
    
    # Simulate CLIP embedding
    import random
    random.seed(123)
    embedding = [random.random() for _ in range(512)]
    
    await qdrant.upsert_vectors(
        product_ids=[product.external_id],
        vectors=[embedding],
        payloads=[{
            "title": product.title,
            "category": product.category,
            "price": float(product.price)
        }]
    )
    print(f"✅ Embedding stored for: {product.external_id}")
    
    # Step 3: Search for similar products
    print("\n3. Searching for similar products...")
    results = await qdrant.search_similar(
        query_vector=embedding,
        top_k=5,
        score_threshold=0.5
    )
    print(f"✅ Found {len(results)} similar products")
    
    # Step 4: Log the search
    print("\n4. Logging search query...")
    async with get_session() as session:
        await log_search(session, {
            "query_type": "image",
            "product_id": product.external_id,
            "similarity_score": results[0]['score'] if results else 0.0,
            "results_count": len(results),
            "search_time_ms": 120
        })
    print("✅ Search logged")
    
    qdrant.close()


async def example_6_query_products():
    """Example 6: Query and display products."""
    print("\n" + "="*60)
    print("EXAMPLE 6: Query Products")
    print("="*60)
    
    async with get_session() as session:
        print("\nRetrieving all products...")
        products = await get_products(session, skip=0, limit=10)
        
        print(f"\n✅ Found {len(products)} products:\n")
        for product in products:
            print(f"📦 {product.title}")
            print(f"   ID: {product.external_id}")
            print(f"   Category: {product.category}")
            print(f"   Price: {product.price} {product.currency}")
            print(f"   Created: {product.created_at}")
            print()


async def main():
    """Run all examples."""
    print("\n" + "="*60)
    print("🚀 DATABASE MODULES USAGE EXAMPLES")
    print("="*60)
    
    try:
        # Initialize database
        print("\nInitializing database...")
        await init_db()
        print("✅ Database initialized")
        
        # Run examples
        await example_1_basic_product_operations()
        await example_2_batch_product_creation()
        await example_3_qdrant_operations()
        await example_4_search_logging()
        await example_5_complete_workflow()
        await example_6_query_products()
        
        print("\n" + "="*60)
        print("✅ ALL EXAMPLES COMPLETED SUCCESSFULLY!")
        print("="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())

