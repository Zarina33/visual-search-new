"""
Comprehensive tests for optimized CLIP model wrapper.
"""
import asyncio
from pathlib import Path
from typing import List

import numpy as np
import pytest
from PIL import Image

from app.models.clip_model import CLIPEmbedder


@pytest.fixture
def clip_embedder():
    """Create CLIPEmbedder instance with CPU device."""
    return CLIPEmbedder(device="cpu")


@pytest.fixture
def sample_image_path(tmp_path):
    """Create a sample image file and return its path."""
    image_path = tmp_path / "test_image.jpg"
    image = Image.new("RGB", (224, 224), color="red")
    image.save(image_path)
    return str(image_path)


@pytest.fixture
def sample_images_paths(tmp_path):
    """Create multiple sample image files and return their paths."""
    paths = []
    colors = ["red", "green", "blue", "yellow", "purple"]
    
    for i, color in enumerate(colors):
        image_path = tmp_path / f"test_image_{i}.jpg"
        image = Image.new("RGB", (224, 224), color=color)
        image.save(image_path)
        paths.append(str(image_path))
    
    return paths


class TestCLIPEmbedderInitialization:
    """Tests for CLIPEmbedder initialization."""

    def test_init_default_parameters(self):
        """Test initialization with default parameters."""
        embedder = CLIPEmbedder()
        
        assert embedder.model_name == "openai/clip-vit-base-patch32"
        assert embedder.device in ["cpu", "cuda"]
        assert embedder.model is not None
        assert embedder.processor is not None

    def test_init_custom_model(self):
        """Test initialization with custom model name."""
        model_name = "openai/clip-vit-base-patch32"
        embedder = CLIPEmbedder(model_name=model_name, device="cpu")
        
        assert embedder.model_name == model_name

    def test_init_cpu_device(self):
        """Test initialization with CPU device."""
        embedder = CLIPEmbedder(device="cpu")
        
        assert embedder.device == "cpu"

    def test_init_auto_device(self):
        """Test initialization with auto device selection."""
        embedder = CLIPEmbedder(device="auto")
        
        assert embedder.device in ["cpu", "cuda"]

    def test_get_embedding_dimension(self, clip_embedder):
        """Test getting embedding dimension."""
        dim = clip_embedder.get_embedding_dimension()
        
        assert isinstance(dim, int)
        assert dim == 512  # Default for base CLIP model


