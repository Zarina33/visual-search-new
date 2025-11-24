# CLIP Model Module

Optimized CLIP (Contrastive Language-Image Pre-training) model wrapper for efficient image and text embedding generation.

## Features

- ✅ **Automatic GPU Detection**: Automatically uses GPU if available, falls back to CPU
- ✅ **Async Support**: All image operations are async for better performance
- ✅ **Batch Processing**: Efficient batch processing with configurable batch size
- ✅ **L2 Normalization**: All embeddings are L2 normalized for cosine similarity
- ✅ **Error Handling**: Graceful handling of corrupted/missing files
- ✅ **Progress Tracking**: Built-in progress bars for batch operations
- ✅ **Memory Efficient**: Uses `torch.no_grad()` for inference
- ✅ **Logging**: Comprehensive logging with loguru
- ✅ **Graceful Shutdown**: Automatic cleanup of resources

## Installation

```bash
# Install dependencies
poetry install

# Or with pip
pip install torch transformers pillow numpy loguru tqdm
```

## Quick Start

### Initialize the Embedder

```python
from app.models.clip_model import CLIPEmbedder

# Auto device selection (GPU if available, else CPU)
embedder = CLIPEmbedder(device="auto")

# Force CPU
embedder = CLIPEmbedder(device="cpu")

# Force GPU
embedder = CLIPEmbedder(device="cuda")

# Custom model
embedder = CLIPEmbedder(
    model_name="openai/clip-vit-large-patch14",
    device="auto"
)
```

### Single Image Embedding

```python
import asyncio

async def generate_single():
    embedder = CLIPEmbedder(device="auto")
    
    # Generate embedding for a single image
    embedding = await embedder.generate_embedding("path/to/image.jpg")
    
    print(f"Shape: {embedding.shape}")  # (512,)
    print(f"Norm: {np.linalg.norm(embedding)}")  # ~1.0 (L2 normalized)

asyncio.run(generate_single())
```

### Batch Image Embeddings

```python
import asyncio

async def generate_batch():
    embedder = CLIPEmbedder(device="auto")
    
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
    
    # Process results
    for i, emb in enumerate(embeddings):
        if emb is not None:
            print(f"Image {i}: {emb.shape}")
        else:
            print(f"Image {i}: Failed")

asyncio.run(generate_batch())
```

### Text Encoding

```python
embedder = CLIPEmbedder(device="auto")

# Single text
text_embedding = embedder.encode_text("a red sports car")
print(text_embedding.shape)  # (512,)

# Multiple texts
texts = ["a red car", "a blue sofa", "a wooden table"]
text_embeddings = embedder.encode_text(texts)
print(text_embeddings.shape)  # (3, 512)
```

### Similarity Search

```python
import asyncio
import numpy as np

async def search_similar():
    embedder = CLIPEmbedder(device="auto")
    
    # Generate image embeddings
    image_paths = ["car.jpg", "sofa.jpg", "table.jpg"]
    image_embeddings = await embedder.generate_embeddings_batch(image_paths)
    
    # Text query
    query = "a vehicle"
    query_embedding = embedder.encode_text(query)
    
    # Compute similarities
    similarities = []
    for i, img_emb in enumerate(image_embeddings):
        if img_emb is not None:
            sim = embedder.compute_similarity(query_embedding, img_emb)
            similarities.append((image_paths[i], sim))
    
    # Sort by similarity
    similarities.sort(key=lambda x: x[1], reverse=True)
    
    # Display results
    for path, sim in similarities:
        print(f"{path}: {sim:.4f}")

asyncio.run(search_similar())
```

## API Reference

### CLIPEmbedder

Main class for CLIP model operations.

#### `__init__(model_name: str = "openai/clip-vit-base-patch32", device: str = "auto")`

Initialize the CLIP embedder.

**Parameters:**
- `model_name` (str): HuggingFace model name
- `device` (str): Device to use ('auto', 'cpu', 'cuda', 'cuda:0', etc.)

**Example:**
```python
embedder = CLIPEmbedder(
    model_name="openai/clip-vit-base-patch32",
    device="auto"
)
```

#### `async generate_embedding(image_path: str) -> Optional[np.ndarray]`

Generate normalized embedding for a single image.

**Parameters:**
- `image_path` (str): Path to image file

**Returns:**
- `np.ndarray`: Normalized embedding vector (L2 norm), or None if failed

**Raises:**
- `FileNotFoundError`: If image file doesn't exist

**Example:**
```python
embedding = await embedder.generate_embedding("image.jpg")
```

#### `async generate_embeddings_batch(image_paths: List[str], batch_size: int = 32, show_progress: bool = True) -> List[Optional[np.ndarray]]`

Generate embeddings for multiple images with batch processing.

**Parameters:**
- `image_paths` (List[str]): List of image file paths
- `batch_size` (int): Number of images to process in each batch (default: 32)
- `show_progress` (bool): Whether to show progress bar (default: True)

**Returns:**
- `List[Optional[np.ndarray]]`: List of embeddings (None for failed images)

**Example:**
```python
embeddings = await embedder.generate_embeddings_batch(
    image_paths,
    batch_size=32,
    show_progress=True
)
```

#### `encode_text(text: Union[str, List[str]]) -> np.ndarray`

Encode text(s) to normalized embedding vector(s).

**Parameters:**
- `text` (Union[str, List[str]]): String or list of strings

**Returns:**
- `np.ndarray`: Normalized embedding vector(s)

**Example:**
```python
# Single text
embedding = embedder.encode_text("a red car")

# Multiple texts
embeddings = embedder.encode_text(["a red car", "a blue sofa"])
```

