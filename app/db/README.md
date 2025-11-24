# Database Modules

This directory contains database modules for PostgreSQL and Qdrant vector database.

## Overview

- **postgres.py**: SQLAlchemy 2.0 async models and CRUD operations for product metadata
- **qdrant.py**: Vector database manager for product embeddings and similarity search

## PostgreSQL Module

### Models

#### Product
Stores product metadata:
- `id`: Internal auto-increment ID
- `external_id`: Unique external product identifier
- `title`: Product title (max 500 chars)
- `description`: Product description (text)
- `category`: Product category (indexed)
- `price`: Product price (decimal)
- `currency`: Currency code
- `image_url`: URL to product image
- `product_metadata`: Additional JSON metadata
- `created_at`: Creation timestamp
- `updated_at`: Last update timestamp

#### SearchLog
Tracks search queries:
- `id`: Internal auto-increment ID
- `query_type`: Type of search ("image" or "text")
- `product_id`: Related product ID
- `similarity_score`: Similarity score
- `results_count`: Number of results returned
- `search_time_ms`: Search execution time in milliseconds
- `created_at`: Log timestamp

### Usage Examples

#### Initialize Database

```python
from app.db import init_db

# Create all tables
await init_db()
```

#### Create a Product

```python
from app.db import get_session, create_product

async with get_session() as session:
    product = await create_product(session, {
        "external_id": "prod_001",
        "title": "Red Sofa",
        "description": "Comfortable red sofa",
        "category": "furniture",
        "price": 599.99,
        "currency": "USD",
        "image_url": "https://example.com/sofa.jpg",
        "product_metadata": {"color": "red", "material": "fabric"}
    })
    print(f"Created product: {product.id}")
```

#### Get Products

```python
from app.db import get_session, get_products, get_product_by_external_id

async with get_session() as session:
    # Get all products with pagination
    products = await get_products(session, skip=0, limit=10)
    
    # Get specific product
    product = await get_product_by_external_id(session, "prod_001")
```

#### Update a Product

```python
from app.db import get_session, update_product

async with get_session() as session:
    product = await update_product(session, product_id=1, {
        "price": 499.99,
        "product_metadata": {"color": "red", "material": "fabric", "on_sale": True}
    })
```

#### Delete a Product

```python
from app.db import get_session, delete_product

async with get_session() as session:
    success = await delete_product(session, product_id=1)
```

#### Log Search Query

```python
from app.db import get_session, log_search

async with get_session() as session:
    log = await log_search(session, {
        "query_type": "image",
        "product_id": "prod_001",
        "similarity_score": 0.95,
        "results_count": 10,
        "search_time_ms": 150
    })
```

## Qdrant Module

### QdrantManager Class

Manages vector embeddings for similarity search.

**Note:** Product IDs are automatically converted to UUIDs internally for Qdrant compatibility. You can use string IDs (like "prod_001"), and they will be converted to stable UUIDs using uuid5.

### Usage Examples

#### Initialize Qdrant

```python
from app.db import QdrantManager

# Create manager instance
qdrant = QdrantManager()

# Create collection
await qdrant.create_collection(vector_size=512, distance="Cosine")
```

#### Add Vectors

```python
# Add product embeddings
product_ids = ["prod_001", "prod_002", "prod_003"]
vectors = [
    [0.1, 0.2, ...],  # 512-dimensional vector
    [0.3, 0.4, ...],
    [0.5, 0.6, ...]
]
payloads = [
    {"title": "Red Sofa", "category": "furniture"},
    {"title": "Blue Chair", "category": "furniture"},
    {"title": "Wooden Table", "category": "furniture"}
]

await qdrant.upsert_vectors(product_ids, vectors, payloads)
```

#### Search Similar Products

```python
# Search for similar products
query_vector = [0.15, 0.25, ...]  # 512-dimensional query vector

results = await qdrant.search_similar(
    query_vector=query_vector,
    top_k=10,
    score_threshold=0.7
)

for result in results:
    print(f"Product: {result['id']}, Score: {result['score']}")
    print(f"Payload: {result['payload']}")
```

#### Delete Vectors

```python
# Delete product embeddings
await qdrant.delete_vectors(["prod_001", "prod_002"])
```

#### Get Collection Info

```python
# Get collection statistics
info = await qdrant.get_collection_info()
print(f"Collection: {info['name']}")
print(f"Vectors: {info['vectors_count']}")
print(f"Vector size: {info['vector_size']}")
print(f"Distance: {info['distance']}")
```

## Database Initialization Script

Use the initialization script to set up both databases:

```bash
# Run initialization script
python scripts/init_databases.py

# Or make it executable and run directly
chmod +x scripts/init_databases.py
./scripts/init_databases.py
```

The script will:
1. Create PostgreSQL tables
2. Create Qdrant collection
3. Display statistics and status

## Configuration

All database settings are configured in `app/config.py` using environment variables:

### PostgreSQL Settings
- `POSTGRES_HOST`: PostgreSQL host (default: localhost)
- `POSTGRES_PORT`: PostgreSQL port (default: 5432)
- `POSTGRES_DB`: Database name (default: visual_search)
- `POSTGRES_USER`: Database user (default: postgres)
- `POSTGRES_PASSWORD`: Database password (default: postgres)

### Qdrant Settings
- `QDRANT_HOST`: Qdrant host (default: localhost)
- `QDRANT_PORT`: Qdrant HTTP port (default: 6333)
- `QDRANT_COLLECTION_NAME`: Collection name (default: product_embeddings)
- `QDRANT_VECTOR_SIZE`: Vector dimension (default: 512)

## Dependencies

Required packages (already in `pyproject.toml`):
- `sqlalchemy[asyncio]>=2.0.23`: Async SQLAlchemy ORM
- `asyncpg>=0.29.0`: Async PostgreSQL driver
- `qdrant-client>=1.7.0`: Qdrant vector database client
- `loguru>=0.7.2`: Logging library

Install dependencies:
```bash
poetry install
```

## Error Handling

All database operations include comprehensive error handling and logging:
- Errors are logged using `loguru`
- Exceptions are raised with detailed error messages
- Database sessions are automatically rolled back on errors
- Connection pooling handles connection failures gracefully

## Best Practices

1. **Always use async context managers** for database sessions:
   ```python
   async with get_session() as session:
       # Your database operations
   ```

2. **Use transactions** for multiple related operations:
   ```python
   async with get_session() as session:
       product = await create_product(session, product_data)
       await log_search(session, log_data)
       # Both operations committed together
   ```

3. **Handle exceptions** appropriately:
   ```python
   try:
       async with get_session() as session:
           product = await create_product(session, product_data)
   except Exception as e:
       logger.error(f"Failed to create product: {e}")
       # Handle error
   ```

4. **Close connections** when shutting down:
   ```python
   from app.db import close_db
   
   await close_db()
   ```

## Testing

Test the database modules:

```bash
# Run all tests
pytest tests/

# Test specific module
pytest tests/test_postgres.py
pytest tests/test_qdrant.py
```

