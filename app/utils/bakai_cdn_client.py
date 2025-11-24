"""
BakaiMarket CDN API Client.

Клиент для работы с API CDN BakaiMarket для получения списка товаров и изображений.
"""
import httpx
from typing import List, Dict, Optional, Any
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings


class BakaiCDNClient:
    """Client for BakaiMarket CDN API."""
    
    def __init__(
        self,
        api_url: str = None,
        access_key: str = None,
        secret_key: str = None
    ):
        """
        Initialize BakaiMarket CDN client.
        
        Args:
            api_url: API base URL (default from settings)
            access_key: Access key for authentication (default from settings)
            secret_key: Secret key for authentication (default from settings)
        """
        self.api_url = api_url or settings.bakai_cdn_api_url
        self.access_key = access_key or settings.bakai_cdn_access_key
        self.secret_key = secret_key or settings.bakai_cdn_secret_key
        
        if not self.access_key or not self.secret_key:
            logger.warning("⚠️  BakaiMarket CDN credentials not configured")
        
        self.headers = {
            "X-Access-Key": self.access_key,
            "X-Secret-Key": self.secret_key,
            "Content-Type": "application/json"
        }
        
        logger.info(f"🔗 BakaiCDN Client initialized: {self.api_url}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=10)
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make HTTP request to BakaiMarket API with retry logic.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (e.g., "/products")
            params: Query parameters
            json_data: JSON body data
            
        Returns:
            Response data as dict
            
        Raises:
            httpx.HTTPError: If request fails after retries
        """
        url = f"{self.api_url}{endpoint}"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=self.headers,
                    params=params,
                    json=json_data
                )
                response.raise_for_status()
                
                logger.debug(f"✅ Request successful: {method} {endpoint}")
                return response.json()
                
            except httpx.HTTPError as e:
                logger.error(f"❌ Request failed: {method} {endpoint} - {e}")
                raise
    
    async def get_products(
        self,
        limit: int = 100,
        offset: int = 0,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get list of products from BakaiMarket.
        
        Args:
            limit: Maximum number of products to return
            offset: Offset for pagination
            category: Filter by category (optional)
            
        Returns:
            List of product dictionaries
        """
        params = {
            "limit": limit,
            "offset": offset
        }
        
        if category:
            params["category"] = category
        
        try:
            logger.info(f"📦 Fetching products: limit={limit}, offset={offset}")
            response = await self._make_request("GET", "/products", params=params)
            
            products = response.get("products", [])
            total = response.get("total", len(products))
            
            logger.success(f"✅ Fetched {len(products)} products (total: {total})")
            return products
            
        except Exception as e:
            logger.error(f"❌ Failed to fetch products: {e}")
            return []
    
    async def get_product_by_id(self, product_id: str) -> Optional[Dict[str, Any]]:
        """
        Get single product by ID.
        
        Args:
            product_id: Product external ID
            
        Returns:
            Product dict or None if not found
        """
        try:
            logger.info(f"🔍 Fetching product: {product_id}")
            response = await self._make_request("GET", f"/products/{product_id}")
            
            product = response.get("product")
            if product:
                logger.success(f"✅ Product found: {product_id}")
            else:
                logger.warning(f"⚠️  Product not found: {product_id}")
            
            return product
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"⚠️  Product not found: {product_id}")
                return None
            logger.error(f"❌ Failed to fetch product {product_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Failed to fetch product {product_id}: {e}")
            return None
    
    async def get_all_products(
        self,
        batch_size: int = 100,
        max_products: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all products with pagination.
        
        Args:
            batch_size: Number of products per request
            max_products: Maximum total products to fetch (None = all)
            
        Returns:
            List of all product dictionaries
        """
        all_products = []
        offset = 0
        
        logger.info(f"📦 Fetching all products (batch_size={batch_size})")
        
        while True:
            # Fetch batch
            products = await self.get_products(limit=batch_size, offset=offset)
            
            if not products:
                break
            
            all_products.extend(products)
            offset += len(products)
            
            logger.info(f"📊 Progress: {len(all_products)} products fetched")
            
            # Check if we reached the limit
            if max_products and len(all_products) >= max_products:
                all_products = all_products[:max_products]
                break
            
            # If we got less than batch_size, we're done
            if len(products) < batch_size:
                break
        
        logger.success(f"✅ Total products fetched: {len(all_products)}")
        return all_products
    
    async def download_image(
        self,
        image_url: str,
        save_path: str
    ) -> bool:
        """
        Download product image from CDN.
        
        Args:
            image_url: Image URL (can be relative or absolute)
            save_path: Local path to save image
            
        Returns:
            True if successful, False otherwise
        """
        # If URL is relative, prepend API base URL
        if not image_url.startswith("http"):
            image_url = f"{self.api_url}{image_url}"
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(image_url, headers=self.headers)
                response.raise_for_status()
                
                # Save image
                with open(save_path, "wb") as f:
                    f.write(response.content)
                
                logger.debug(f"✅ Image downloaded: {save_path}")
                return True
                
        except Exception as e:
            logger.error(f"❌ Failed to download image {image_url}: {e}")
            return False
    
    async def test_connection(self) -> bool:
        """
        Test connection to BakaiMarket API.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("🔍 Testing connection to BakaiMarket API...")
            
            # Try to fetch just 1 product to test
            products = await self.get_products(limit=1)
            
            if products:
                logger.success("✅ Connection successful!")
                return True
            else:
                logger.warning("⚠️  Connection successful but no products found")
                return True
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False


# Global client instance
_bakai_client: Optional[BakaiCDNClient] = None


def get_bakai_client() -> BakaiCDNClient:
    """Get or create global BakaiCDN client instance."""
    global _bakai_client
    
    if _bakai_client is None:
        _bakai_client = BakaiCDNClient()
    
    return _bakai_client

