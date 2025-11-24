"""
BakaiMarket S3-compatible storage client.

Клиент для работы с S3-совместимым хранилищем BakaiMarket (MinIO/S3).
"""
import boto3
from botocore.client import Config
from botocore.exceptions import ClientError
from typing import List, Dict, Optional, Any
from loguru import logger
from pathlib import Path

from app.config import settings


class BakaiS3Client:
    """Client for BakaiMarket S3-compatible storage."""
    
    def __init__(
        self,
        endpoint_url: str = None,
        access_key: str = None,
        secret_key: str = None
    ):
        """
        Initialize BakaiMarket S3 client.
        
        Args:
            endpoint_url: S3 endpoint URL (default from settings)
            access_key: Access key (default from settings)
            secret_key: Secret key (default from settings)
        """
        self.endpoint_url = endpoint_url or settings.bakai_cdn_api_url
        self.access_key = access_key or settings.bakai_cdn_access_key
        self.secret_key = secret_key or settings.bakai_cdn_secret_key
        
        if not self.access_key or not self.secret_key:
            logger.warning("⚠️  BakaiMarket S3 credentials not configured")
        
        # Create S3 client with signature version 4
        self.s3_client = boto3.client(
            's3',
            endpoint_url=self.endpoint_url,
            aws_access_key_id=self.access_key,
            aws_secret_access_key=self.secret_key,
            config=Config(signature_version='s3v4'),
            region_name='us-east-1'  # Default region
        )
        
        logger.info(f"🔗 BakaiS3 Client initialized: {self.endpoint_url}")
    
    def list_buckets(self) -> List[str]:
        """
        List all available buckets.
        
        Returns:
            List of bucket names
        """
        try:
            response = self.s3_client.list_buckets()
            buckets = [bucket['Name'] for bucket in response.get('Buckets', [])]
            logger.info(f"📦 Found {len(buckets)} buckets")
            return buckets
        except ClientError as e:
            logger.error(f"❌ Failed to list buckets: {e}")
            return []
    
    def list_objects(
        self,
        bucket_name: str,
        prefix: str = "",
        max_keys: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        List objects in a bucket.
        
        Args:
            bucket_name: Name of the bucket
            prefix: Prefix filter (folder path)
            max_keys: Maximum number of objects to return
            
        Returns:
            List of object metadata dicts
        """
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            objects = response.get('Contents', [])
            logger.info(f"📄 Found {len(objects)} objects in bucket '{bucket_name}'")
            
            return objects
            
        except ClientError as e:
            logger.error(f"❌ Failed to list objects in '{bucket_name}': {e}")
            return []
    
    def download_file(
        self,
        bucket_name: str,
        object_key: str,
        local_path: str
    ) -> bool:
        """
        Download file from S3 storage.
        
        Args:
            bucket_name: Name of the bucket
            object_key: Object key (path in bucket)
            local_path: Local path to save file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if needed
            Path(local_path).parent.mkdir(parents=True, exist_ok=True)
            
            self.s3_client.download_file(bucket_name, object_key, local_path)
            logger.debug(f"✅ Downloaded: {object_key} -> {local_path}")
            return True
            
        except ClientError as e:
            logger.error(f"❌ Failed to download {object_key}: {e}")
            return False
    
    def get_object_metadata(
        self,
        bucket_name: str,
        object_key: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get metadata for an object.
        
        Args:
            bucket_name: Name of the bucket
            object_key: Object key
            
        Returns:
            Object metadata dict or None
        """
        try:
            response = self.s3_client.head_object(
                Bucket=bucket_name,
                Key=object_key
            )
            return response
        except ClientError as e:
            logger.error(f"❌ Failed to get metadata for {object_key}: {e}")
            return None
    
    def generate_presigned_url(
        self,
        bucket_name: str,
        object_key: str,
        expiration: int = 3600
    ) -> Optional[str]:
        """
        Generate presigned URL for object.
        
        Args:
            bucket_name: Name of the bucket
            object_key: Object key
            expiration: URL expiration time in seconds
            
        Returns:
            Presigned URL or None
        """
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': bucket_name,
                    'Key': object_key
                },
                ExpiresIn=expiration
            )
            return url
        except ClientError as e:
            logger.error(f"❌ Failed to generate presigned URL: {e}")
            return None
    
    def test_connection(self) -> bool:
        """
        Test connection to S3 storage.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            logger.info("🔍 Testing connection to BakaiMarket S3...")
            buckets = self.list_buckets()
            
            if buckets is not None:
                logger.success(f"✅ Connection successful! Found {len(buckets)} buckets")
                return True
            else:
                logger.warning("⚠️  Connection successful but no buckets accessible")
                return False
                
        except Exception as e:
            logger.error(f"❌ Connection failed: {e}")
            return False


# Global client instance
_bakai_s3_client: Optional[BakaiS3Client] = None


def get_bakai_s3_client() -> BakaiS3Client:
    """Get or create global BakaiS3 client instance."""
    global _bakai_s3_client
    
    if _bakai_s3_client is None:
        _bakai_s3_client = BakaiS3Client()
    
    return _bakai_s3_client

