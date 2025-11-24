"""
Tests for CLIP model wrapper.
"""
import pytest
import numpy as np
from PIL import Image

from app.models.clip_model import CLIPModel


@pytest.fixture
def clip_model():
    """Create CLIP model instance."""
    return CLIPModel(device="cpu")


@pytest.fixture
def sample_image():
    """Create sample image."""
    return Image.new("RGB", (224, 224), color="red")


def test_encode_image_single(clip_model, sample_image):
    """Test encoding a single image."""
    embedding = clip_model.encode_image(sample_image)
    
    assert isinstance(embedding, np.ndarray)
    assert embedding.ndim == 1
    assert len(embedding) == 512  # Default CLIP embedding size


def test_encode_image_batch(clip_model, sample_image):
    """Test encoding multiple images."""
    images = [sample_image, sample_image]
    embeddings = clip_model.encode_image(images)
    
    assert isinstance(embeddings, np.ndarray)
    assert embeddings.ndim == 2
    assert embeddings.shape == (2, 512)


def test_encode_text_single(clip_model):
    """Test encoding a single text."""
    text = "a red car"
    embedding = clip_model.encode_text(text)
    
    assert isinstance(embedding, np.ndarray)
    assert embedding.ndim == 1
    assert len(embedding) == 512


def test_encode_text_batch(clip_model):
    """Test encoding multiple texts."""
    texts = ["a red car", "a blue sofa"]
    embeddings = clip_model.encode_text(texts)
    
    assert isinstance(embeddings, np.ndarray)
    assert embeddings.ndim == 2
    assert embeddings.shape == (2, 512)


def test_compute_similarity(clip_model, sample_image):
    """Test computing similarity between image and text."""
    image_embedding = clip_model.encode_image(sample_image)
    text_embedding = clip_model.encode_text("a red image")
    
    similarity = clip_model.compute_similarity(image_embedding, text_embedding)
    
    assert isinstance(similarity, float)
    assert -1.0 <= similarity <= 1.0

