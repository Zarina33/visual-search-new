"""
PostgreSQL database module with SQLAlchemy 2.0 async support.
"""
from datetime import datetime
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Numeric,
    Float,
    DateTime,
    Index,
    JSON,
    select,
    update,
    delete,
)
from sqlalchemy.ext.asyncio import (
    create_async_engine,
    AsyncSession,
    async_sessionmaker,
)
from sqlalchemy.orm import DeclarativeBase
from loguru import logger

from app.config import settings


# Base class for SQLAlchemy models
class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


# SQLAlchemy Models
class Product(Base):
    """Product model for storing product metadata."""
    
    __tablename__ = "products"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    external_id = Column(String(255), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True, index=True)
    price = Column(Numeric(10, 2), nullable=True)
    currency = Column(String(10), nullable=True)
    image_url = Column(String(1000), nullable=True)
    product_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False
    )
    
    def __repr__(self) -> str:
        return f"<Product(id={self.id}, external_id='{self.external_id}', title='{self.title}')>"


class SearchLog(Base):
    """Search log model for tracking search queries."""
    
    __tablename__ = "search_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    query_type = Column(String(50), nullable=False)  # "image" or "text"
    product_id = Column(String(255), nullable=True)
    similarity_score = Column(Float, nullable=True)
    results_count = Column(Integer, nullable=True)
    search_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self) -> str:
        return f"<SearchLog(id={self.id}, query_type='{self.query_type}', results_count={self.results_count})>"


# Create indexes
Index("idx_products_external_id", Product.external_id)
Index("idx_products_category", Product.category)
Index("idx_search_logs_created_at", SearchLog.created_at)


# Database engine and session management
_engine = None
_async_session_maker = None


def get_async_database_url() -> str:
    """
    Construct async PostgreSQL connection URL.
    
    Returns:
        Async database URL for asyncpg
    """
    return (
        f"postgresql+asyncpg://{settings.postgres_user}:{settings.postgres_password}"
        f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
    )


def get_engine(force_new: bool = False):
    """
    Get or create async database engine.
    
    Args:
        force_new: If True, create a new engine even if one exists
    
    Returns:
        AsyncEngine instance
    """
    global _engine
    if _engine is None or force_new:
        database_url = get_async_database_url()
        _engine = create_async_engine(
            database_url,
            echo=settings.debug,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            poolclass=None if force_new else None,  # Use default pool
        )
        logger.info(f"Created async database engine: {settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}")
    return _engine


def get_session_maker(force_new: bool = False):
    """
    Get or create async session maker.
    
    Args:
        force_new: If True, create a new session maker even if one exists
    
    Returns:
        async_sessionmaker instance
    """
    global _async_session_maker
    if _async_session_maker is None or force_new:
        engine = get_engine(force_new=force_new)
        _async_session_maker = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        logger.info("Created async session maker")
    return _async_session_maker


async def reset_engine():
    """
    Reset the global engine and session maker.
    Useful for testing to avoid event loop issues.
    """
    global _engine, _async_session_maker
    
    if _engine is not None:
        await _engine.dispose()
        _engine = None
    
    _async_session_maker = None
    logger.info("Reset database engine and session maker")


