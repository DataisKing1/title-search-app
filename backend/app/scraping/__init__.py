"""Browser automation and scraping package"""
from app.scraping.browser_pool import BrowserPoolManager
from app.scraping.base_adapter import BaseCountyAdapter, SearchResult, DownloadedDocument

__all__ = [
    "BrowserPoolManager",
    "BaseCountyAdapter",
    "SearchResult",
    "DownloadedDocument",
]
