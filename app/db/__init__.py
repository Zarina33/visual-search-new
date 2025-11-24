"""
Database clients for PostgreSQL and Qdrant.
"""
from .postgres import (
    Product,
    SearchLog,
    init_db,
    get_session,
    create_product,
    get_product_by_id,
    get_product_by_external_id,
    get_products,
    update_product,
    delete_product,
    log_search,
    close_db,
)
from .qdrant import QdrantManager

__all__ = [
    # PostgreSQL models
    "Product",
    "SearchLog",
    # PostgreSQL functions
    "init_db",
    "get_session",
    "create_product",
    "get_product_by_id",
    "get_product_by_external_id",
    "get_products",
    "update_product",
    "delete_product",
    "log_search",
    "close_db",
    # Qdrant
    "QdrantManager",
]