async def init_db() -> None:
    """
    Create all database tables.
    
    This function creates all tables defined in the Base metadata.
    """
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Database tables created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to create database tables: {e}")
        raise


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Async context manager for database sessions.
    
    Usage:
        async with get_session() as session:
            # Use session here
            pass
    
    Yields:
        AsyncSession instance
    """
    session_maker = get_session_maker()
    session = session_maker()
    try:
        yield session
        await session.commit()
    except Exception as e:
        await session.rollback()
        logger.error(f"Session error: {e}")
        raise
    finally:
        await session.close()


# CRUD Operations for Product
async def create_product(session: AsyncSession, product_data: dict) -> Product:
    """
    Create a new product.
    
    Args:
        session: Database session
        product_data: Dictionary with product data
        
    Returns:
        Created Product instance
        
    Raises:
        Exception: If product creation fails
    """
    try:
        product = Product(**product_data)
        session.add(product)
        await session.flush()
        await session.refresh(product)
        logger.info(f"✅ Created product: {product.external_id}")
        return product
    except Exception as e:
        logger.error(f"❌ Failed to create product: {e}")
        raise


async def get_product_by_id(session: AsyncSession, product_id: int) -> Optional[Product]:
    """
    Get product by internal ID.
    
    Args:
        session: Database session
        product_id: Internal product ID
        
    Returns:
        Product instance or None if not found
    """
    try:
        stmt = select(Product).where(Product.id == product_id)
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()
        if product:
            logger.debug(f"Found product by ID: {product_id}")
        else:
            logger.debug(f"Product not found by ID: {product_id}")
        return product
    except Exception as e:
        logger.error(f"❌ Failed to get product by ID {product_id}: {e}")
        raise


async def get_product_by_external_id(session: AsyncSession, external_id: str) -> Optional[Product]:
    """
    Get product by external ID.
    
    Args:
        session: Database session
        external_id: External product ID
        
    Returns:
        Product instance or None if not found
    """
    try:
        stmt = select(Product).where(Product.external_id == external_id)
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()
        if product:
            logger.debug(f"Found product by external_id: {external_id}")
        else:
            logger.debug(f"Product not found by external_id: {external_id}")
        return product
    except Exception as e:
        logger.error(f"❌ Failed to get product by external_id {external_id}: {e}")
        raise


async def get_products_count(session: AsyncSession) -> int:
    """
    Get total count of products in database.
    
    Args:
        session: Database session
        
    Returns:
        Total number of products
    """
    try:
        from sqlalchemy import func
        stmt = select(func.count(Product.id))
        result = await session.execute(stmt)
        count = result.scalar()
        return count or 0
    except Exception as e:
        logger.error(f"❌ Failed to get products count: {e}")
        raise


async def get_products(
    session: AsyncSession,
    skip: int = 0,
    limit: int = 100
) -> list[Product]:
    """
    Get list of products with pagination.
    
    Args:
        session: Database session
        skip: Number of records to skip
        limit: Maximum number of records to return
        
    Returns:
        List of Product instances
    """
    try:
        stmt = select(Product).offset(skip).limit(limit).order_by(Product.created_at.desc())
        result = await session.execute(stmt)
        products = result.scalars().all()
        logger.debug(f"Retrieved {len(products)} products (skip={skip}, limit={limit})")
        return list(products)
    except Exception as e:
        logger.error(f"❌ Failed to get products: {e}")
        raise


async def update_product(
    session: AsyncSession,
    product_id: int,
    product_data: dict
) -> Optional[Product]:
    """
    Update an existing product.
    
    Args:
        session: Database session
        product_id: Internal product ID
        product_data: Dictionary with updated product data
        
    Returns:
        Updated Product instance or None if not found
    """
    try:
        # Add updated_at timestamp
        product_data["updated_at"] = datetime.utcnow()
        
        stmt = (
            update(Product)
            .where(Product.id == product_id)
            .values(**product_data)
            .returning(Product)
        )
        result = await session.execute(stmt)
        product = result.scalar_one_or_none()
        
        if product:
            await session.flush()
            await session.refresh(product)
            logger.info(f"✅ Updated product: {product_id}")
        else:
            logger.warning(f"Product not found for update: {product_id}")
            
        return product
    except Exception as e:
        logger.error(f"❌ Failed to update product {product_id}: {e}")
        raise


async def delete_product(session: AsyncSession, product_id: int) -> bool:
    """
    Delete a product (hard delete).
    
    Args:
        session: Database session
        product_id: Internal product ID
        
    Returns:
        True if deleted, False if not found
    """
    try:
        stmt = delete(Product).where(Product.id == product_id)
        result = await session.execute(stmt)
        
        if result.rowcount > 0:
            logger.info(f"✅ Deleted product: {product_id}")
            return True
        else:
            logger.warning(f"Product not found for deletion: {product_id}")
            return False
    except Exception as e:
        logger.error(f"❌ Failed to delete product {product_id}: {e}")
        raise


# CRUD Operations for SearchLog
async def log_search(session: AsyncSession, log_data: dict) -> SearchLog:
    """
    Log a search query.
    
    Args:
        session: Database session
        log_data: Dictionary with search log data
        
    Returns:
        Created SearchLog instance
    """
    try:
        search_log = SearchLog(**log_data)
        session.add(search_log)
        await session.flush()
        await session.refresh(search_log)
        logger.debug(f"Logged search: {search_log.query_type}")
        return search_log
    except Exception as e:
        logger.error(f"❌ Failed to log search: {e}")
        raise


async def close_db() -> None:
    """
    Close database engine and cleanup connections.
    """
    global _engine, _async_session_maker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_maker = None
        logger.info("Database engine closed")
