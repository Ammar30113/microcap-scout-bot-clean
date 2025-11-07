"""
FastAPI route registrations.
"""

from .health import router as health_router
from .products import router as products_router

__all__ = ["health_router", "products_router"]