#### `compute_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float`

Compute cosine similarity between two normalized embeddings.

**Parameters:**
- `embedding1` (np.ndarray): First embedding vector (normalized)
- `embedding2` (np.ndarray): Second embedding vector (normalized)

**Returns:**
- `float`: Similarity score between -1 and 1 (typically 0 to 1 for normalized vectors)

**Example:**
```python
similarity = embedder.compute_similarity(img_embedding, text_embedding)
```

#### `get_embedding_dimension() -> int`

Get the dimension of embedding vectors.

**Returns:**
- `int`: Embedding dimension (typically 512 for base CLIP model)

**Example:**
```python
dim = embedder.get_embedding_dimension()  # 512
```

## Performance Optimization

### 1. Batch Processing

Always use batch processing for multiple images:

```python
# ❌ Slow - Sequential processing
embeddings = []
for path in image_paths:
    emb = await embedder.generate_embedding(path)
    embeddings.append(emb)

# ✅ Fast - Batch processing
embeddings = await embedder.generate_embeddings_batch(image_paths, batch_size=32)
```

### 2. GPU Acceleration

Use GPU for faster processing:

```python
# Auto-detect GPU
embedder = CLIPEmbedder(device="auto")

# Or explicitly use GPU
embedder = CLIPEmbedder(device="cuda")
```

### 3. Optimal Batch Size

Choose batch size based on your GPU memory:

- **CPU**: batch_size=8-16
- **GPU (4GB)**: batch_size=32
- **GPU (8GB+)**: batch_size=64-128

```python
embeddings = await embedder.generate_embeddings_batch(
    image_paths,
    batch_size=64  # Adjust based on your hardware
)
```

### 4. Memory Management

The embedder automatically uses `torch.no_grad()` for inference and cleans up resources on shutdown.

## Error Handling

The embedder gracefully handles various error scenarios:

```python
# Missing files
embedding = await embedder.generate_embedding("nonexistent.jpg")
# Raises FileNotFoundError

# Corrupted files
embeddings = await embedder.generate_embeddings_batch(
    ["good.jpg", "corrupted.jpg", "good2.jpg"]
)
# Returns [embedding, None, embedding]

# Empty batch
embeddings = await embedder.generate_embeddings_batch([])
# Returns []
```

## Integration with Vector Databases

### Qdrant Example

```python
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

# Initialize
embedder = CLIPEmbedder(device="auto")
client = QdrantClient(host="localhost", port=6333)

# Create collection
client.create_collection(
    collection_name="products",
    vectors_config=VectorParams(
        size=embedder.get_embedding_dimension(),  # 512
        distance=Distance.COSINE
    )
)

# Index images
image_paths = ["product1.jpg", "product2.jpg"]
embeddings = await embedder.generate_embeddings_batch(image_paths)

points = []
for i, emb in enumerate(embeddings):
    if emb is not None:
        points.append({
            "id": i,
            "vector": emb.tolist(),
            "payload": {"image_path": image_paths[i]}
        })

client.upsert(collection_name="products", points=points)

# Search
query = "red sports car"
query_embedding = embedder.encode_text(query)

results = client.search(
    collection_name="products",
    query_vector=query_embedding.tolist(),
    limit=10
)
```

## Testing

Run the test suite:

```bash
# Run all tests
pytest tests/test_clip.py -v

# Run specific test class
pytest tests/test_clip.py::TestCLIPEmbedderInitialization -v

# Run with coverage
pytest tests/test_clip.py --cov=app.models.clip_model --cov-report=html
```

## Logging

The embedder uses loguru for comprehensive logging:

```python
from loguru import logger

# Configure logging
logger.remove()
logger.add(
    "clip_embedder.log",
    rotation="1 day",
    level="INFO"
)

# Use embedder (logs automatically)
embedder = CLIPEmbedder(device="auto")
```

Log levels:
- **INFO**: Initialization, progress updates
- **DEBUG**: Detailed operation info
- **WARNING**: Non-critical errors (missing files, etc.)
- **ERROR**: Critical errors
- **SUCCESS**: Successful operations

## Troubleshooting

### CUDA Out of Memory

Reduce batch size:

```python
embeddings = await embedder.generate_embeddings_batch(
    image_paths,
    batch_size=16  # Reduce from 32
)
```

### Model Download Issues

Models are downloaded from HuggingFace. If you have connection issues:

```python
# Pre-download model
from transformers import CLIPModel, CLIPProcessor

model_name = "openai/clip-vit-base-patch32"
CLIPModel.from_pretrained(model_name)
CLIPProcessor.from_pretrained(model_name)
```

### Slow CPU Performance

Use GPU or reduce image resolution:

```python
from PIL import Image

# Resize images before processing
image = Image.open("large_image.jpg")
image = image.resize((512, 512))
image.save("resized_image.jpg")

embedding = await embedder.generate_embedding("resized_image.jpg")
```

## Backward Compatibility

The legacy `CLIPModel` class is still available for backward compatibility:

```python
from app.models.clip_model import CLIPModel

# Legacy usage (deprecated)
model = CLIPModel(device="cpu")
embedding = model.encode_image(pil_image)
```

**Note:** New code should use `CLIPEmbedder` instead.

## License

This module uses the CLIP model from OpenAI, which is licensed under MIT License.

## References

- [CLIP Paper](https://arxiv.org/abs/2103.00020)
- [OpenAI CLIP](https://github.com/openai/CLIP)
- [HuggingFace Transformers](https://huggingface.co/docs/transformers)

