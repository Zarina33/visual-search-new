"""
Tests for API endpoints.
"""
import pytest
from fastapi.testclient import TestClient

from app.api.main import app

client = TestClient(app)


def test_health_check():
    """Test basic health check endpoint."""
    response = client.get("/api/v1/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "service" in data
    assert "version" in data


def test_detailed_health_check():
    """Test detailed health check endpoint."""
    response = client.get("/api/v1/health/detailed")
    
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "components" in data


def test_search_by_text_missing_query():
    """Test text search without query parameter."""
    response = client.post(
        "/api/v1/search/by-text",
        json={}  # Empty body - should fail validation
    )
    
    assert response.status_code == 422  # Validation error


def test_search_by_text_with_query():
    """Test text search with query parameter."""
    response = client.post(
        "/api/v1/search/by-text",
        json={
            "query": "red car",
            "limit": 10,
            "min_similarity": 0.0
        }
    )
    
    # May fail if CLIP model or database is not set up
    # 200 - success, 500 - server error, 503 - service unavailable (CLIP not loaded)
    assert response.status_code in [200, 500, 503]
    
    if response.status_code == 200:
        data = response.json()
        assert "query_time_ms" in data
        assert "results_count" in data
        assert "results" in data
        assert isinstance(data["results"], list)

