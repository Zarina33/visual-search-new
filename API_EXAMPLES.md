# API Examples

Complete examples for using the Visual Search API.

## Base URL

```
http://localhost:8000
```

## Interactive Documentation

Visit `http://localhost:8000/docs` for interactive Swagger UI documentation.

---

## Health Endpoints

### Basic Health Check

```bash
curl http://localhost:8000/api/v1/health
```

**Response:**
```json
{
  "status": "healthy",
  "service": "visual-search-project",
  "version": "0.1.0"
}
```

### Detailed Health Check

```bash
curl http://localhost:8000/api/v1/health/detailed
```

**Response:**
```json
{
  "status": "healthy",
  "service": "visual-search-project",
  "version": "0.1.0",
  "components": {
    "postgres": "healthy",
    "qdrant": "healthy"
  }
}
```

---

## Product Endpoints

### Create Product

```bash
curl -X POST "http://localhost:8000/api/v1/products" \
  -H "Content-Type: application/json" \
  -d '{
    "external_id": "prod_001",
    "title": "Modern Gray Sofa",
    "description": "Comfortable 3-seater sofa with modern design",
    "category": "furniture",
    "price": 599.99,
    "currency": "USD",
    "image_url": "https://example.com/images/sofa.jpg",
    "metadata": {
      "brand": "IKEA",
      "color": "gray",
      "material": "fabric"
    }
  }'
```

**Response:**
```json
{
  "id": 1,
  "external_id": "prod_001",
  "title": "Modern Gray Sofa",
  "description": "Comfortable 3-seater sofa with modern design",
  "category": "furniture",
  "price": 599.99,
  "currency": "USD",
  "image_url": "https://example.com/images/sofa.jpg",
  "metadata": {
    "brand": "IKEA",
    "color": "gray",
    "material": "fabric"
  },
  "created_at": "2025-11-05T10:30:00",
  "updated_at": "2025-11-05T10:30:00"
}
```

### Get Product by ID

```bash
curl http://localhost:8000/api/v1/products/prod_001
```

**Response:**
```json
{
  "id": 1,
  "external_id": "prod_001",
  "title": "Modern Gray Sofa",
  "description": "Comfortable 3-seater sofa with modern design",
  "category": "furniture",
  "price": 599.99,
  "currency": "USD",
  "image_url": "https://example.com/images/sofa.jpg",
  "metadata": {
    "brand": "IKEA",
    "color": "gray",
    "material": "fabric"
  },
  "created_at": "2025-11-05T10:30:00",
  "updated_at": "2025-11-05T10:30:00"
}
```

### List Products

```bash
# List all products (default pagination)
curl "http://localhost:8000/api/v1/products"

# With pagination
curl "http://localhost:8000/api/v1/products?skip=0&limit=10"

# Filter by category
curl "http://localhost:8000/api/v1/products?category=furniture&limit=20"
```

**Response:**
```json
[
  {
    "id": 1,
    "external_id": "prod_001",
    "title": "Modern Gray Sofa",
    "description": "Comfortable 3-seater sofa with modern design",
    "category": "furniture",
    "price": 599.99,
    "currency": "USD",
    "image_url": "https://example.com/images/sofa.jpg",
    "metadata": {
      "brand": "IKEA",
      "color": "gray",
      "material": "fabric"
    },
    "created_at": "2025-11-05T10:30:00",
    "updated_at": "2025-11-05T10:30:00"
  }
]
```

---

## Search Endpoints

### Text Search

Search for products using natural language descriptions.

```bash
# Basic text search
curl -X POST "http://localhost:8000/api/v1/search/text?query=modern+sofa"

# With custom limit
curl -X POST "http://localhost:8000/api/v1/search/text?query=red+sports+car&limit=5"

# With custom similarity threshold
curl -X POST "http://localhost:8000/api/v1/search/text?query=wooden+table&limit=10&threshold=0.7"
```

**Example Query Variations:**
- `"modern gray sofa"`
- `"comfortable couch for living room"`
- `"red sports car"`
- `"wooden dining table"`
- `"blue office chair"`

