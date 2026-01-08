"""Base adapter class for county website scraping"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from playwright.async_api import Page
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import logging

from app.config import settings

logger = logging.getLogger(__name__)


class DocumentTypeHint(str, Enum):
    """Hints for document type classification"""
    DEED = "deed"
    MORTGAGE = "mortgage"
    DEED_OF_TRUST = "deed_of_trust"
    LIEN = "lien"
    RELEASE = "release"
    ASSIGNMENT = "assignment"
    EASEMENT = "easement"
    PLAT = "plat"
    OTHER = "other"


@dataclass
class SearchResult:
    """Represents a single search result from a county website"""
    instrument_number: str
    document_type: str
    recording_date: Optional[datetime] = None
    grantor: List[str] = field(default_factory=list)
    grantee: List[str] = field(default_factory=list)
    book: Optional[str] = None
    page: Optional[str] = None
    consideration: Optional[str] = None
    legal_description: Optional[str] = None
    download_url: Optional[str] = None
    source_county: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DownloadedDocument:
    """Represents a downloaded document"""
    file_path: str
    file_name: str
    file_size: int
    mime_type: str
    content_hash: str
    instrument_number: Optional[str] = None


class BaseCountyAdapter(ABC):
    """
    Abstract base class for county recorder website adapters.

    Each county website has different layouts and search interfaces.
    Subclasses implement the specific logic for each county.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration.

        Args:
            config: County-specific configuration including:
                - county_name: Name of the county
                - recorder_url: Base URL for recorder website
                - requests_per_minute: Rate limit
                - delay_between_requests_ms: Delay between requests
                - requires_auth: Whether authentication is required
                - auth_config: Authentication credentials if required
        """
        self.config = config
        self.county_name = config.get("county_name", "Unknown")
        self.base_url = config.get("recorder_url", "")
        self.rate_limit = config.get("requests_per_minute", 10)
        self.delay_ms = config.get("delay_between_requests_ms", 2000)
        self.requires_auth = config.get("requires_auth", False)
        self.auth_config = config.get("auth_config", {})
        self.logger = logging.getLogger(f"{__name__}.{self.county_name}")

    @abstractmethod
    async def initialize(self, page: Page) -> bool:
        """
        Initialize the session on the county website.

        This typically involves:
        - Navigating to the search page
        - Accepting any disclaimers or terms
        - Logging in if required

        Args:
            page: Playwright page object

        Returns:
            bool: True if initialization successful
        """
        pass

    @abstractmethod
    async def search_by_parcel(
        self,
        page: Page,
        parcel_number: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """
        Search records by parcel/APN number.

        Args:
            page: Playwright page object
            parcel_number: The parcel or APN number
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of SearchResult objects
        """
        pass

    @abstractmethod
    async def search_by_name(
        self,
        page: Page,
        name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """
        Search records by grantor/grantee name.

        Args:
            page: Playwright page object
            name: The name to search for
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of SearchResult objects
        """
        pass

    async def search_by_address(
        self,
        page: Page,
        address: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """
        Search records by property address.

        Default implementation returns empty list.
        Override if the county supports address search.

        Args:
            page: Playwright page object
            address: The property address
            start_date: Optional start date filter
            end_date: Optional end date filter

        Returns:
            List of SearchResult objects
        """
        self.logger.warning(f"Address search not implemented for {self.county_name}")
        return []

    @abstractmethod
    async def download_document(
        self,
        page: Page,
        result: SearchResult,
        download_path: str
    ) -> Optional[DownloadedDocument]:
        """
        Download a document PDF.

        Args:
            page: Playwright page object
            result: SearchResult containing download info
            download_path: Directory to save the file

        Returns:
            DownloadedDocument if successful, None otherwise
        """
        pass

    async def handle_captcha(self, page: Page) -> bool:
        """
        Handle CAPTCHA if encountered.

        Default implementation logs warning and returns False.
        Override for county-specific CAPTCHA handling.

        Args:
            page: Playwright page object

        Returns:
            bool: True if CAPTCHA solved, False otherwise
        """
        self.logger.warning(f"CAPTCHA encountered on {self.county_name} - manual intervention needed")
        return False

    async def handle_rate_limit(self, page: Page) -> None:
        """
        Handle rate limit response.

        Default implementation waits for configured delay.

        Args:
            page: Playwright page object
        """
        delay = settings.SCRAPING_RATE_LIMIT_DELAY_SECONDS
        self.logger.warning(f"Rate limit hit on {self.county_name}, waiting {delay} seconds")
        await asyncio.sleep(delay)

    async def wait_between_requests(self) -> None:
        """Wait the configured delay between requests"""
        await asyncio.sleep(self.delay_ms / 1000)

    def classify_document_type(self, type_text: str) -> str:
        """
        Classify document type from raw text.

        Args:
            type_text: Raw document type text from website

        Returns:
            Normalized document type string
        """
        type_lower = type_text.lower().strip()

        # Deed types
        if any(word in type_lower for word in ["warranty deed", "quit claim", "quitclaim", "special warranty"]):
            return "deed"
        if "deed of trust" in type_lower:
            return "deed_of_trust"
        if "deed" in type_lower:
            return "deed"

        # Mortgage and liens
        if "mortgage" in type_lower:
            return "mortgage"
        if "mechanics lien" in type_lower or "mechanic's lien" in type_lower:
            return "mechanics_lien"
        if "tax lien" in type_lower:
            return "tax_lien"
        if "judgment" in type_lower:
            return "judgment"
        if "lien" in type_lower:
            return "lien"

        # Releases and satisfactions
        if "release" in type_lower or "reconveyance" in type_lower:
            return "release"
        if "satisfaction" in type_lower:
            return "satisfaction"

        # Other types
        if "assignment" in type_lower:
            return "assignment"
        if "subordination" in type_lower:
            return "subordination"
        if "easement" in type_lower:
            return "easement"
        if "plat" in type_lower or "subdivision" in type_lower:
            return "plat"
        if "survey" in type_lower:
            return "survey"
        if "lis pendens" in type_lower:
            return "lis_pendens"
        if "ucc" in type_lower:
            return "ucc_filing"

        return "other"

    def parse_date(self, date_text: str) -> Optional[datetime]:
        """
        Parse date string into datetime.

        Args:
            date_text: Raw date string

        Returns:
            datetime object or None if parsing fails
        """
        if not date_text:
            return None

        date_text = date_text.strip()

        # Common formats
        formats = [
            "%m/%d/%Y",
            "%m-%d-%Y",
            "%Y-%m-%d",
            "%m/%d/%y",
            "%B %d, %Y",
            "%b %d, %Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue

        self.logger.warning(f"Could not parse date: {date_text}")
        return None

    def parse_names(self, name_text: str) -> List[str]:
        """
        Parse name string into list of individual names.

        Args:
            name_text: Raw name string (may contain multiple names)

        Returns:
            List of individual names
        """
        if not name_text:
            return []

        # Split on common delimiters
        delimiters = [";", " AND ", " & ", "/", ","]
        names = [name_text]

        for delimiter in delimiters:
            new_names = []
            for name in names:
                new_names.extend(name.split(delimiter))
            names = new_names

        # Clean up each name
        cleaned = []
        for name in names:
            name = name.strip()
            if name and len(name) > 1:
                cleaned.append(name)

        return cleaned

    async def screenshot_on_error(self, page: Page, error_name: str) -> str:
        """
        Take a screenshot when an error occurs.

        Args:
            page: Playwright page object
            error_name: Name to include in filename

        Returns:
            Path to saved screenshot
        """
        import os
        from datetime import datetime

        screenshots_dir = os.getenv("STORAGE_PATH", "./storage")
        os.makedirs(f"{screenshots_dir}/screenshots", exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{screenshots_dir}/screenshots/{self.county_name}_{error_name}_{timestamp}.png"

        try:
            await page.screenshot(path=filename, full_page=True)
            self.logger.info(f"Saved error screenshot: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Failed to save screenshot: {e}")
            return ""

    async def check_for_errors(self, page: Page) -> Optional[str]:
        """
        Check page for common error conditions.

        Args:
            page: Playwright page object

        Returns:
            Error message if error detected, None otherwise
        """
        # Check for common error indicators
        error_selectors = [
            ".error-message",
            ".alert-danger",
            "#errorMessage",
            "[class*='error']",
            "[class*='Error']",
        ]

        for selector in error_selectors:
            try:
                element = page.locator(selector).first
                if await element.count() > 0:
                    text = await element.inner_text()
                    if text:
                        return text.strip()
            except Exception as e:
                self.logger.debug(f"Error checking selector {selector}: {e}")

        # Check for rate limit indicators
        page_text = await page.content()
        if "too many requests" in page_text.lower():
            return "Rate limit detected"
        if "access denied" in page_text.lower():
            return "Access denied"

        return None