class TestSingleImageEmbedding:
    """Tests for single image embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, clip_embedder, sample_image_path):
        """Test successful embedding generation for a single image."""
        embedding = await clip_embedder.generate_embedding(sample_image_path)
        
        assert embedding is not None
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (512,)
        
        # Check L2 normalization
        norm = np.linalg.norm(embedding)
        assert np.isclose(norm, 1.0, atol=1e-5)

    @pytest.mark.asyncio
    async def test_generate_embedding_file_not_found(self, clip_embedder):
        """Test embedding generation with non-existent file."""
        with pytest.raises(FileNotFoundError):
            await clip_embedder.generate_embedding("/nonexistent/path/image.jpg")

    @pytest.mark.asyncio
    async def test_generate_embedding_corrupted_file(self, clip_embedder, tmp_path):
        """Test embedding generation with corrupted file."""
        corrupted_path = tmp_path / "corrupted.jpg"
        corrupted_path.write_text("not an image")
        
        embedding = await clip_embedder.generate_embedding(str(corrupted_path))
        
        # Should return None for corrupted files
        assert embedding is None

    @pytest.mark.asyncio
    async def test_embedding_consistency(self, clip_embedder, sample_image_path):
        """Test that same image produces same embedding."""
        embedding1 = await clip_embedder.generate_embedding(sample_image_path)
        embedding2 = await clip_embedder.generate_embedding(sample_image_path)
        
        assert np.allclose(embedding1, embedding2, atol=1e-6)


class TestBatchEmbedding:
    """Tests for batch embedding generation."""

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_success(
        self, clip_embedder, sample_images_paths
    ):
        """Test successful batch embedding generation."""
        embeddings = await clip_embedder.generate_embeddings_batch(
            sample_images_paths, batch_size=2, show_progress=False
        )
        
        assert len(embeddings) == len(sample_images_paths)
        
        # Check all embeddings are valid
        for embedding in embeddings:
            assert embedding is not None
            assert isinstance(embedding, np.ndarray)
            assert embedding.shape == (512,)
            
            # Check L2 normalization
            norm = np.linalg.norm(embedding)
            assert np.isclose(norm, 1.0, atol=1e-5)

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_with_failures(
        self, clip_embedder, sample_images_paths, tmp_path
    ):
        """Test batch processing with some failed images."""
        # Add a non-existent path
        paths_with_failure = sample_images_paths + ["/nonexistent/image.jpg"]
        
        embeddings = await clip_embedder.generate_embeddings_batch(
            paths_with_failure, batch_size=2, show_progress=False
        )
        
        assert len(embeddings) == len(paths_with_failure)
        
        # Check successful embeddings
        for i in range(len(sample_images_paths)):
            assert embeddings[i] is not None
        
        # Check failed embedding
        assert embeddings[-1] is None

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_empty_list(self, clip_embedder):
        """Test batch processing with empty list."""
        embeddings = await clip_embedder.generate_embeddings_batch(
            [], batch_size=2, show_progress=False
        )
        
        assert len(embeddings) == 0

    @pytest.mark.asyncio
    async def test_generate_embeddings_batch_different_batch_sizes(
        self, clip_embedder, sample_images_paths
    ):
        """Test batch processing with different batch sizes."""
        # Test with batch_size=1
        embeddings1 = await clip_embedder.generate_embeddings_batch(
            sample_images_paths, batch_size=1, show_progress=False
        )
        
        # Test with batch_size=10 (larger than number of images)
        embeddings2 = await clip_embedder.generate_embeddings_batch(
            sample_images_paths, batch_size=10, show_progress=False
        )
        
        # Results should be the same
        assert len(embeddings1) == len(embeddings2)
        for emb1, emb2 in zip(embeddings1, embeddings2):
            assert np.allclose(emb1, emb2, atol=1e-6)


class TestTextEncoding:
    """Tests for text encoding."""

    def test_encode_text_single(self, clip_embedder):
        """Test encoding a single text string."""
        text = "a red car"
        embedding = clip_embedder.encode_text(text)
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (512,)
        
        # Check L2 normalization
        norm = np.linalg.norm(embedding)
        assert np.isclose(norm, 1.0, atol=1e-5)

    def test_encode_text_batch(self, clip_embedder):
        """Test encoding multiple text strings."""
        texts = ["a red car", "a blue sofa", "a wooden table"]
        embeddings = clip_embedder.encode_text(texts)
        
        assert isinstance(embeddings, np.ndarray)
        assert embeddings.shape == (3, 512)
        
        # Check L2 normalization for each embedding
        for embedding in embeddings:
            norm = np.linalg.norm(embedding)
            assert np.isclose(norm, 1.0, atol=1e-5)

    def test_encode_text_empty_string(self, clip_embedder):
        """Test encoding an empty string."""
        embedding = clip_embedder.encode_text("")
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (512,)

    def test_encode_text_consistency(self, clip_embedder):
        """Test that same text produces same embedding."""
        text = "a red car"
        embedding1 = clip_embedder.encode_text(text)
        embedding2 = clip_embedder.encode_text(text)
        
        assert np.allclose(embedding1, embedding2, atol=1e-6)


class TestSimilarityComputation:
    """Tests for similarity computation."""

    def test_compute_similarity_identical(self, clip_embedder):
        """Test similarity between identical embeddings."""
        text = "a red car"
        embedding = clip_embedder.encode_text(text)
        
        similarity = clip_embedder.compute_similarity(embedding, embedding)
        
        assert isinstance(similarity, float)
        assert np.isclose(similarity, 1.0, atol=1e-5)

    def test_compute_similarity_different(self, clip_embedder):
        """Test similarity between different embeddings."""
        text1 = "a red car"
        text2 = "a blue sofa"
        
        embedding1 = clip_embedder.encode_text(text1)
        embedding2 = clip_embedder.encode_text(text2)
        
        similarity = clip_embedder.compute_similarity(embedding1, embedding2)
        
        assert isinstance(similarity, float)
        assert -1.0 <= similarity <= 1.0
        assert similarity < 1.0  # Should not be identical

    @pytest.mark.asyncio
    async def test_compute_similarity_image_text(
        self, clip_embedder, sample_image_path
    ):
        """Test similarity between image and text embeddings."""
        image_embedding = await clip_embedder.generate_embedding(sample_image_path)
        text_embedding = clip_embedder.encode_text("a red image")
        
        similarity = clip_embedder.compute_similarity(image_embedding, text_embedding)
        
        assert isinstance(similarity, float)
        assert -1.0 <= similarity <= 1.0


class TestResourceManagement:
    """Tests for resource management and cleanup."""

    def test_cleanup_on_delete(self):
        """Test that cleanup is called when embedder is deleted."""
        embedder = CLIPEmbedder(device="cpu")
        
        # Delete the embedder
        del embedder
        
        # If no exception is raised, cleanup worked

    def test_multiple_instances(self):
        """Test creating multiple embedder instances."""
        embedder1 = CLIPEmbedder(device="cpu")
        embedder2 = CLIPEmbedder(device="cpu")
        
        assert embedder1.model is not None
        assert embedder2.model is not None
        
        del embedder1
        del embedder2


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_very_small_image(self, clip_embedder, tmp_path):
        """Test with very small image."""
        image_path = tmp_path / "tiny.jpg"
        image = Image.new("RGB", (10, 10), color="red")
        image.save(image_path)
        
        embedding = await clip_embedder.generate_embedding(str(image_path))
        
        assert embedding is not None
        assert embedding.shape == (512,)

    @pytest.mark.asyncio
    async def test_very_large_image(self, clip_embedder, tmp_path):
        """Test with very large image."""
        image_path = tmp_path / "large.jpg"
        image = Image.new("RGB", (2000, 2000), color="blue")
        image.save(image_path)
        
        embedding = await clip_embedder.generate_embedding(str(image_path))
        
        assert embedding is not None
        assert embedding.shape == (512,)

    def test_very_long_text(self, clip_embedder):
        """Test with very long text (should be truncated)."""
        long_text = " ".join(["word"] * 1000)
        embedding = clip_embedder.encode_text(long_text)
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (512,)

    def test_special_characters_in_text(self, clip_embedder):
        """Test with special characters in text."""
        text = "a car with @#$%^&*() symbols"
        embedding = clip_embedder.encode_text(text)
        
        assert isinstance(embedding, np.ndarray)
        assert embedding.shape == (512,)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

