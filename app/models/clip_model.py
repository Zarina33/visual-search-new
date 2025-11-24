"""
Optimized CLIP model wrapper for image and text encoding.
"""
import asyncio
import atexit
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import torch
from loguru import logger
from PIL import Image
from tqdm.asyncio import tqdm
from transformers import CLIPModel as HFCLIPModel
from transformers import CLIPProcessor

from app.config import settings


class CLIPEmbedder:
    """Optimized wrapper for CLIP model with async support and batch processing."""

    def __init__(
        self,
        model_name: str = "openai/clip-vit-base-patch32",
        device: str = "auto",
    ):
        """
        Initialize CLIP embedder with automatic device selection.

        Args:
            model_name: HuggingFace model name (default: openai/clip-vit-base-patch32)
            device: Device to use ('auto', 'cpu', 'cuda', or specific cuda device like 'cuda:0')
        """
        self.model_name = model_name
        self._setup_device(device)
        self._load_model()
        self._register_shutdown()

        logger.info(
            f"CLIPEmbedder initialized: model={self.model_name}, device={self.device}, "
            f"embedding_dim={self.get_embedding_dimension()}"
        )

    def _setup_device(self, device: str) -> None:
        """
        Setup computation device with automatic GPU detection.

        Args:
            device: Device specification ('auto', 'cpu', 'cuda')
        """
        if device == "auto":
            if torch.cuda.is_available():
                self.device = "cuda"
                logger.info(
                    f"GPU detected: {torch.cuda.get_device_name(0)} "
                    f"(CUDA {torch.version.cuda})"
                )
            else:
                self.device = "cpu"
                logger.info("No GPU detected, using CPU")
        else:
            self.device = device
            logger.info(f"Using specified device: {device}")

        # Validate device
        if self.device.startswith("cuda") and not torch.cuda.is_available():
            logger.warning("CUDA requested but not available, falling back to CPU")
            self.device = "cpu"

    def _load_model(self) -> None:
        """Load CLIP model and processor from HuggingFace."""
        try:
            logger.info(f"Loading CLIP model: {self.model_name}")

            # Load processor and model
            # Use safetensors to avoid torch.load vulnerability
            self.processor = CLIPProcessor.from_pretrained(self.model_name)
            self.model = HFCLIPModel.from_pretrained(
                self.model_name,
                use_safetensors=True
            )

            # Move to device and set to eval mode
            self.model.to(self.device)
            self.model.eval()

            # Get embedding dimension
            self._embedding_dim = self.model.config.projection_dim

            logger.success(
                f"Model loaded successfully (embedding_dim={self._embedding_dim})"
            )

        except Exception as e:
            logger.error(f"Failed to load CLIP model: {e}")
            raise

    def _register_shutdown(self) -> None:
        """Register graceful shutdown handler."""
        atexit.register(self._cleanup)

    def _cleanup(self) -> None:
        """Cleanup resources on shutdown."""
        try:
            if hasattr(self, "model"):
                del self.model
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            # Silently ignore cleanup errors (logger may be closed)
            pass

    async def generate_embedding(self, image_path: str) -> Optional[np.ndarray]:
        """
        Generate normalized embedding for a single image.

        Args:
            image_path: Path to image file

        Returns:
            Normalized embedding vector (L2 norm) as numpy array, or None if failed

        Raises:
            FileNotFoundError: If image file doesn't exist
            Exception: For other processing errors
        """
        try:
            # Validate path
            path = Path(image_path)
            if not path.exists():
                logger.error(f"Image file not found: {image_path}")
                raise FileNotFoundError(f"Image not found: {image_path}")

            # Load image
            logger.debug(f"Loading image: {image_path}")
            image = Image.open(path).convert("RGB")

            # Preprocess image
            inputs = self.processor(images=image, return_tensors="pt")
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Generate embedding with no gradient computation
            with torch.no_grad():
                image_features = self.model.get_image_features(**inputs)

                # CRITICAL: L2 normalization
                image_features = image_features / image_features.norm(
                    dim=-1, keepdim=True
                )

            # Convert to numpy
            embedding = image_features.cpu().numpy()[0]

            logger.debug(
                f"Generated embedding for {image_path}: shape={embedding.shape}, "
                f"norm={np.linalg.norm(embedding):.4f}"
            )

            return embedding

        except FileNotFoundError:
            raise
        except Exception as e:
            logger.error(f"Error generating embedding for {image_path}: {e}")
            return None

    async def generate_embeddings_batch(
        self,
        image_paths: List[str],
        batch_size: int = 32,
        show_progress: bool = True,
    ) -> List[Optional[np.ndarray]]:
        """
        Generate embeddings for multiple images with batch processing.

        Args:
            image_paths: List of image file paths
            batch_size: Number of images to process in each batch
            show_progress: Whether to show progress bar

        Returns:
            List of embeddings (None for failed images)
        """
        logger.info(
            f"Starting batch embedding generation: {len(image_paths)} images, "
            f"batch_size={batch_size}"
        )

        embeddings: List[Optional[np.ndarray]] = []
        failed_count = 0

        # Process in batches
        for i in range(0, len(image_paths), batch_size):
            batch_paths = image_paths[i : i + batch_size]

            # Load batch images
            batch_images = []
            batch_indices = []

            for idx, path in enumerate(batch_paths):
                try:
                    path_obj = Path(path)
                    if not path_obj.exists():
                        logger.warning(f"Skipping missing file: {path}")
                        embeddings.append(None)
                        failed_count += 1
                        continue

                    image = Image.open(path_obj).convert("RGB")
                    batch_images.append(image)
                    batch_indices.append(len(embeddings))
                    embeddings.append(None)  # Placeholder

                except Exception as e:
                    logger.warning(f"Failed to load image {path}: {e}")
                    embeddings.append(None)
                    failed_count += 1

            # Process batch if we have valid images
            if batch_images:
                try:
                    # Preprocess batch
                    inputs = self.processor(images=batch_images, return_tensors="pt")
                    inputs = {k: v.to(self.device) for k, v in inputs.items()}

                    # Generate embeddings with no gradient computation
                    with torch.no_grad():
                        batch_features = self.model.get_image_features(**inputs)

                        # CRITICAL: L2 normalization
                        batch_features = batch_features / batch_features.norm(
                            dim=-1, keepdim=True
                        )

                    # Convert to numpy and assign to results
                    batch_embeddings = batch_features.cpu().numpy()

                    for idx, embedding in zip(batch_indices, batch_embeddings):
                        embeddings[idx] = embedding

                except Exception as e:
                    logger.error(f"Batch processing failed: {e}")
                    # Mark all batch items as failed
                    for idx in batch_indices:
                        embeddings[idx] = None
                    failed_count += len(batch_images)

            # Update progress
            if show_progress:
                progress = (i + len(batch_paths)) / len(image_paths) * 100
                logger.info(f"Progress: {progress:.1f}% ({i + len(batch_paths)}/{len(image_paths)})")

        successful_count = len(embeddings) - failed_count
        logger.info(
            f"Batch processing completed: {successful_count}/{len(image_paths)} successful, "
            f"{failed_count} failed"
        )

        return embeddings

    def get_embedding_dimension(self) -> int:
        """
        Get the dimension of embedding vectors.

        Returns:
            Embedding dimension (typically 512 for base CLIP model)
        """
        return self._embedding_dim

    def encode_text(self, text: Union[str, List[str]]) -> np.ndarray:
        """
        Encode text(s) to normalized embedding vector(s).

        Args:
            text: String or list of strings

        Returns:
            Normalized embedding vector(s) as numpy array
        """
        try:
            # Ensure text is a list
            is_single = not isinstance(text, list)
            texts = [text] if is_single else text

            logger.debug(f"Encoding {len(texts)} text(s)")

            # Process text
            inputs = self.processor(
                text=texts, return_tensors="pt", padding=True, truncation=True
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}

            # Get embeddings with no gradient computation
            with torch.no_grad():
                text_features = self.model.get_text_features(**inputs)

                # CRITICAL: L2 normalization
                text_features = text_features / text_features.norm(
                    dim=-1, keepdim=True
                )

            embeddings = text_features.cpu().numpy()

            return embeddings[0] if is_single else embeddings

        except Exception as e:
            logger.error(f"Error encoding text: {e}")
            raise

    def compute_similarity(
        self, embedding1: np.ndarray, embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two normalized embeddings.

        Args:
            embedding1: First embedding vector (normalized)
            embedding2: Second embedding vector (normalized)

        Returns:
            Similarity score between -1 and 1 (typically 0 to 1 for normalized vectors)
        """
        similarity = np.dot(embedding1, embedding2)
        return float(similarity)


# Legacy alias for backward compatibility
class CLIPModel(CLIPEmbedder):
    """Legacy class name for backward compatibility."""

    def __init__(self, model_name: str = None, device: str = None):
        """Initialize with legacy parameter names."""
        model = model_name or settings.clip_model_name
        dev = device or settings.clip_device
        super().__init__(model_name=model, device=dev)
        logger.warning(
            "CLIPModel is deprecated, use CLIPEmbedder instead"
        )

    def encode_image(self, image: Union[Image.Image, List[Image.Image]]) -> np.ndarray:
        """Legacy method for encoding PIL images directly."""
        is_single = not isinstance(image, list)
        images = [image] if is_single else image

        inputs = self.processor(images=images, return_tensors="pt", padding=True)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}

        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)

        embeddings = image_features.cpu().numpy()
        return embeddings[0] if is_single else embeddings

