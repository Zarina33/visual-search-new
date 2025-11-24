"""
Test database modules (PostgreSQL and Qdrant).
"""
import pytest
import asyncio
from datetime import datetime
from decimal import Decimal

from app.db import (
    init_db,
    get_session,
    create_product,
    get_product_by_id,
    get_product_by_external_id,
    get_products,
    update_product,
    delete_product,
    log_search,
    close_db,
    QdrantManager,
)
from app.db.postgres import reset_engine


@pytest.fixture(autouse=True)
async def reset_db_engine():
    """Reset database engine before each test to avoid event loop issues."""
    await reset_engine()
    yield
    await reset_engine()


class TestPostgreSQL:
    """Test PostgreSQL database operations."""
    
    @pytest.mark.asyncio
    async def test_create_product(self):
        """Test creating a product."""
        async with get_session() as session:
            product_data = {
                "external_id": f"test_prod_{datetime.utcnow().timestamp()}",
                "title": "Test Product",
                "description": "Test description",
                "category": "test",
                "price": 99.99,
                "currency": "USD",
                "image_url": "https://example.com/test.jpg",
                "product_metadata": {"test": True}
            }
            
            product = await create_product(session, product_data)
            
            assert product.id is not None
            assert product.external_id == product_data["external_id"]
            assert product.title == product_data["title"]
            assert float(product.price) == product_data["price"]
    
    @pytest.mark.asyncio
    async def test_get_product_by_external_id(self):
        """Test retrieving a product by external ID."""
        async with get_session() as session:
            # Create a test product
            external_id = f"test_prod_{datetime.utcnow().timestamp()}"
            product_data = {
                "external_id": external_id,
                "title": "Test Product",
                "category": "test",
            }
            
            created_product = await create_product(session, product_data)
            
            # Retrieve the product
            retrieved_product = await get_product_by_external_id(session, external_id)
            
            assert retrieved_product is not None
            assert retrieved_product.id == created_product.id
            assert retrieved_product.external_id == external_id
    
    @pytest.mark.asyncio
    async def test_get_products_pagination(self):
        """Test getting products with pagination."""
        async with get_session() as session:
            products = await get_products(session, skip=0, limit=5)
            
            assert isinstance(products, list)
            assert len(products) <= 5
    
    @pytest.mark.asyncio
    async def test_update_product(self):
        """Test updating a product."""
        async with get_session() as session:
            # Create a test product
            external_id = f"test_prod_{datetime.utcnow().timestamp()}"
            product_data = {
                "external_id": external_id,
                "title": "Original Title",
                "price": 99.99,
            }
            
            product = await create_product(session, product_data)
            
            # Update the product
            updated_data = {
                "title": "Updated Title",
                "price": 149.99,
            }
            
            updated_product = await update_product(session, product.id, updated_data)
            
            assert updated_product is not None
            assert updated_product.title == "Updated Title"
            assert float(updated_product.price) == updated_data["price"]
    
    @pytest.mark.asyncio
    async def test_delete_product(self):
        """Test deleting a product."""
        async with get_session() as session:
            # Create a test product
            external_id = f"test_prod_{datetime.utcnow().timestamp()}"
            product_data = {
                "external_id": external_id,
                "title": "Product to Delete",
            }
            
            product = await create_product(session, product_data)
            product_id = product.id
            
            # Delete the product
            success = await delete_product(session, product_id)
            
            assert success is True
            
            # Verify deletion
            deleted_product = await get_product_by_id(session, product_id)
            assert deleted_product is None
    
    @pytest.mark.asyncio
    async def test_log_search(self):
        """Test logging a search query."""
        async with get_session() as session:
            log_data = {
                "query_type": "image",
                "product_id": "test_prod_001",
                "similarity_score": 0.95,
                "results_count": 10,
                "search_time_ms": 150,
            }
            
            search_log = await log_search(session, log_data)
            
            assert search_log.id is not None
            assert search_log.query_type == "image"
            assert search_log.similarity_score == 0.95
            assert search_log.results_count == 10


class TestQdrant:
    """Test Qdrant vector database operations."""
    
    @pytest.fixture
    async def qdrant_manager(self):
        """Create QdrantManager instance for testing."""
        manager = QdrantManager(collection_name="test_collection")
        # Clean up before each test
        if await manager.collection_exists():
            await manager.delete_collection()
        yield manager
        # Clean up after test
        if await manager.collection_exists():
            await manager.delete_collection()
    
    @pytest.mark.asyncio
    async def test_create_collection(self, qdrant_manager):
        """Test creating a collection."""
        success = await qdrant_manager.create_collection(vector_size=512, distance="Cosine")
        
        assert success is True
        assert await qdrant_manager.collection_exists() is True
    
    @pytest.mark.asyncio
    async def test_upsert_and_search_vectors(self, qdrant_manager):
        """Test upserting and searching vectors."""
        # Create collection with correct dimension
        await qdrant_manager.create_collection(vector_size=128, distance="Cosine")
        
        # Create test vectors
        product_ids = ["test_001", "test_002", "test_003"]
        vectors = [
            [0.1] * 128,
            [0.5] * 128,
            [0.9] * 128,
        ]
        payloads = [
            {"title": "Product 1", "category": "test"},
            {"title": "Product 2", "category": "test"},
            {"title": "Product 3", "category": "test"},
        ]
        
        # Upsert vectors
        success = await qdrant_manager.upsert_vectors(product_ids, vectors, payloads)
        assert success is True
        
        # Search for similar vectors
        query_vector = [0.1] * 128
        results = await qdrant_manager.search_similar(
            query_vector=query_vector,
            top_k=3,
            score_threshold=0.0
        )
        
        assert len(results) > 0
        assert "id" in results[0]
        assert "score" in results[0]
        assert "payload" in results[0]
    
    @pytest.mark.asyncio
    async def test_delete_vectors(self, qdrant_manager):
        """Test deleting vectors."""
        # Create collection with correct dimension
        await qdrant_manager.create_collection(vector_size=128, distance="Cosine")
        
        # Add test vectors
        product_ids = ["test_delete_001", "test_delete_002"]
        vectors = [[0.1] * 128, [0.2] * 128]
        
        await qdrant_manager.upsert_vectors(product_ids, vectors)
        
        # Delete vectors
        success = await qdrant_manager.delete_vectors(["test_delete_001"])
        assert success is True
    
    @pytest.mark.asyncio
    async def test_get_collection_info(self, qdrant_manager):
        """Test getting collection information."""
        # Ensure collection exists
        await qdrant_manager.create_collection(vector_size=512, distance="Cosine")
        
        info = await qdrant_manager.get_collection_info()
        
        assert "name" in info
        assert "vectors_count" in info
        assert "vector_size" in info
        assert info["vector_size"] == 512
    
    @pytest.mark.asyncio
    async def test_count_vectors(self, qdrant_manager):
        """Test counting vectors in collection."""
        # Ensure collection exists
        await qdrant_manager.create_collection(vector_size=128, distance="Cosine")
        
        count = await qdrant_manager.count_vectors()
        
        assert isinstance(count, int)
        assert count >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