**Response:**
```json
{
  "query": "modern sofa",
  "query_type": "text",
  "results": [
    {
      "product_id": "prod_001",
      "title": "Modern Gray Sofa",
      "description": "Comfortable 3-seater sofa with modern design",
      "image_url": "https://example.com/images/sofa.jpg",
      "score": 0.89,
      "metadata": {
        "brand": "IKEA",
        "color": "gray",
        "material": "fabric"
      }
    },
    {
      "product_id": "prod_002",
      "title": "Contemporary Sectional Sofa",
      "description": "Large L-shaped sofa with modern aesthetics",
      "image_url": "https://example.com/images/sectional.jpg",
      "score": 0.85,
      "metadata": {
        "brand": "West Elm",
        "color": "beige",
        "material": "leather"
      }
    }
  ],
  "total": 2
}
```

### Image Search

Search for similar products by uploading an image.

```bash
# Search by image
curl -X POST "http://localhost:8000/api/v1/search/image" \
  -F "image=@/path/to/your/image.jpg"

# With custom parameters
curl -X POST "http://localhost:8000/api/v1/search/image" \
  -F "image=@/path/to/sofa.jpg" \
  -F "limit=10" \
  -F "threshold=0.6"
```

**Python Example:**
```python
import requests

# Search by image
with open('sofa.jpg', 'rb') as f:
    files = {'image': f}
    params = {'limit': 10, 'threshold': 0.5}
    response = requests.post(
        'http://localhost:8000/api/v1/search/image',
        files=files,
        params=params
    )
    results = response.json()
    print(results)
```

**Response:**
```json
{
  "query": "sofa.jpg",
  "query_type": "image",
  "results": [
    {
      "product_id": "prod_001",
      "title": "Modern Gray Sofa",
      "description": "Comfortable 3-seater sofa with modern design",
      "image_url": "https://example.com/images/sofa.jpg",
      "score": 0.95,
      "metadata": {
        "brand": "IKEA",
        "color": "gray",
        "material": "fabric"
      }
    },
    {
      "product_id": "prod_003",
      "title": "Minimalist Sofa",
      "description": "Simple and elegant sofa design",
      "image_url": "https://example.com/images/minimal-sofa.jpg",
      "score": 0.88,
      "metadata": {
        "brand": "Muji",
        "color": "white",
        "material": "cotton"
      }
    }
  ],
  "total": 2
}
```

---

## Python SDK Examples

### Complete Workflow Example

```python
import requests
from pathlib import Path

BASE_URL = "http://localhost:8000/api/v1"

# 1. Create a product
def create_product():
    product_data = {
        "external_id": "prod_sofa_001",
        "title": "Modern Gray Sofa",
        "description": "Comfortable 3-seater sofa",
        "category": "furniture",
        "price": 599.99,
        "currency": "USD",
        "image_url": "https://example.com/sofa.jpg"
    }
    
    response = requests.post(f"{BASE_URL}/products", json=product_data)
    return response.json()

# 2. Search by text
def search_by_text(query, limit=10):
    params = {"query": query, "limit": limit}
    response = requests.post(f"{BASE_URL}/search/text", params=params)
    return response.json()

# 3. Search by image
def search_by_image(image_path, limit=10):
    with open(image_path, 'rb') as f:
        files = {'image': f}
        params = {'limit': limit}
        response = requests.post(
            f"{BASE_URL}/search/image",
            files=files,
            params=params
        )
        return response.json()

# 4. Get product details
def get_product(product_id):
    response = requests.get(f"{BASE_URL}/products/{product_id}")
    return response.json()

# Usage
if __name__ == "__main__":
    # Create product
    product = create_product()
    print(f"Created product: {product['external_id']}")
    
    # Text search
    text_results = search_by_text("modern sofa", limit=5)
    print(f"Found {text_results['total']} results for text search")
    
    # Image search
    image_results = search_by_image("sofa.jpg", limit=5)
    print(f"Found {image_results['total']} results for image search")
    
    # Get product details
    product_details = get_product("prod_sofa_001")
    print(f"Product title: {product_details['title']}")
```

### Async Python Example

