"""
Search endpoints for visual and text search.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Query, Body, Path
from fastapi.responses import JSONResponse
from typing import Optional, List
from PIL import Image
import tempfile
import time
from pathlib import Path as FilePath
import io
from loguru import logger

from app.schemas.search import SearchResponse, SearchResult, TextSearchRequest
from app.models.clip_model import CLIPEmbedder
from app.db.qdrant import QdrantManager
from app.db.postgres import get_session, get_product_by_external_id
from app.config import settings
from app.utils.metrics import record_search, record_clip_inference, record_qdrant_search

router = APIRouter(prefix="/api/v1/search", tags=["search"])

# Глобальные инстансы (инициализируются при старте приложения)
clip_embedder: Optional[CLIPEmbedder] = None
qdrant_manager: Optional[QdrantManager] = None

# Максимальный размер файла (10MB)
MAX_FILE_SIZE = 10 * 1024 * 1024


def get_clip_embedder() -> CLIPEmbedder:
    """Get CLIP embedder instance."""
    global clip_embedder
    if clip_embedder is None:
        raise HTTPException(
            status_code=503,
            detail="CLIP embedder not initialized. Please restart the application."
        )
    return clip_embedder


def get_qdrant_manager() -> QdrantManager:
    """Get Qdrant manager instance."""
    global qdrant_manager
    if qdrant_manager is None:
        raise HTTPException(
            status_code=503,
            detail="Qdrant manager not initialized. Please restart the application."
        )
    return qdrant_manager


@router.post("/by-text", response_model=SearchResponse)
async def search_by_text(
    request: TextSearchRequest = Body(..., description="Text search request")
) -> SearchResponse:
    """
    Search products by text query.
    
    Generates text embedding using CLIP and searches for similar products in Qdrant.
    
    Args:
        request: Text search request with query, limit, and min_similarity
        
    Returns:
        Search results with product information and similarity scores
        
    Raises:
        HTTPException: If search fails
    """
    start_time = time.time()
    
    try:
        logger.info(f"Text search: '{request.query}' (limit={request.limit}, min_sim={request.min_similarity})")
        
        # 1. Генерировать текстовый эмбеддинг через CLIP
        embedder = get_clip_embedder()
        
        clip_start = time.time()
        query_embedding = embedder.encode_text(request.query)
        clip_duration = time.time() - clip_start
        record_clip_inference(clip_duration)
        
        # 2. Искать похожие векторы в Qdrant
        qdrant = get_qdrant_manager()
        
        qdrant_start = time.time()
        vector_results = await qdrant.search_similar(
            query_vector=query_embedding.tolist(),
            top_k=request.limit,
            score_threshold=request.min_similarity
        )
        qdrant_duration = time.time() - qdrant_start
        record_qdrant_search(qdrant_duration)
        
        # 3. Получить метаданные из PostgreSQL
        results = []
        async with get_session() as session:
            for vector_result in vector_results:
                product_id = vector_result["id"]
                
                # Получить продукт из PostgreSQL
                product = await get_product_by_external_id(session, product_id)
                
                if product:
                    results.append(
                        SearchResult(
                            product_id=str(product.id),
                            external_id=product.external_id,
                            title=product.title,
                            description=product.description,
                            category=product.category,
                            price=product.price,
                            currency=product.currency,
                            image_url=product.image_url,
                            similarity_score=vector_result["score"]
                        )
                    )
        
        query_time_ms = int((time.time() - start_time) * 1000)
        
        # Record metrics
        record_search("by-text", time.time() - start_time, success=True)
        
        logger.info(f"Text search completed: {len(results)} results in {query_time_ms}ms")
        
        return SearchResponse(
            query_time_ms=query_time_ms,
            results_count=len(results),
            results=results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Record failed search
        record_search("by-text", time.time() - start_time, success=False)
        logger.error(f"Text search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/by-image", response_model=SearchResponse)
async def search_by_image(
    image: UploadFile = File(..., description="Query image file"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of results"),
    min_similarity: float = Query(default=0.0, ge=0.0, le=1.0, description="Minimum similarity threshold")
) -> SearchResponse:
    """
    Search products by uploaded image.
    
    Accepts an image file, generates embedding using CLIP, and searches for similar products.
    
    Args:
        image: Uploaded image file (JPEG, PNG, etc.)
        limit: Maximum number of results to return
        min_similarity: Minimum similarity threshold (0.0-1.0)
        
    Returns:
        Search results with product information and similarity scores
        
    Raises:
        HTTPException: If image is invalid or search fails
    """
    start_time = time.time()
    temp_file = None
    
    try:
        logger.info(f"Image search: {image.filename} (limit={limit}, min_sim={min_similarity})")
        
        # Валидация формата
        if not image.content_type or not image.content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {image.content_type}. Must be an image."
            )
        
        # Чтение файла
        image_data = await image.read()
        
        # Валидация размера
        if len(image_data) > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {len(image_data)} bytes. Maximum: {MAX_FILE_SIZE} bytes (10MB)"
            )
        
        # 1. Сохранить временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
            temp_file.write(image_data)
            temp_file_path = temp_file.name
        
        # 2. Генерировать эмбеддинг через CLIP
        embedder = get_clip_embedder()
        
        clip_start = time.time()
        embedding = await embedder.generate_embedding(temp_file_path)
        clip_duration = time.time() - clip_start
        record_clip_inference(clip_duration)
        
        if embedding is None:
            raise HTTPException(
                status_code=400,
                detail="Failed to generate embedding. Image may be corrupted."
            )
        
        # 3. Искать похожие векторы в Qdrant
        qdrant = get_qdrant_manager()
        
        qdrant_start = time.time()
        vector_results = await qdrant.search_similar(
            query_vector=embedding.tolist(),
            top_k=limit,
            score_threshold=min_similarity
        )
        qdrant_duration = time.time() - qdrant_start
        record_qdrant_search(qdrant_duration)
        
        # 4. Получить метаданные из PostgreSQL
        results = []
        async with get_session() as session:
            for vector_result in vector_results:
                product_id = vector_result["id"]
                
                # Получить продукт из PostgreSQL
                product = await get_product_by_external_id(session, product_id)
                
                if product:
                    results.append(
                        SearchResult(
                            product_id=str(product.id),
                            external_id=product.external_id,
                            title=product.title,
                            description=product.description,
                            category=product.category,
                            price=product.price,
                            currency=product.currency,
                            image_url=product.image_url,
                            similarity_score=vector_result["score"]
                        )
                    )
        
        query_time_ms = int((time.time() - start_time) * 1000)
        
        # Record metrics
        record_search("by-image", time.time() - start_time, success=True)
        
        logger.info(f"Image search completed: {len(results)} results in {query_time_ms}ms")
        
        return SearchResponse(
            query_time_ms=query_time_ms,
            results_count=len(results),
            results=results
        )
        
    except HTTPException:
        raise
    except Exception as e:
        # Record failed search
        record_search("by-image", time.time() - start_time, success=False)
        logger.error(f"Image search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
    finally:
        # 5. Удаление временного файла
        if temp_file and FilePath(temp_file_path).exists():
            try:
                FilePath(temp_file_path).unlink()
                logger.debug(f"Temporary file deleted: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {e}")


@router.get("/similar/{product_id}", response_model=SearchResponse)
async def search_similar_products(
    product_id: str = Path(..., description="Product external ID"),
    limit: int = Query(default=10, ge=1, le=50, description="Maximum number of results")
) -> SearchResponse:
    """
    Find similar products to a given product.
    
    Retrieves the product's vector from Qdrant and searches for similar products.
    
    Args:
        product_id: External product ID
        limit: Maximum number of results to return
        
    Returns:
        Search results with similar products
        
    Raises:
        HTTPException: If product not found or search fails
    """
    start_time = time.time()
    
    try:
        logger.info(f"Similar products search: {product_id} (limit={limit})")
        
        # 1. Получить продукт и его эмбеддинг
        qdrant = get_qdrant_manager()
        
        async with get_session() as session:
            product = await get_product_by_external_id(session, product_id)
            
            if not product:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product not found: {product_id}"
                )
            
            # Получить изображение и сгенерировать эмбеддинг
            if product.image_url and product.image_url.startswith("file://"):
                image_path = product.image_url.replace("file://", "")
                
                embedder = get_clip_embedder()
                
                clip_start = time.time()
                embedding = await embedder.generate_embedding(image_path)
                clip_duration = time.time() - clip_start
                record_clip_inference(clip_duration)
                
                if embedding is None:
                    raise HTTPException(
                        status_code=500,
                        detail="Failed to generate embedding for product image"
                    )
                
                # 2. Искать похожие
                qdrant_start = time.time()
                vector_results = await qdrant.search_similar(
                    query_vector=embedding.tolist(),
                    top_k=limit + 1,
                    score_threshold=0.0
                )
                qdrant_duration = time.time() - qdrant_start
                record_qdrant_search(qdrant_duration)
                
                # 3. Получить метаданные из PostgreSQL (исключая сам товар)
                results = []
                for vector_result in vector_results:
                    result_product_id = vector_result["id"]
                    
                    # Пропустить сам товар
                    if result_product_id == product_id:
                        continue
                    
                    similar_product = await get_product_by_external_id(session, result_product_id)
                    
                    if similar_product:
                        results.append(
                            SearchResult(
                                product_id=str(similar_product.id),
                                external_id=similar_product.external_id,
                                title=similar_product.title,
                                description=similar_product.description,
                                category=similar_product.category,
                                price=similar_product.price,
                                currency=similar_product.currency,
                                image_url=similar_product.image_url,
                                similarity_score=vector_result["score"]
                            )
                        )
                    
                    if len(results) >= limit:
                        break
                
                query_time_ms = int((time.time() - start_time) * 1000)
                
                # Record metrics
                record_search("similar", time.time() - start_time, success=True)
                
                logger.info(f"Similar products search completed: {len(results)} results in {query_time_ms}ms")
                
                return SearchResponse(
                    query_time_ms=query_time_ms,
                    results_count=len(results),
                    results=results
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Product has no valid image URL"
                )
        
    except HTTPException:
        raise
    except Exception as e:
        # Record failed search
        record_search("similar", time.time() - start_time, success=False)
        logger.error(f"Similar products search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
