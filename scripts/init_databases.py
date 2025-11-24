#!/usr/bin/env python3
"""
Database initialization script.

This script initializes both PostgreSQL and Qdrant databases:
1. Creates tables in PostgreSQL
2. Creates collection in Qdrant
3. Displays statistics and status
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from loguru import logger
from app.config import settings
from app.db.postgres import init_db, get_session, Product, SearchLog, close_db
from app.db.qdrant import QdrantManager


async def init_postgresql() -> bool:
    """
    Initialize PostgreSQL database.
    
    Returns:
        True if successful, False otherwise
    """
    print("\n" + "="*60)
    print("📊 INITIALIZING POSTGRESQL DATABASE")
    print("="*60)
    
    try:
        print(f"\n🔗 Connecting to PostgreSQL...")
        print(f"   Host: {settings.postgres_host}")
        print(f"   Port: {settings.postgres_port}")
        print(f"   Database: {settings.postgres_db}")
        print(f"   User: {settings.postgres_user}")
        
        # Create tables
        print(f"\n📋 Creating tables...")
        await init_db()
        
        # Verify tables
        async with get_session() as session:
            # Try to query tables to verify they exist
            from sqlalchemy import text
            result = await session.execute(
                text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
            )
            tables = [row[0] for row in result.fetchall()]
            
            print(f"\n✅ PostgreSQL initialized successfully!")
            print(f"\n📊 Tables created:")
            for table in tables:
                print(f"   • {table}")
            
            return True
            
    except Exception as e:
        print(f"\n❌ Failed to initialize PostgreSQL: {e}")
        logger.error(f"PostgreSQL initialization error: {e}")
        return False


async def init_qdrant() -> bool:
    """
    Initialize Qdrant vector database.
    
    Returns:
        True if successful, False otherwise
    """
    print("\n" + "="*60)
    print("🔍 INITIALIZING QDRANT VECTOR DATABASE")
    print("="*60)
    
    try:
        print(f"\n🔗 Connecting to Qdrant...")
        print(f"   Host: {settings.qdrant_host}")
        print(f"   Port: {settings.qdrant_port}")
        print(f"   Collection: {settings.qdrant_collection_name}")
        
        # Initialize Qdrant manager
        qdrant = QdrantManager(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            collection_name=settings.qdrant_collection_name
        )
        
        # Create collection
        print(f"\n📦 Creating collection...")
        print(f"   Vector size: {settings.qdrant_vector_size}")
        print(f"   Distance metric: Cosine")
        
        await qdrant.create_collection(
            vector_size=settings.qdrant_vector_size,
            distance="Cosine"
        )
        
        # Get collection info
        info = await qdrant.get_collection_info()
        
        print(f"\n✅ Qdrant initialized successfully!")
        print(f"\n📊 Collection info:")
        print(f"   • Name: {info['name']}")
        print(f"   • Vector size: {info['vector_size']}")
        print(f"   • Distance: {info['distance']}")
        print(f"   • Points count: {info['points_count']}")
        print(f"   • Status: {info['status']}")
        
        # Close connection
        qdrant.close()
        
        return True
        
    except Exception as e:
        print(f"\n❌ Failed to initialize Qdrant: {e}")
        logger.error(f"Qdrant initialization error: {e}")
        return False


async def display_summary(postgres_success: bool, qdrant_success: bool) -> None:
    """
    Display initialization summary.
    
    Args:
        postgres_success: PostgreSQL initialization status
        qdrant_success: Qdrant initialization status
    """
    print("\n" + "="*60)
    print("📋 INITIALIZATION SUMMARY")
    print("="*60)
    
    print(f"\n{'✅' if postgres_success else '❌'} PostgreSQL: {'SUCCESS' if postgres_success else 'FAILED'}")
    print(f"{'✅' if qdrant_success else '❌'} Qdrant: {'SUCCESS' if qdrant_success else 'FAILED'}")
    
    if postgres_success and qdrant_success:
        print("\n🎉 All databases initialized successfully!")
        print("\n📝 Next steps:")
        print("   1. Load sample data: python scripts/load_sample_data.py")
        print("   2. Start the API server: make run")
        print("   3. Test the API: python tests/test_api.py")
    else:
        print("\n⚠️  Some databases failed to initialize.")
        print("   Please check the error messages above and fix the issues.")
        
    print("\n" + "="*60 + "\n")


async def main() -> None:
    """Main initialization function."""
    print("\n" + "="*60)
    print("🚀 DATABASE INITIALIZATION SCRIPT")
    print("="*60)
    print(f"\n📦 Project: {settings.app_name}")
    print(f"🔖 Version: {settings.app_version}")
    print(f"🔧 Environment: {'Development' if settings.debug else 'Production'}")
    
    # Initialize PostgreSQL
    postgres_success = await init_postgresql()
    
    # Initialize Qdrant
    qdrant_success = await init_qdrant()
    
    # Display summary
    await display_summary(postgres_success, qdrant_success)
    
    # Close database connections
    await close_db()
    
    # Exit with appropriate code
    if postgres_success and qdrant_success:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    # Configure logger
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <level>{message}</level>",
        level=settings.log_level
    )
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\n⚠️  Initialization cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        logger.exception("Unexpected error during initialization")
        sys.exit(1)





