"""
Image processing utilities.
"""
import requests
from PIL import Image
from io import BytesIO
from typing import Tuple
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings


@retry(
    stop=stop_after_attempt(settings.max_retries),
    wait=wait_exponential(multiplier=settings.retry_delay, max=10),
)
def download_image(url: str, timeout: int = 10) -> Image.Image:
    """
    Download image from URL with retry logic.
    
    Args:
        url: Image URL
        timeout: Request timeout in seconds
        
    Returns:
        PIL Image object
        
    Raises:
        Exception: If download fails after retries
    """
    response = requests.get(url, timeout=timeout)
    response.raise_for_status()
    
    image = Image.open(BytesIO(response.content))
    return image.convert("RGB")


def process_image(
    image: Image.Image,
    max_size: int = None,
    quality: int = None,
) -> Image.Image:
    """
    Process and resize image if needed.
    
    Args:
        image: PIL Image object
        max_size: Maximum dimension (default from settings)
        quality: Image quality (default from settings)
        
    Returns:
        Processed PIL Image object
    """
    max_size = max_size or settings.max_image_size
    quality = quality or settings.image_quality
    
    # Convert to RGB if needed
    if image.mode != "RGB":
        image = image.convert("RGB")
    
    # Resize if image is too large
    if max(image.size) > max_size:
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    
    return image


def validate_image_format(filename: str) -> bool:
    """
    Validate image file format.
    
    Args:
        filename: Image filename
        
    Returns:
        True if format is allowed, False otherwise
    """
    extension = filename.lower().split(".")[-1]
    return extension in settings.allowed_formats_list


def get_image_dimensions(image: Image.Image) -> Tuple[int, int]:
    """
    Get image dimensions.
    
    Args:
        image: PIL Image object
        
    Returns:
        Tuple of (width, height)
    """
    return image.size

