"""
Celery tasks for background processing.
"""
import logging
from typing import List, Dict, Any
from PIL import Image
import requests
from io import BytesIO

from app.workers.celery_app import celery_app
from app.models.clip_model import CLIPModel
from app.db.qdrant import QdrantClient
from app.db.postgres import PostgresClient
from app.utils.image_processing import download_image, process_image

logger = logging.getLogger(__name__)


@celery_app.task(name="index_product", bind=True, max_retries=3)
def index_product(self, product_id: str, image_url: str) -> Dict[str, Any]:
    """
    Index a product image in the vector database.
    
    Args:
        product_id: Product external ID
        image_url: URL of the product image
        
    Returns:
        Task result with status
    """
    try:
        logger.info(f"Indexing product {product_id} with image {image_url}")
        
        # Download and process image
        image = download_image(image_url)
        processed_image = process_image(image)
        
        # Generate embedding
        clip_model = CLIPModel()
        embedding = clip_model.encode_image(processed_image)
        
        # Store in Qdrant
        qdrant_client = QdrantClient()
        qdrant_client.add_vectors(
            vectors=[embedding],
            ids=[product_id],
            payloads=[{"product_id": product_id, "image_url": image_url}],
        )
        
        logger.info(f"Successfully indexed product {product_id}")
        
        return {
            "status": "success",
            "product_id": product_id,
            "message": "Product indexed successfully",
        }
        
    except Exception as e:
        logger.error(f"Failed to index product {product_id}: {str(e)}")
        
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=2 ** self.request.retries)


@celery_app.task(name="batch_index_products", bind=True)
def batch_index_products(self, products: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Batch index multiple products.
    
    Args:
        products: List of dicts with product_id and image_url
        
    Returns:
        Task result with statistics
    """
    try:
        logger.info(f"Batch indexing {len(products)} products")
        
        clip_model = CLIPModel()
        qdrant_client = QdrantClient()
        
        vectors = []
        ids = []
        payloads = []
        
        successful = 0
        failed = 0
        
        for product in products:
            try:
                product_id = product["product_id"]
                image_url = product["image_url"]
                
                # Download and process image
                image = download_image(image_url)
                processed_image = process_image(image)
                
                # Generate embedding
                embedding = clip_model.encode_image(processed_image)
                
                vectors.append(embedding)
                ids.append(product_id)
                payloads.append({"product_id": product_id, "image_url": image_url})
                
                successful += 1
                
            except Exception as e:
                logger.error(f"Failed to process product {product.get('product_id')}: {str(e)}")
                failed += 1
        
        # Batch insert into Qdrant
        if vectors:
            qdrant_client.add_vectors(vectors=vectors, ids=ids, payloads=payloads)
        
        logger.info(f"Batch indexing complete: {successful} successful, {failed} failed")
        
        return {
            "status": "success",
            "total": len(products),
            "successful": successful,
            "failed": failed,
        }
        
    except Exception as e:
        logger.error(f"Batch indexing failed: {str(e)}")
        raise


@celery_app.task(name="reindex_all_products")
def reindex_all_products() -> Dict[str, Any]:
    """
    Reindex all products from the database.
    
    Returns:
        Task result with statistics
    """
    try:
        logger.info("Starting full reindex of all products")
        
        # Get all products from PostgreSQL
        pg_client = PostgresClient()
        products = pg_client.fetch_all(
            "SELECT external_id, image_url FROM products WHERE image_url IS NOT NULL"
        )
        
        # Prepare batch data
        batch_data = [
            {"product_id": p["external_id"], "image_url": p["image_url"]}
            for p in products
        ]
        
        # Trigger batch indexing
        result = batch_index_products(batch_data)
        
        logger.info("Full reindex complete")
        
        return result
        
    except Exception as e:
        logger.error(f"Full reindex failed: {str(e)}")
        raise

