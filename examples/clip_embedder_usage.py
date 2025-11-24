"""
Example usage of the optimized CLIPEmbedder.

This script demonstrates how to use the CLIPEmbedder class for:
1. Single image embedding generation
2. Batch image embedding generation
3. Text encoding
4. Similarity computation
"""
import asyncio
from pathlib import Path

import numpy as np
from loguru import logger

from app.models.clip_model import CLIPEmbedder


async def example_single_image():
    """Example: Generate embedding for a single image."""
    logger.info("=" * 60)
    logger.info("Example 1: Single Image Embedding")
    logger.info("=" * 60)
    
    # Initialize embedder with auto device selection
    embedder = CLIPEmbedder(device="auto")
    
    # Generate embedding for a single image
    image_path = "path/to/your/image.jpg"
    
    try:
        embedding = await embedder.generate_embedding(image_path)
        
        if embedding is not None:
            logger.success(f"Generated embedding: shape={embedding.shape}")
            logger.info(f"Embedding norm: {np.linalg.norm(embedding):.4f}")
            logger.info(f"First 5 values: {embedding[:5]}")
    except FileNotFoundError:
        logger.warning(f"Image not found: {image_path}")


async def example_batch_images():
    """Example: Generate embeddings for multiple images."""
    logger.info("=" * 60)
    logger.info("Example 2: Batch Image Embeddings")
    logger.info("=" * 60)
    
    # Initialize embedder
    embedder = CLIPEmbedder(device="auto")
    
    # List of image paths
    image_paths = [
        "path/to/image1.jpg",
        "path/to/image2.jpg",
        "path/to/image3.jpg",
    ]
    
    # Generate embeddings in batch
    embeddings = await embedder.generate_embeddings_batch(
        image_paths,
        batch_size=32,
        show_progress=True
    )
    
    # Check results
    successful = sum(1 for emb in embeddings if emb is not None)
    logger.success(f"Successfully generated {successful}/{len(embeddings)} embeddings")
    
    # Process embeddings
    for i, embedding in enumerate(embeddings):
        if embedding is not None:
            logger.info(f"Image {i}: shape={embedding.shape}, norm={np.linalg.norm(embedding):.4f}")


def example_text_encoding():
    """Example: Encode text to embeddings."""
    logger.info("=" * 60)
    logger.info("Example 3: Text Encoding")
    logger.info("=" * 60)
    
    # Initialize embedder
    embedder = CLIPEmbedder(device="auto")
    
    # Single text
    text = "a red sports car"
    embedding = embedder.encode_text(text)
    logger.success(f"Single text embedding: shape={embedding.shape}")
    
    # Multiple texts
    texts = [
        "a red sports car",
        "a blue sofa",
        "a wooden dining table",
    ]
    embeddings = embedder.encode_text(texts)
    logger.success(f"Batch text embeddings: shape={embeddings.shape}")
    
    # Check normalization
    for i, emb in enumerate(embeddings):
        norm = np.linalg.norm(emb)
        logger.info(f"Text {i} '{texts[i]}': norm={norm:.4f}")


async def example_similarity_search():
    """Example: Search for similar images using text query."""
    logger.info("=" * 60)
    logger.info("Example 4: Similarity Search")
    logger.info("=" * 60)
    
    # Initialize embedder
    embedder = CLIPEmbedder(device="auto")
    
    # Generate embeddings for a collection of images
    image_paths = [
        "path/to/car.jpg",
        "path/to/sofa.jpg",
        "path/to/table.jpg",
    ]
    
    image_labels = ["car", "sofa", "table"]
    
    logger.info("Generating image embeddings...")
    image_embeddings = await embedder.generate_embeddings_batch(
        image_paths,
        batch_size=32,
        show_progress=False
    )
    
    # Text query
    query = "a vehicle for transportation"
    logger.info(f"Query: '{query}'")
    
    query_embedding = embedder.encode_text(query)
    
    # Compute similarities
    similarities = []
    for i, img_emb in enumerate(image_embeddings):
        if img_emb is not None:
            similarity = embedder.compute_similarity(query_embedding, img_emb)
            similarities.append((image_labels[i], similarity))
    
    # Sort by similarity
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    # Display results
    logger.success("Search results (sorted by similarity):")
    for label, sim in similarities:
        logger.info(f"  {label}: {sim:.4f}")


async def example_image_to_image_similarity():
    """Example: Find similar images."""
    logger.info("=" * 60)
    logger.info("Example 5: Image-to-Image Similarity")
    logger.info("=" * 60)
    
    # Initialize embedder
    embedder = CLIPEmbedder(device="auto")
    
    # Query image
    query_image = "path/to/query_image.jpg"
    
    # Database images
    database_images = [
        "path/to/image1.jpg",
        "path/to/image2.jpg",
        "path/to/image3.jpg",
    ]
    
    try:
        # Generate embedding for query image
        logger.info("Generating query image embedding...")
        query_embedding = await embedder.generate_embedding(query_image)
        
        if query_embedding is None:
            logger.error("Failed to generate query embedding")
            return
        
        # Generate embeddings for database images
        logger.info("Generating database image embeddings...")
        db_embeddings = await embedder.generate_embeddings_batch(
            database_images,
            batch_size=32,
            show_progress=False
        )
        
        # Compute similarities
        similarities = []
        for i, db_emb in enumerate(db_embeddings):
            if db_emb is not None:
                similarity = embedder.compute_similarity(query_embedding, db_emb)
                similarities.append((database_images[i], similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Display results
        logger.success("Most similar images:")
        for img_path, sim in similarities:
            logger.info(f"  {Path(img_path).name}: {sim:.4f}")
            
    except FileNotFoundError as e:
        logger.warning(f"Image not found: {e}")


def example_get_embedding_dimension():
    """Example: Get embedding dimension."""
    logger.info("=" * 60)
    logger.info("Example 6: Get Embedding Dimension")
    logger.info("=" * 60)
    
    # Initialize embedder
    embedder = CLIPEmbedder(device="auto")
    
    # Get embedding dimension
    dim = embedder.get_embedding_dimension()
    logger.success(f"Embedding dimension: {dim}")
    
    # This is useful for initializing vector databases
    logger.info(f"Use this dimension when creating Qdrant collection: {dim}")


async def main():
    """Run all examples."""
    logger.info("CLIPEmbedder Usage Examples")
    logger.info("=" * 60)
    
    # Run examples
    await example_single_image()
    print()
    
    await example_batch_images()
    print()
    
    example_text_encoding()
    print()
    
    await example_similarity_search()
    print()
    
    await example_image_to_image_similarity()
    print()
    
    example_get_embedding_dimension()
    print()
    
    logger.success("All examples completed!")


if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        lambda msg: print(msg, end=""),
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level="INFO"
    )
    
    # Run examples
    asyncio.run(main())

