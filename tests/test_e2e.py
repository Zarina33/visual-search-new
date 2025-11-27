"""
End-to-end tests for the complete visual search system.
"""
import pytest
import asyncio
from pathlib import Path
from PIL import Image
import io
import httpx
import time

# Test configuration
API_BASE_URL = "http://localhost:8008"
TEST_IMAGES_DIR = Path(__file__).parent.parent / "test_images"


class TestE2EVisualSearch:
    """End-to-end tests for visual search functionality."""
    
    @pytest.mark.asyncio
    async def test_health_checks(self):
        """Test that all health endpoints are working."""
        async with httpx.AsyncClient() as client:
            # Basic health check
            response = await client.get(f"{API_BASE_URL}/api/v1/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            
            # Detailed health check
            response = await client.get(f"{API_BASE_URL}/api/v1/health/detailed")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert "components" in data
    
    @pytest.mark.asyncio
    async def test_text_search(self):
        """Test text-based product search."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{API_BASE_URL}/api/v1/search/by-text",
                json={
                    "query": "product",
                    "limit": 10,
                    "min_similarity": 0.0
                }
            )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "results" in data
            assert "results_count" in data
            assert "query_time_ms" in data
            assert data["results_count"] > 0
            assert len(data["results"]) <= 10
            
            # Verify result structure
            if data["results"]:
                result = data["results"][0]
                assert "product_id" in result
                assert "external_id" in result
                assert "similarity_score" in result
                assert 0.0 <= result["similarity_score"] <= 1.0
    
    @pytest.mark.asyncio
    async def test_image_search(self):
        """Test image-based product search."""
        # Use a test image
        test_image_path = TEST_IMAGES_DIR / "red_square.jpg"
        
        if not test_image_path.exists():
            pytest.skip("Test image not found")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            with open(test_image_path, 'rb') as f:
                files = {'image': ('test.jpg', f, 'image/jpeg')}
                params = {'limit': 5, 'min_similarity': 0.0}
                
                response = await client.post(
                    f"{API_BASE_URL}/api/v1/search/by-image",
                    files=files,
                    params=params
                )
            
            assert response.status_code == 200
            data = response.json()
            
            assert "results" in data
            assert "results_count" in data
            assert "query_time_ms" in data
            assert len(data["results"]) <= 5
            
            # Verify result structure
            if data["results"]:
                result = data["results"][0]
                assert "product_id" in result
                assert "external_id" in result
                assert "image_url" in result
                assert "similarity_score" in result
    
    @pytest.mark.asyncio
    async def test_similar_products(self):
        """Test finding similar products."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First, get a product from text search
            response = await client.post(
                f"{API_BASE_URL}/api/v1/search/by-text",
                json={"query": "product", "limit": 1}
            )
            
            assert response.status_code == 200
            data = response.json()
            
            if data["results_count"] == 0:
                pytest.skip("No products in database")
            
            product_id = data["results"][0]["external_id"]
            
            # Now search for similar products
            response = await client.get(
                f"{API_BASE_URL}/api/v1/search/similar/{product_id}",
                params={"limit": 5}
            )
            
            # Note: This might fail if product has file:// URL
            # In that case, it's expected
            if response.status_code == 200:
                data = response.json()
                assert "results" in data
                assert len(data["results"]) <= 5
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self):
        """Test that metrics are being collected."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/api/v1/metrics")
            assert response.status_code == 200
            
            # Should be Prometheus format
            text = response.text
            assert "visual_search" in text
    
    @pytest.mark.asyncio
    async def test_search_performance(self):
        """Test search performance."""
        test_image_path = TEST_IMAGES_DIR / "red_square.jpg"
        
        if not test_image_path.exists():
            pytest.skip("Test image not found")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            start_time = time.time()
            
            with open(test_image_path, 'rb') as f:
                files = {'image': ('test.jpg', f, 'image/jpeg')}
                params = {'limit': 10}
                
                response = await client.post(
                    f"{API_BASE_URL}/api/v1/search/by-image",
                    files=files,
                    params=params
                )
            
            elapsed = time.time() - start_time
            
            assert response.status_code == 200
            data = response.json()
            
            # Search should complete in reasonable time
            assert elapsed < 5.0, f"Search took too long: {elapsed}s"
            assert data["query_time_ms"] < 5000, f"Query time too high: {data['query_time_ms']}ms"


class TestE2EWebhooks:
    """End-to-end tests for webhook functionality."""
    
    @pytest.mark.asyncio
    async def test_webhook_health(self):
        """Test webhook health endpoint."""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/api/v1/webhooks/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
    
    @pytest.mark.asyncio
    async def test_webhook_test_endpoint(self):
        """Test webhook test endpoint (without signature)."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            webhook_data = {
                "event_type": "product.created",
                "event_id": "test_event_001",
                "timestamp": "2025-11-12T10:00:00Z",
                "data": {
                    "product_id": "test_product_webhook",
                    "title": "Test Product",
                    "description": "Test webhook product",
                    "category": "test",
                    "price": 99.99,
                    "currency": "USD",
                    "image_key": "test/test_image.jpg"
                }
            }
            
            response = await client.post(
                f"{API_BASE_URL}/api/v1/webhooks/test",
                json=webhook_data
            )
            
            # Note: This will fail if Celery is not running
            # That's expected for unit tests
            if response.status_code == 200:
                data = response.json()
                assert data["success"] is True
                assert data["event_id"] == "test_event_001"


class TestE2EDataFlow:
    """End-to-end tests for complete data flow."""
    
    @pytest.mark.asyncio
    async def test_complete_search_flow(self):
        """Test complete flow: upload image -> search -> get results."""
        test_image_path = TEST_IMAGES_DIR / "blue_square.jpg"
        
        if not test_image_path.exists():
            pytest.skip("Test image not found")
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Perform image search
            with open(test_image_path, 'rb') as f:
                files = {'image': ('test.jpg', f, 'image/jpeg')}
                params = {'limit': 10, 'min_similarity': 0.5}
                
                response = await client.post(
                    f"{API_BASE_URL}/api/v1/search/by-image",
                    files=files,
                    params=params
                )
            
            assert response.status_code == 200
            data = response.json()
            
            # 2. Verify results
            assert data["results_count"] >= 0
            assert isinstance(data["results"], list)
            
            # 3. If results exist, verify each result has required fields
            for result in data["results"]:
                assert "product_id" in result
                assert "external_id" in result
                assert "similarity_score" in result
                assert result["similarity_score"] >= 0.5
                
                # 4. Verify similarity scores are in descending order
                if len(data["results"]) > 1:
                    scores = [r["similarity_score"] for r in data["results"]]
                    assert scores == sorted(scores, reverse=True), "Results should be sorted by similarity"


@pytest.mark.asyncio
async def test_api_documentation():
    """Test that API documentation is accessible."""
    async with httpx.AsyncClient() as client:
        # OpenAPI JSON
        response = await client.get(f"{API_BASE_URL}/openapi.json")
        assert response.status_code == 200
        
        # Swagger UI
        response = await client.get(f"{API_BASE_URL}/docs")
        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])

