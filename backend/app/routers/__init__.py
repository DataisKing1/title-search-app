"""API routers package"""
from app.routers.auth import router as auth_router
from app.routers.searches import router as searches_router
from app.routers.documents import router as documents_router
from app.routers.reports import router as reports_router
from app.routers.batch import router as batch_router
from app.routers.counties import router as counties_router
from app.routers.chain_analysis import router as chain_analysis_router

__all__ = [
    "auth_router",
    "searches_router",
    "documents_router",
    "reports_router",
    "batch_router",
    "counties_router",
    "chain_analysis_router",
]
