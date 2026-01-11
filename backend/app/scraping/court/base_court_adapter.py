"""Base adapter class for court records scraping"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from playwright.async_api import Page
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
import logging

logger = logging.getLogger(__name__)


class CaseType(str, Enum):
    """Types of court cases relevant to title search"""
    CIVIL = "civil"
    FORECLOSURE = "foreclosure"
    PROBATE = "probate"
    DOMESTIC = "domestic"
    SMALL_CLAIMS = "small_claims"
    JUDGMENT = "judgment"
    LIS_PENDENS = "lis_pendens"
    OTHER = "other"


class CaseStatus(str, Enum):
    """Status of a court case"""
    OPEN = "open"
    CLOSED = "closed"
    DISMISSED = "dismissed"
    PENDING = "pending"
    UNKNOWN = "unknown"


@dataclass
class CourtSearchResult:
    """Represents a single court case from search results"""
    case_number: str
    case_type: CaseType
    court_name: str
    filing_date: Optional[datetime] = None
    parties: List[str] = field(default_factory=list)
    plaintiff: Optional[str] = None
    defendant: Optional[str] = None
    status: CaseStatus = CaseStatus.UNKNOWN
    description: Optional[str] = None
    case_url: Optional[str] = None
    county: Optional[str] = None
    judgment_amount: Optional[str] = None
    raw_data: Dict[str, Any] = field(default_factory=dict)


class BaseCourtAdapter(ABC):
    """
    Abstract base class for court records website adapters.

    Court record systems vary significantly from state to state.
    Subclasses implement the specific logic for each court system.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize adapter with configuration.

        Args:
            config: Court-specific configuration including:
                - state: State code (e.g., "CO")
                - court_url: Base URL for court website
                - requests_per_minute: Rate limit
                - delay_between_requests_ms: Delay between requests
        """
        self.config = config
        self.state = config.get("state", "CO")
        self.base_url = config.get("court_url", "")
        self.rate_limit = config.get("requests_per_minute", 5)
        self.delay_ms = config.get("delay_between_requests_ms", 5000)
        self.logger = logging.getLogger(f"{__name__}.{self.state}")

    @abstractmethod
    async def initialize(self, page: Page) -> bool:
        """
        Initialize the session on the court website.

        This typically involves:
        - Navigating to the search page
        - Accepting any disclaimers or terms

        Args:
            page: Playwright page object

        Returns:
            bool: True if initialization successful
        """
        pass

    @abstractmethod
    async def search_by_name(
        self,
        page: Page,
        last_name: str,
        first_name: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        county: Optional[str] = None
    ) -> List[CourtSearchResult]:
        """
        Search court records by party name.

        Args:
            page: Playwright page object
            last_name: Party's last name (required)
            first_name: Party's first name (optional)
            start_date: Optional start date filter
            end_date: Optional end date filter
            county: Optional county filter

        Returns:
            List of CourtSearchResult objects
        """
        pass

    async def search_by_case_number(
        self,
        page: Page,
        case_number: str
    ) -> Optional[CourtSearchResult]:
        """
        Search court records by case number.

        Default implementation returns None.
        Override if the court system supports case number lookup.

        Args:
            page: Playwright page object
            case_number: The case number to search for

        Returns:
            CourtSearchResult if found, None otherwise
        """
        self.logger.warning(f"Case number search not implemented for {self.state}")
        return None

    async def get_case_details(
        self,
        page: Page,
        case_number: str
    ) -> Optional[CourtSearchResult]:
        """
        Get detailed information for a specific case.

        Args:
            page: Playwright page object
            case_number: The case number to get details for

        Returns:
            CourtSearchResult with full details, None if not found
        """
        self.logger.warning(f"Case details lookup not implemented for {self.state}")
        return None

    async def wait_between_requests(self) -> None:
        """Wait the configured delay between requests"""
        await asyncio.sleep(self.delay_ms / 1000)

    def classify_case_type(self, type_text: str) -> CaseType:
        """
        Classify case type from raw text.

        Args:
            type_text: Raw case type text from website

        Returns:
            CaseType enum value
        """
        type_lower = type_text.lower().strip()

        # Foreclosure cases
        if any(word in type_lower for word in ["foreclosure", "force", "fc"]):
            return CaseType.FORECLOSURE

        # Civil cases
        if any(word in type_lower for word in ["civil", "cv", "civ"]):
            return CaseType.CIVIL

        # Probate cases
        if any(word in type_lower for word in ["probate", "pr", "estate", "decedent"]):
            return CaseType.PROBATE

        # Domestic/Family cases
        if any(word in type_lower for word in ["domestic", "dr", "divorce", "family"]):
            return CaseType.DOMESTIC

        # Small claims
        if any(word in type_lower for word in ["small claim", "sc"]):
            return CaseType.SMALL_CLAIMS

        # Judgment-related
        if any(word in type_lower for word in ["judgment", "jdgmt"]):
            return CaseType.JUDGMENT

        return CaseType.OTHER

    def classify_case_status(self, status_text: str) -> CaseStatus:
        """
        Classify case status from raw text.

        Args:
            status_text: Raw status text from website

        Returns:
            CaseStatus enum value
        """
        status_lower = status_text.lower().strip()

        if any(word in status_lower for word in ["open", "active", "pending"]):
            return CaseStatus.OPEN

        if any(word in status_lower for word in ["closed", "disposed", "resolved"]):
            return CaseStatus.CLOSED

        if any(word in status_lower for word in ["dismiss", "withdrawn"]):
            return CaseStatus.DISMISSED

        return CaseStatus.UNKNOWN

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
            "%d-%b-%Y",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(date_text, fmt)
            except ValueError:
                continue

        self.logger.warning(f"Could not parse date: {date_text}")
        return None

    def parse_name_parts(self, full_name: str) -> tuple:
        """
        Parse a full name into last name and first name.

        Args:
            full_name: Full name string (various formats)

        Returns:
            Tuple of (last_name, first_name) or (full_name, None) if unparseable
        """
        if not full_name:
            return ("", None)

        full_name = full_name.strip()

        # Handle "LAST, FIRST" format
        if "," in full_name:
            parts = full_name.split(",", 1)
            return (parts[0].strip(), parts[1].strip() if len(parts) > 1 else None)

        # Handle "FIRST LAST" format - take last word as last name
        parts = full_name.split()
        if len(parts) >= 2:
            return (parts[-1], " ".join(parts[:-1]))

        return (full_name, None)

    def is_title_relevant_case(self, case: CourtSearchResult) -> bool:
        """
        Determine if a case is relevant to title search.

        Filters out domestic, traffic, and other non-title-affecting cases.

        Args:
            case: CourtSearchResult to evaluate

        Returns:
            bool: True if case may affect property title
        """
        # Always relevant case types
        relevant_types = [
            CaseType.FORECLOSURE,
            CaseType.CIVIL,
            CaseType.JUDGMENT,
            CaseType.LIS_PENDENS,
        ]

        if case.case_type in relevant_types:
            return True

        # Probate may be relevant if it involves property
        if case.case_type == CaseType.PROBATE:
            return True

        # Skip domestic and small claims by default
        # (could have judgment liens but less common for title issues)
        if case.case_type in [CaseType.DOMESTIC, CaseType.SMALL_CLAIMS]:
            return False

        return False

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
        filename = f"{screenshots_dir}/screenshots/court_{self.state}_{error_name}_{timestamp}.png"

        try:
            await page.screenshot(path=filename, full_page=True)
            self.logger.info(f"Saved error screenshot: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Failed to save screenshot: {e}")
            return ""
