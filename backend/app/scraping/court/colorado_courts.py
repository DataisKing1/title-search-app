"""Colorado Judicial Branch court records adapter"""
from playwright.async_api import Page
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import re

from app.scraping.court.base_court_adapter import (
    BaseCourtAdapter,
    CourtSearchResult,
    CaseType,
    CaseStatus,
)


class ColoradoCourtsAdapter(BaseCourtAdapter):
    """
    Adapter for Colorado Judicial Branch court records.

    Portal: https://www.coloradojudicial.gov/dockets

    Search Types:
        - Individual (by first name / last name)
        - Business (by business name)
        - Case Number

    Court Types:
        - District Court (civil, foreclosure, probate)
        - County Court (small claims, civil)

    Case Classes (relevant to title):
        - CV: Civil
        - CW: Civil Water
        - DR: Domestic Relations (less relevant but may have judgments)
        - JD: Juvenile Delinquency (not relevant)
        - PR: Probate
    """

    BASE_URL = "https://www.coloradojudicial.gov"
    DOCKET_SEARCH_URL = f"{BASE_URL}/dockets"

    # Case classes relevant to title search
    RELEVANT_CASE_CLASSES = ["CV", "CW", "PR"]

    # County name to judicial district mapping (partial - key counties)
    COUNTY_DISTRICTS = {
        "adams": "17th",
        "arapahoe": "18th",
        "boulder": "20th",
        "denver": "2nd",
        "douglas": "18th",
        "el paso": "4th",
        "jefferson": "1st",
        "larimer": "8th",
        "weld": "19th",
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.state = "CO"
        self.base_url = self.DOCKET_SEARCH_URL

    async def initialize(self, page: Page) -> bool:
        """Navigate to docket search page and prepare for searches"""
        try:
            self.logger.info("Initializing Colorado Courts adapter")

            # Navigate to docket search
            await page.goto(self.DOCKET_SEARCH_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Wait for the search form to load
            form_loaded = await page.locator("input[placeholder*='Last Name'], input[name*='lastName']").count() > 0

            if not form_loaded:
                # Try waiting a bit more
                await asyncio.sleep(3)
                form_loaded = await page.locator("input, select").count() > 5

            if form_loaded:
                self.logger.info("Colorado Courts adapter initialized successfully")
                return True
            else:
                self.logger.error("Search form not found on page")
                await self.screenshot_on_error(page, "init_form_not_found")
                return False

        except Exception as e:
            self.logger.error(f"Failed to initialize Colorado Courts adapter: {e}")
            await self.screenshot_on_error(page, "init_error")
            return False

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
        Search Colorado court records by party name.

        Args:
            page: Playwright page object
            last_name: Party's last name (required)
            first_name: Party's first name (optional)
            start_date: Optional start date filter
            end_date: Optional end date filter
            county: Optional county name to filter

        Returns:
            List of CourtSearchResult objects
        """
        results = []

        try:
            self.logger.info(f"Searching Colorado courts for: {last_name}, {first_name or ''}")

            # Navigate to search page if not already there
            if "dockets" not in page.url.lower():
                await page.goto(self.DOCKET_SEARCH_URL, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

            # Click reset button to clear any previous search
            reset_btn = page.locator("#edit-reset")
            if await reset_btn.count() > 0:
                await reset_btn.click()
                await asyncio.sleep(1)

            # Select "Individual" radio button to show name fields
            individual_radio = page.locator("#edit-name-type-individual")
            if await individual_radio.count() > 0:
                await individual_radio.click()
                await asyncio.sleep(0.5)

            # Fill in the last name (required)
            last_name_input = page.locator("#edit-last-name")
            if await last_name_input.count() > 0:
                await last_name_input.fill(last_name)
            else:
                self.logger.error("Last name input field not found")
                return results

            # Fill in first name if provided
            if first_name:
                first_name_input = page.locator("#edit-first-name")
                if await first_name_input.count() > 0:
                    await first_name_input.fill(first_name)

            # Select court type - prefer "Both" for comprehensive search
            court_select = page.locator("#edit-court")
            if await court_select.count() > 0:
                try:
                    await court_select.select_option(value="Both")
                except Exception:
                    self.logger.debug("Could not set court type to Both")

            # Select county if specified
            if county:
                county_select = page.locator("#edit-county")
                if await county_select.count() > 0:
                    # Map common county names to their option values
                    county_values = {
                        "denver": "16",  # Denver - District
                        "adams": "1",
                        "arapahoe": "3",
                        "boulder": "7",
                        "douglas": "18",
                        "el paso": "21",
                        "jefferson": "27",
                        "larimer": "35",
                        "weld": "64",
                    }
                    county_lower = county.lower().strip()
                    value = county_values.get(county_lower)

                    if value:
                        try:
                            await county_select.select_option(value=value)
                        except Exception as e:
                            self.logger.warning(f"Could not select county {county}: {e}")
                    else:
                        # Try by label
                        try:
                            await county_select.select_option(label=f"{county.title()} County")
                        except Exception:
                            self.logger.warning(f"Could not select county: {county}")

            # Set date range - use 6 Months for broader search
            date_range_select = page.locator("#edit-date-range")
            if await date_range_select.count() > 0:
                try:
                    await date_range_select.select_option(label="6 Months")
                except Exception:
                    self.logger.debug("Could not set date range")

            # Click search/submit button
            submit_btn = page.locator("#edit-submit")
            if await submit_btn.count() > 0:
                await submit_btn.click()
            else:
                self.logger.error("Submit button not found")
                return results

            # Wait for results to load
            await asyncio.sleep(3)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass  # Continue even if networkidle times out

            # Check for "no results" message
            no_results = page.locator(
                "text=No results found, "
                "text=No records found, "
                "text=No matching dockets, "
                ".view-empty, "
                ".no-results"
            )
            if await no_results.count() > 0:
                self.logger.info(f"No court records found for {last_name}")
                return results

            # Parse results
            results = await self._parse_search_results(page, county)

            # Handle pagination
            page_num = 1
            while await self._has_next_page(page) and page_num < 5:  # Max 5 pages
                await self._go_to_next_page(page)
                await asyncio.sleep(2)
                page_results = await self._parse_search_results(page, county)
                results.extend(page_results)
                page_num += 1
                await self.wait_between_requests()

            self.logger.info(f"Found {len(results)} court records for {last_name}")

        except Exception as e:
            self.logger.error(f"Colorado court search failed: {e}")
            await self.screenshot_on_error(page, f"search_error_{last_name}")

        return results

    async def search_by_business_name(
        self,
        page: Page,
        business_name: str,
        county: Optional[str] = None
    ) -> List[CourtSearchResult]:
        """
        Search Colorado court records by business name.

        Args:
            page: Playwright page object
            business_name: Business entity name
            county: Optional county filter

        Returns:
            List of CourtSearchResult objects
        """
        results = []

        try:
            self.logger.info(f"Searching Colorado courts for business: {business_name}")

            # Navigate to search page
            if "dockets" not in page.url.lower():
                await page.goto(self.DOCKET_SEARCH_URL, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(2)

            # Find and fill business name input
            business_input = page.locator(
                "input[placeholder*='Business'], "
                "input[name*='businessName'], "
                "input[id*='businessName'], "
                "input[aria-label*='Business']"
            ).first

            if await business_input.count() > 0:
                await business_input.fill(business_name)
            else:
                # Fall back to last name search with business name
                self.logger.warning("Business name field not found, using last name field")
                last_name_input = page.locator("input[placeholder*='Last Name']").first
                if await last_name_input.count() > 0:
                    await last_name_input.fill(business_name)

            # Select county if specified
            if county:
                county_select = page.locator("select[name*='county']")
                if await county_select.count() > 0:
                    try:
                        await county_select.select_option(label=county.title())
                    except Exception:
                        pass

            # Click search
            search_btn = page.locator("button:has-text('Search'), button[type='submit']").first
            if await search_btn.count() > 0:
                await search_btn.click()

            await asyncio.sleep(3)
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Parse results
            results = await self._parse_search_results(page, county)

            self.logger.info(f"Found {len(results)} court records for business: {business_name}")

        except Exception as e:
            self.logger.error(f"Business name search failed: {e}")
            await self.screenshot_on_error(page, f"business_search_error")

        return results

    async def _parse_search_results(
        self,
        page: Page,
        county_filter: Optional[str] = None
    ) -> List[CourtSearchResult]:
        """
        Parse search results from the docket table.

        Colorado Judicial Branch returns a table with columns:
        - Date, Time, Name, Case Number, Hearing Type

        Args:
            page: Playwright page object
            county_filter: Optional county to filter results

        Returns:
            List of CourtSearchResult objects
        """
        results = []
        seen_cases = set()  # Dedupe by case number

        try:
            # Find the main results table
            table = page.locator("table")
            if await table.count() == 0:
                self.logger.debug("No results table found")
                return results

            # Get all data rows (skip header)
            rows = table.locator("tbody tr")
            row_count = await rows.count()
            self.logger.debug(f"Found {row_count} result rows")

            # Limit to first 100 unique cases to avoid overwhelming results
            for i in range(min(row_count, 500)):
                try:
                    row = rows.nth(i)
                    cells = await row.locator("td").all()

                    if len(cells) < 4:
                        continue

                    # Extract cell contents
                    # Columns: Date, Time, Name, Case Number, Hearing Type
                    date_text = (await cells[0].inner_text()).strip()
                    name_text = (await cells[2].inner_text()).strip() if len(cells) > 2 else ""
                    case_number = (await cells[3].inner_text()).strip() if len(cells) > 3 else ""
                    hearing_type = (await cells[4].inner_text()).strip() if len(cells) > 4 else ""

                    # Clean up case number
                    case_number = case_number.replace("\n", "").replace("\t", "").strip()

                    # Skip if no case number or already seen
                    if not case_number or case_number in seen_cases:
                        continue

                    # Extract date (format: M/D/YYYY)
                    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_text)
                    filing_date = self.parse_date(date_match.group(1)) if date_match else None

                    # Determine case type from case number prefix
                    case_type = self._extract_case_type_from_number(case_number)

                    # Skip non-title-relevant case types early
                    if case_type not in [CaseType.CIVIL, CaseType.FORECLOSURE, CaseType.PROBATE, CaseType.JUDGMENT]:
                        continue

                    seen_cases.add(case_number)

                    # Clean up name
                    name_text = name_text.replace("\n", "").strip()
                    parties = [name_text] if name_text else []

                    # Get case URL if available
                    case_link = row.locator("a").first
                    case_url = None
                    if await case_link.count() > 0:
                        href = await case_link.get_attribute("href")
                        if href and "/case/" in href:
                            case_url = f"{self.BASE_URL}{href}" if not href.startswith("http") else href

                    result = CourtSearchResult(
                        case_number=case_number,
                        case_type=case_type,
                        court_name="Denver District Court" if county_filter and "denver" in county_filter.lower() else "Colorado Courts",
                        filing_date=filing_date,
                        parties=parties,
                        status=CaseStatus.OPEN,  # Docket entries are for open/active cases
                        county=county_filter or "Colorado",
                        case_url=case_url,
                        description=hearing_type,
                        raw_data={"date": date_text, "name": name_text, "hearing": hearing_type}
                    )

                    results.append(result)

                    # Limit to 50 unique relevant cases
                    if len(results) >= 50:
                        break

                except Exception as e:
                    self.logger.debug(f"Failed to parse result row {i}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to parse search results: {e}")

        return results

    def _extract_case_type_from_number(self, case_number: str) -> CaseType:
        """
        Extract case type from Colorado case number format.

        Colorado case numbers use prefixes like:
        - CV: Civil
        - CR: Criminal
        - DR: Domestic Relations
        - PR: Probate
        - JV/JD: Juvenile
        - M: Misdemeanor
        - T: Traffic
        """
        case_upper = case_number.upper()

        # Civil cases (most relevant for title)
        if "CV" in case_upper or case_upper.startswith("CV"):
            return CaseType.CIVIL

        # Probate (can affect title through estates)
        if "PR" in case_upper:
            return CaseType.PROBATE

        # Domestic relations (may have property divisions)
        if "DR" in case_upper:
            return CaseType.DOMESTIC

        # Criminal - usually not title relevant
        if "CR" in case_upper:
            return CaseType.OTHER

        # Misdemeanor/Traffic - not title relevant
        if case_upper.startswith("M") or case_upper.startswith("T") or "MJ" in case_upper:
            return CaseType.OTHER

        # Juvenile - not title relevant
        if "JV" in case_upper or "JD" in case_upper:
            return CaseType.OTHER

        return CaseType.OTHER

    def _extract_case_type(self, text: str, case_number: str) -> CaseType:
        """Extract case type from text or case number"""
        text_lower = text.lower()

        # Check case number for type code
        if "-cv-" in case_number.lower() or case_number.upper().startswith("CV"):
            return CaseType.CIVIL

        # Check text for keywords
        if "foreclosure" in text_lower:
            return CaseType.FORECLOSURE
        if "probate" in text_lower or "-pr-" in case_number.lower():
            return CaseType.PROBATE
        if "domestic" in text_lower or "-dr-" in case_number.lower():
            return CaseType.DOMESTIC
        if "small claim" in text_lower or "-sc-" in case_number.lower():
            return CaseType.SMALL_CLAIMS
        if "civil" in text_lower:
            return CaseType.CIVIL

        return CaseType.OTHER

    def _extract_parties(self, text: str) -> List[str]:
        """Extract party names from result text"""
        parties = []

        # Look for "v." or "vs" pattern
        vs_match = re.search(r'([A-Z][A-Za-z\s,]+)\s+(?:v\.|vs\.?)\s+([A-Z][A-Za-z\s,]+)', text)
        if vs_match:
            parties.append(vs_match.group(1).strip())
            parties.append(vs_match.group(2).strip())
            return parties

        # Look for party labels
        plaintiff_match = re.search(r'Plaintiff[:\s]+([A-Za-z\s,]+?)(?:\s+Defendant|\s*$)', text, re.IGNORECASE)
        if plaintiff_match:
            parties.append(plaintiff_match.group(1).strip())

        defendant_match = re.search(r'Defendant[:\s]+([A-Za-z\s,]+)', text, re.IGNORECASE)
        if defendant_match:
            parties.append(defendant_match.group(1).strip())

        return parties

    def _extract_court_name(self, text: str) -> str:
        """Extract court name from result text"""
        # Look for court patterns
        court_match = re.search(
            r'((?:\d+(?:st|nd|rd|th)\s+)?(?:District|County)\s+Court[^,]*)',
            text,
            re.IGNORECASE
        )
        if court_match:
            return court_match.group(1).strip()

        return "Colorado Courts"

    def _extract_county(self, text: str, court_name: str) -> Optional[str]:
        """Extract county from result text or court name"""
        # List of Colorado counties to match
        counties = [
            "Adams", "Alamosa", "Arapahoe", "Archuleta", "Baca", "Bent", "Boulder",
            "Broomfield", "Chaffee", "Cheyenne", "Clear Creek", "Conejos", "Costilla",
            "Crowley", "Custer", "Delta", "Denver", "Dolores", "Douglas", "Eagle",
            "El Paso", "Elbert", "Fremont", "Garfield", "Gilpin", "Grand", "Gunnison",
            "Hinsdale", "Huerfano", "Jackson", "Jefferson", "Kiowa", "Kit Carson",
            "La Plata", "Lake", "Larimer", "Las Animas", "Lincoln", "Logan", "Mesa",
            "Mineral", "Moffat", "Montezuma", "Montrose", "Morgan", "Otero", "Ouray",
            "Park", "Phillips", "Pitkin", "Prowers", "Pueblo", "Rio Blanco",
            "Rio Grande", "Routt", "Saguache", "San Juan", "San Miguel", "Sedgwick",
            "Summit", "Teller", "Washington", "Weld", "Yuma"
        ]

        combined_text = f"{text} {court_name}"

        for county in counties:
            if county.lower() in combined_text.lower():
                return county

        return None

    def _extract_status(self, text: str) -> CaseStatus:
        """Extract case status from text"""
        text_lower = text.lower()

        if any(word in text_lower for word in ["open", "active", "pending"]):
            return CaseStatus.OPEN
        if any(word in text_lower for word in ["closed", "disposed", "resolved", "final"]):
            return CaseStatus.CLOSED
        if any(word in text_lower for word in ["dismiss", "withdrawn"]):
            return CaseStatus.DISMISSED

        return CaseStatus.UNKNOWN

    async def _has_next_page(self, page: Page) -> bool:
        """Check if there's a next page of results"""
        try:
            next_btn = page.locator(
                "a:has-text('Next'), "
                "button:has-text('Next'), "
                ".pagination-next:not(.disabled), "
                "a[rel='next']"
            )

            if await next_btn.count() > 0:
                # Check if not disabled
                first_btn = next_btn.first
                is_disabled = await first_btn.is_disabled()
                classes = await first_btn.get_attribute("class") or ""

                if not is_disabled and "disabled" not in classes:
                    return True

        except Exception as e:
            self.logger.debug(f"Next page check failed: {e}")

        return False

    async def _go_to_next_page(self, page: Page):
        """Navigate to the next page of results"""
        try:
            next_btn = page.locator(
                "a:has-text('Next'), "
                "button:has-text('Next'), "
                "a[rel='next']"
            ).first

            if await next_btn.count() > 0:
                await next_btn.click()
                await page.wait_for_load_state("networkidle", timeout=10000)

        except Exception as e:
            self.logger.error(f"Failed to go to next page: {e}")

    async def check_health(self) -> bool:
        """Check if the Colorado Courts portal is accessible."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.DOCKET_SEARCH_URL,
                    follow_redirects=True,
                    timeout=30
                )
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
