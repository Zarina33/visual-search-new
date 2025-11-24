"""
Quick test to demonstrate CLIPEmbedder with GPU acceleration.
"""
import asyncio
import time
import numpy as np
from pathlib import Path

from app.models.clip_model import CLIPEmbedder


async def test_gpu_performance():
    """Test CLIP embedder with GPU."""
    print("=" * 70)
    print("CLIP Embedder GPU Test")
    print("=" * 70)
    
    # Initialize with auto device selection (will use GPU if available)
    print("\n1. Initializing CLIPEmbedder with auto device...")
    embedder = CLIPEmbedder(device="auto")
    
    print(f"   ✓ Device: {embedder.device}")
    print(f"   ✓ Model: {embedder.model_name}")
    print(f"   ✓ Embedding dimension: {embedder.get_embedding_dimension()}")
    
    # Test text encoding
    print("\n2. Testing text encoding...")
    start = time.time()
    
    texts = [
        "красная спортивная машина",
        "синий диван",
        "деревянный стол",
        "белый холодильник",
        "черный телефон"
    ]
    
    text_embeddings = embedder.encode_text(texts)
    elapsed = time.time() - start
    
    print(f"   ✓ Encoded {len(texts)} texts in {elapsed:.3f}s")
    print(f"   ✓ Embeddings shape: {text_embeddings.shape}")
    
    # Check normalization
    norms = [np.linalg.norm(emb) for emb in text_embeddings]
    print(f"   ✓ L2 norms (should be ~1.0): {[f'{n:.4f}' for n in norms]}")
    
    # Test similarity between texts
    print("\n3. Testing text similarity...")
    query = "автомобиль"
    query_emb = embedder.encode_text(query)
    
    print(f"   Query: '{query}'")
    print("   Similarities:")
    
    for i, text in enumerate(texts):
        sim = embedder.compute_similarity(query_emb, text_embeddings[i])
        print(f"      - '{text}': {sim:.4f}")
    
    # Test with sample images if available
    print("\n4. Testing image encoding...")
    
    # Check if sample images exist
    sample_images_dir = Path("../clip/images")
    if sample_images_dir.exists():
        image_paths = list(sample_images_dir.glob("*.jpeg"))[:5]
        
        if image_paths:
            print(f"   Found {len(image_paths)} sample images")
            
            start = time.time()
            image_embeddings = await embedder.generate_embeddings_batch(
                [str(p) for p in image_paths],
                batch_size=32,
                show_progress=False
            )
            elapsed = time.time() - start
            
            successful = sum(1 for emb in image_embeddings if emb is not None)
            print(f"   ✓ Processed {successful}/{len(image_paths)} images in {elapsed:.3f}s")
            print(f"   ✓ Speed: {successful/elapsed:.2f} images/sec")
            
            # Test image-text similarity
            if successful > 0:
                print("\n5. Testing image-text similarity...")
                test_queries = ["машина", "диван", "стол"]
                
                for query in test_queries:
                    query_emb = embedder.encode_text(query)
                    
                    similarities = []
                    for i, img_emb in enumerate(image_embeddings):
                        if img_emb is not None:
                            sim = embedder.compute_similarity(query_emb, img_emb)
                            similarities.append((image_paths[i].name, sim))
                    
                    # Sort by similarity
                    similarities.sort(key=lambda x: x[1], reverse=True)
                    
                    print(f"\n   Query: '{query}'")
                    print(f"   Top 3 matches:")
                    for name, sim in similarities[:3]:
                        print(f"      - {name}: {sim:.4f}")
        else:
            print("   No sample images found in ../clip/images/")
    else:
        print("   Sample images directory not found")
    
    print("\n" + "=" * 70)
    print("✓ All tests completed successfully!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(test_gpu_performance())

