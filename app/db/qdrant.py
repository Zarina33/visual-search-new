"""
Qdrant vector database module with async support.
"""
from typing import Optional
from uuid import uuid5, NAMESPACE_DNS
from loguru import logger

from qdrant_client import QdrantClient as QdrantClientSDK
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)

from app.config import settings


def _product_id_to_uuid(product_id: str) -> str:
    """
    Convert product_id string to UUID string.
    
    Args:
        product_id: Product external ID
        
    Returns:
        UUID string
    """
    return str(uuid5(NAMESPACE_DNS, product_id))


class QdrantManager:
    """
    Manager class for Qdrant vector database operations.
    
    Handles vector storage, search, and collection management for product embeddings.
    """
    
    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        collection_name: Optional[str] = None
    ):
        """
        Initialize Qdrant manager.
        
        Args:
            host: Qdrant server host (defaults to settings)
            port: Qdrant server port (defaults to settings)
            collection_name: Name of the collection (defaults to settings)
        """
        self.host = host or settings.qdrant_host
        self.port = port or settings.qdrant_port
        self.collection_name = collection_name or settings.qdrant_collection_name
        
        try:
            self.client = QdrantClientSDK(host=self.host, port=self.port)
            logger.info(f"✅ Connected to Qdrant: {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"❌ Failed to connect to Qdrant: {e}")
            raise
    
    async def create_collection(
        self,
        vector_size: int = 512,
        distance: str = "Cosine"
    ) -> bool:
        """
        Create collection if it doesn't exist.
        
        Args:
            vector_size: Dimension of the vectors (default: 512 for CLIP)
            distance: Distance metric - "Cosine", "Euclidean", or "Dot"
            
        Returns:
            True if collection was created or already exists
            
        Raises:
            Exception: If collection creation fails
        """
        try:
            # Check if collection already exists
            if await self.collection_exists():
                logger.info(f"Collection '{self.collection_name}' already exists")
                return True
            
            # Map distance string to Distance enum
            distance_map = {
                "Cosine": Distance.COSINE,
                "Euclidean": Distance.EUCLID,
                "Dot": Distance.DOT,
            }
            
            if distance not in distance_map:
                raise ValueError(f"Invalid distance metric: {distance}. Use 'Cosine', 'Euclidean', or 'Dot'")
            
            # Create collection
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=distance_map[distance]
                )
            )
            
            logger.info(f"✅ Created collection '{self.collection_name}' with vector_size={vector_size}, distance={distance}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to create collection '{self.collection_name}': {e}")
            raise
    
    async def collection_exists(self) -> bool:
        """
        Check if collection exists.
        
        Returns:
            True if collection exists, False otherwise
        """
        try:
            collections = self.client.get_collections().collections
            exists = any(col.name == self.collection_name for col in collections)
            logger.debug(f"Collection '{self.collection_name}' exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"❌ Failed to check collection existence: {e}")
            raise
    
    async def upsert_vectors(
        self,
        product_ids: list[str],
        vectors: list[list[float]],
        payloads: Optional[list[dict]] = None
    ) -> bool:
        """
        Add or update vectors in the collection.
        
        Args:
            product_ids: List of unique product IDs (external_id)
            vectors: List of embedding vectors
            payloads: Optional list of metadata dictionaries for each vector
            
        Returns:
            True if operation was successful
            
        Raises:
            ValueError: If input lists have different lengths
            Exception: If upsert operation fails
        """
        try:
            # Validate input
            if len(product_ids) != len(vectors):
                raise ValueError(f"Length mismatch: {len(product_ids)} product_ids vs {len(vectors)} vectors")
            
            if payloads is not None and len(payloads) != len(vectors):
                raise ValueError(f"Length mismatch: {len(payloads)} payloads vs {len(vectors)} vectors")
            
            # Create default payloads if not provided
            if payloads is None:
                payloads = [{"product_id": pid} for pid in product_ids]
            else:
                # Ensure product_id is in payload
                for i, payload in enumerate(payloads):
                    if "product_id" not in payload:
                        payload["product_id"] = product_ids[i]
            
            # Create points with UUID
            points = [
                PointStruct(
                    id=_product_id_to_uuid(product_id),
                    vector=vector,
                    payload=payload
                )
                for product_id, vector, payload in zip(product_ids, vectors, payloads)
            ]
            
            # Upsert to Qdrant
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
            
            logger.info(f"✅ Upserted {len(points)} vectors to collection '{self.collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to upsert vectors: {e}")
            raise
    
    async def delete_vectors(self, product_ids: list[str]) -> bool:
        """
        Delete vectors by product IDs.
        
        Args:
            product_ids: List of product IDs to delete
            
        Returns:
            True if operation was successful
            
        Raises:
            Exception: If delete operation fails
        """
        try:
            if not product_ids:
                logger.warning("No product IDs provided for deletion")
                return True
            
            # Convert product IDs to UUIDs
            uuids = [_product_id_to_uuid(pid) for pid in product_ids]
            
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=uuids
            )
            
            logger.info(f"✅ Deleted {len(product_ids)} vectors from collection '{self.collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete vectors: {e}")
            raise
    
    async def search_similar(
        self,
        query_vector: list[float],
        top_k: int = 10,
        score_threshold: float = 0.0
    ) -> list[dict]:
        """
        Search for similar vectors.
        
        Args:
            query_vector: Query embedding vector
            top_k: Number of top results to return
            score_threshold: Minimum similarity score (0.0 to 1.0)
            
        Returns:
            List of dictionaries with format:
            [
                {
                    "id": "prod_001",
                    "score": 0.95,
                    "payload": {"product_id": "prod_001", ...}
                },
                ...
            ]
            
        Raises:
            Exception: If search operation fails
        """
        try:
            # Perform search
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                score_threshold=score_threshold
            )
            
            # Format results - return product_id from payload
            results = [
                {
                    "id": result.payload.get("product_id", str(result.id)),
                    "score": float(result.score),
                    "payload": result.payload
                }
                for result in search_results
            ]
            
            logger.info(f"✅ Found {len(results)} similar vectors (top_k={top_k}, threshold={score_threshold})")
            return results
            
        except Exception as e:
            logger.error(f"❌ Failed to search similar vectors: {e}")
            raise
    
    async def get_collection_info(self) -> dict:
        """
        Get information about the collection.
        
        Returns:
            Dictionary with collection information:
            {
                "name": "product_embeddings",
                "vectors_count": 1000,
                "points_count": 1000,
                "status": "green",
                "vector_size": 512,
                "distance": "Cosine"
            }
            
        Raises:
            Exception: If collection doesn't exist or operation fails
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            
            info = {
                "name": self.collection_name,
                "vectors_count": collection_info.vectors_count or 0,
                "points_count": collection_info.points_count,
                "status": collection_info.status,
                "vector_size": collection_info.config.params.vectors.size,
                "distance": collection_info.config.params.vectors.distance.name
            }
            
            logger.debug(f"Collection info: {info}")
            return info
            
        except Exception as e:
            logger.error(f"❌ Failed to get collection info: {e}")
            raise
    
    async def count_vectors(self) -> int:
        """
        Get the number of vectors in the collection.
        
        Returns:
            Number of vectors in the collection
            
        Raises:
            Exception: If collection doesn't exist or operation fails
        """
        try:
            collection_info = self.client.get_collection(self.collection_name)
            count = collection_info.points_count
            logger.debug(f"Collection '{self.collection_name}' has {count} vectors")
            return count
        except Exception as e:
            logger.error(f"❌ Failed to count vectors: {e}")
            raise
    
    async def delete_collection(self) -> bool:
        """
        Delete the entire collection.
        
        Warning: This operation cannot be undone!
        
        Returns:
            True if collection was deleted
            
        Raises:
            Exception: If delete operation fails
        """
        try:
            if not await self.collection_exists():
                logger.warning(f"Collection '{self.collection_name}' does not exist")
                return True
            
            self.client.delete_collection(self.collection_name)
            logger.warning(f"⚠️  Deleted collection '{self.collection_name}'")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to delete collection: {e}")
            raise
    
    def close(self) -> None:
        """
        Close the Qdrant client connection.
        """
        try:
            if hasattr(self, 'client') and self.client:
                self.client.close()
                logger.info("Qdrant client connection closed")
        except Exception as e:
            logger.error(f"Error closing Qdrant client: {e}")