```python
import httpx
import asyncio

BASE_URL = "http://localhost:8000/api/v1"

async def search_multiple_queries(queries):
    """Search multiple queries in parallel"""
    async with httpx.AsyncClient() as client:
        tasks = [
            client.post(
                f"{BASE_URL}/search/text",
                params={"query": query, "limit": 5}
            )
            for query in queries
        ]
        responses = await asyncio.gather(*tasks)
        return [r.json() for r in responses]

# Usage
queries = ["modern sofa", "wooden table", "sports car"]
results = asyncio.run(search_multiple_queries(queries))
for query, result in zip(queries, results):
    print(f"{query}: {result['total']} results")
```

---

## JavaScript/Node.js Examples

### Using Fetch API

```javascript
const BASE_URL = 'http://localhost:8000/api/v1';

// Create product
async function createProduct() {
  const productData = {
    external_id: 'prod_sofa_001',
    title: 'Modern Gray Sofa',
    description: 'Comfortable 3-seater sofa',
    category: 'furniture',
    price: 599.99,
    currency: 'USD',
    image_url: 'https://example.com/sofa.jpg'
  };
  
  const response = await fetch(`${BASE_URL}/products`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(productData)
  });
  
  return await response.json();
}

// Text search
async function searchByText(query, limit = 10) {
  const params = new URLSearchParams({ query, limit });
  const response = await fetch(`${BASE_URL}/search/text?${params}`, {
    method: 'POST'
  });
  
  return await response.json();
}

// Image search
async function searchByImage(file, limit = 10) {
  const formData = new FormData();
  formData.append('image', file);
  
  const params = new URLSearchParams({ limit });
  const response = await fetch(`${BASE_URL}/search/image?${params}`, {
    method: 'POST',
    body: formData
  });
  
  return await response.json();
}

// Usage
(async () => {
  // Create product
  const product = await createProduct();
  console.log('Created product:', product.external_id);
  
  // Text search
  const results = await searchByText('modern sofa', 5);
  console.log(`Found ${results.total} results`);
})();
```

---

## Background Task Examples

### Using Celery Tasks (Python)

```python
from app.workers.tasks import index_product, batch_index_products, reindex_all_products

# Index single product
task = index_product.delay(
    product_id="prod_001",
    image_url="https://example.com/sofa.jpg"
)

# Check task status
print(f"Task ID: {task.id}")
print(f"Task state: {task.state}")

# Wait for result
result = task.get(timeout=60)
print(f"Result: {result}")

# Batch index multiple products
products = [
    {"product_id": "prod_001", "image_url": "https://example.com/sofa1.jpg"},
    {"product_id": "prod_002", "image_url": "https://example.com/sofa2.jpg"},
    {"product_id": "prod_003", "image_url": "https://example.com/sofa3.jpg"},
]

batch_task = batch_index_products.delay(products)
batch_result = batch_task.get(timeout=300)
print(f"Indexed {batch_result['successful']} products")

# Reindex all products
reindex_task = reindex_all_products.delay()
reindex_result = reindex_task.get(timeout=3600)
print(f"Reindexed {reindex_result['successful']} products")
```

---

## Error Handling

### Common Error Responses

**400 Bad Request:**
```json
{
  "detail": "File must be an image"
}
```

**404 Not Found:**
```json
{
  "detail": "Product not found"
}
```

**422 Validation Error:**
```json
{
  "detail": [
    {
      "loc": ["query"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

**500 Internal Server Error:**
```json
{
  "detail": "Search failed: Connection timeout"
}
```

### Error Handling Example

```python
import requests

def safe_search(query):
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/search/text",
            params={"query": query, "limit": 10},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e.response.status_code}")
        print(f"Detail: {e.response.json()}")
    except requests.exceptions.ConnectionError:
        print("Connection error: Could not connect to API")
    except requests.exceptions.Timeout:
        print("Timeout error: Request took too long")
    except Exception as e:
        print(f"Unexpected error: {e}")
    
    return None
```

---

## Rate Limiting (Future Implementation)

When rate limiting is implemented, responses will include headers:

```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1699200000
```

---

## Best Practices

1. **Use appropriate limits**: Don't request more results than needed
2. **Set reasonable thresholds**: Higher threshold = more relevant but fewer results
3. **Handle errors gracefully**: Always check response status
4. **Use timeouts**: Set reasonable timeouts for requests
5. **Batch operations**: Use batch endpoints for multiple items
6. **Cache results**: Cache frequent queries on client side
7. **Retry logic**: Implement exponential backoff for retries

---

**Last Updated**: November 5, 2025

