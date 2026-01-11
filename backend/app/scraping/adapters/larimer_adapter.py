"""Larimer County Clerk & Recorder adapter for Landmark Web system"""
from playwright.async_api import Page
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import os
import hashlib

from app.scraping.base_adapter import BaseCountyAdapter, SearchResult, DownloadedDocument
from app.scraping.adapters import register_adapter


@register_adapter("larimer")
class LarimerCountyAdapter(BaseCountyAdapter):
    """
    Adapter for Larimer County Clerk & Recorder - Landmark Web system.

    Portal: https://records.larimer.org/landmarkweb
    System: Landmark Web Official Records Search

    Search Types:
        - Name Search: Search by grantor/grantee names
        - Reception Number Search: Search by instrument/reception number
        - Book and Page Search: Search by book/page reference
        - Record Date Search: Search by date range
        - Document Search: Search by document type
        - Legal Search: Search by legal description
        - Consideration Search: Search by transaction value

    Notes:
        - Searchable indexing available online from 1971 to present
        - Registration required for watermarked image viewing
        - Unwatermarked images require purchase
    """

    BASE_URL = "https://records.larimer.org/landmarkweb"

    # Search page URLs
    SEARCH_URLS = {
        "name": f"{BASE_URL}/Search/NameSearch.aspx",
        "reception": f"{BASE_URL}/Search/ReceptionSearch.aspx",
        "book_page": f"{BASE_URL}/Search/BookPageSearch.aspx",
        "date": f"{BASE_URL}/Search/RecordDateSearch.aspx",
        "document": f"{BASE_URL}/Search/DocumentSearch.aspx",
        "legal": f"{BASE_URL}/Search/LegalSearch.aspx",
    }

    # CSS selectors for form elements
    SELECTORS = {
        # Name Search
        "name_input": "#txtName, input[id*='txtName'], input[name*='Name']",
        "name_type": "#ddlNameType, select[id*='NameType']",

        # Reception Number Search
        "reception_from": "#txtReceptionFrom, input[id*='ReceptionFrom']",
        "reception_to": "#txtReceptionTo, input[id*='ReceptionTo']",

        # Date fields
        "date_from": "#txtDateFrom, input[id*='DateFrom']",
        "date_to": "#txtDateTo, input[id*='DateTo']",

        # Book/Page
        "book": "#txtBook, input[id*='Book']",
        "page": "#txtPage, input[id*='Page']",

        # Common buttons
        "search_button": "#btnSearch, input[value='Search'], button:has-text('Search')",
        "clear_button": "#btnClear, input[value='Clear'], button:has-text('Clear')",

        # Results
        "result_table": "#grdResults, table.results, .datagrid",
        "result_row": "#grdResults tr, table.results tr, .datagrid tr",
        "no_results": "text=/no records|no results|0 records/i",

        # Disclaimer
        "accept_disclaimer": "#btnAccept, input[value*='Accept'], button:has-text('Accept')",
    }

    # Document type codes
    DOC_TYPES = {
        "deed": ["DEED", "WD", "QCD", "SWD", "SPWD", "BD", "COD"],
        "mortgage": ["MORT", "DTD", "TD", "DOT", "DT"],
        "release": ["REL", "RELS", "RELDOT", "RELMORT"],
        "lien": ["LIEN", "ML", "FTL", "STL", "JL", "MTL"],
        "easement": ["EASE", "ESMT", "EAS"],
        "plat": ["PLAT", "SURVEY", "SUR"],
        "assignment": ["ASGN", "AOT", "AODOT"],
        "lis_pendens": ["LP", "NLP", "NLISP"],
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.county_name = "Larimer"
        self._initialized = False

    async def initialize(self, page: Page) -> bool:
        """Navigate to search portal and accept disclaimer"""
        try:
            self.logger.info("Initializing Larimer County Landmark Web adapter")

            # Navigate to the main portal
            await page.goto(self.BASE_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Accept disclaimer if present
            await self._accept_disclaimer(page)

            # Verify we're on the search interface
            await asyncio.sleep(1)

            # Check if we can access any search functionality
            content = await page.content()
            if "Search" in content or "landmarkweb" in page.url.lower():
                self._initialized = True
                self.logger.info("Larimer County adapter initialized successfully")
                return True
            else:
                self.logger.error("Could not verify search interface access")
                return False

        except Exception as e:
            self.logger.error(f"Failed to initialize Larimer adapter: {e}")
            await self.screenshot_on_error(page, "larimer_init_error")
            return False

    async def _accept_disclaimer(self, page: Page):
        """Accept the disclaimer if present"""
        try:
            # Look for accept button
            accept_selectors = [
                "#btnAccept",
                "input[value*='Accept']",
                "button:has-text('Accept')",
                "a:has-text('Accept')",
                "input[type='button'][value*='I Accept']",
            ]

            for selector in accept_selectors:
                try:
                    accept_btn = page.locator(selector)
                    if await accept_btn.count() > 0:
                        await accept_btn.first.click()
                        self.logger.info("Accepted disclaimer")
                        await asyncio.sleep(2)
                        await page.wait_for_load_state("networkidle")
                        return
                except:
                    continue

            self.logger.debug("No disclaimer found or already accepted")

        except Exception as e:
            self.logger.debug(f"Disclaimer handling: {e}")

    async def _navigate_to_search(self, page: Page, search_type: str):
        """Navigate to the appropriate search page"""
        url = self.SEARCH_URLS.get(search_type, self.SEARCH_URLS["name"])

        if page.url != url:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(1)
            # Re-accept disclaimer if needed
            await self._accept_disclaimer(page)

    async def search_by_name(
        self,
        page: Page,
        name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """Search Larimer County records by grantor/grantee name"""
        results = []

        try:
            self.logger.info(f"Searching Larimer County by name: {name}")

            # Navigate to name search
            await self._navigate_to_search(page, "name")
            await asyncio.sleep(1)

            # Find and fill name input
            name_input = page.locator(self.SELECTORS["name_input"]).first
            if await name_input.count() == 0:
                # Try finding any text input
                name_input = page.locator("input[type='text']").first

            if await name_input.count() > 0:
                await name_input.fill(name)
                self.logger.debug(f"Entered name: {name}")
            else:
                self.logger.error("Could not find name input field")
                return results

            # Set date range if provided
            if start_date:
                date_from = page.locator(self.SELECTORS["date_from"]).first
                if await date_from.count() > 0:
                    await date_from.fill(start_date.strftime("%m/%d/%Y"))

            if end_date:
                date_to = page.locator(self.SELECTORS["date_to"]).first
                if await date_to.count() > 0:
                    await date_to.fill(end_date.strftime("%m/%d/%Y"))

            # Click search button
            await self._click_search(page)
            await asyncio.sleep(3)

            # Parse results
            results = await self._parse_search_results(page)

            # Handle pagination
            page_num = 1
            while await self._has_next_page(page) and page_num < 10:
                await self._go_to_next_page(page)
                await asyncio.sleep(1)
                page_results = await self._parse_search_results(page)
                results.extend(page_results)
                page_num += 1
                await self.wait_between_requests()

            self.logger.info(f"Found {len(results)} documents for name '{name}'")

        except Exception as e:
            self.logger.error(f"Larimer name search failed: {e}")
            await self.screenshot_on_error(page, "larimer_name_search_error")

        return results

    async def search_by_instrument(
        self,
        page: Page,
        instrument_number: str
    ) -> List[SearchResult]:
        """Search Larimer County records by reception/instrument number"""
        results = []

        try:
            self.logger.info(f"Searching Larimer County by instrument: {instrument_number}")

            # Navigate to reception number search
            await self._navigate_to_search(page, "reception")
            await asyncio.sleep(1)

            # Find and fill reception number input
            reception_input = page.locator(self.SELECTORS["reception_from"]).first
            if await reception_input.count() == 0:
                reception_input = page.locator("input[type='text']").first

            if await reception_input.count() > 0:
                await reception_input.fill(instrument_number)

                # Also fill the "to" field with same number for exact match
                reception_to = page.locator(self.SELECTORS["reception_to"]).first
                if await reception_to.count() > 0:
                    await reception_to.fill(instrument_number)
            else:
                self.logger.error("Could not find reception number input")
                return results

            # Click search
            await self._click_search(page)
            await asyncio.sleep(2)

            # Parse results
            results = await self._parse_search_results(page)
            self.logger.info(f"Found {len(results)} documents for instrument '{instrument_number}'")

        except Exception as e:
            self.logger.error(f"Larimer instrument search failed: {e}")
            await self.screenshot_on_error(page, "larimer_instrument_search_error")

        return results

    async def search_by_parcel(
        self,
        page: Page,
        parcel_number: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """Search Larimer County records by parcel/legal description"""
        self.logger.info(f"Parcel search requested for: {parcel_number}")
        self.logger.warning("Larimer County Landmark Web requires legal description search. "
                          "Consider looking up owner name from assessor first.")
        return []

    async def _click_search(self, page: Page):
        """Click the search button"""
        try:
            search_selectors = [
                "#btnSearch",
                "input[value='Search']",
                "input[type='submit'][value*='Search']",
                "button:has-text('Search')",
                "input[type='button'][value*='Search']",
            ]

            for selector in search_selectors:
                try:
                    search_btn = page.locator(selector)
                    if await search_btn.count() > 0:
                        await search_btn.first.click()
                        self.logger.debug("Clicked search button")
                        await page.wait_for_load_state("networkidle")
                        return
                except:
                    continue

            self.logger.warning("Could not find search button")

        except Exception as e:
            self.logger.error(f"Failed to click search: {e}")

    async def _parse_search_results(self, page: Page) -> List[SearchResult]:
        """Parse search results from the results table"""
        results = []

        try:
            # Wait for results to load
            await asyncio.sleep(1)

            # Check for no results message
            no_results = page.locator("text=/no records|no results|0 records found/i")
            if await no_results.count() > 0:
                self.logger.debug("No results found")
                return results

            # Find the results table
            table_selectors = [
                "#grdResults",
                "table.results",
                "table.datagrid",
                "table[id*='Results']",
                "table[id*='Grid']",
            ]

            result_table = None
            for selector in table_selectors:
                table = page.locator(selector)
                if await table.count() > 0:
                    result_table = table
                    break

            if not result_table:
                # Try finding any table with data rows
                tables = page.locator("table")
                for i in range(await tables.count()):
                    table = tables.nth(i)
                    rows = table.locator("tr")
                    if await rows.count() > 2:  # Header + at least one data row
                        result_table = table
                        break

            if not result_table:
                self.logger.debug("No results table found")
                return results

            # Get all rows
            rows = result_table.locator("tr")
            row_count = await rows.count()
            self.logger.debug(f"Found {row_count} rows in results table")

            seen_instruments = set()

            # Skip header row, parse data rows
            for i in range(1, row_count):
                try:
                    row = rows.nth(i)
                    cells = row.locator("td")
                    cell_count = await cells.count()

                    if cell_count < 4:
                        continue

                    # Extract cell text
                    cell_texts = []
                    for j in range(cell_count):
                        text = await cells.nth(j).inner_text()
                        cell_texts.append(text.strip())

                    # Parse based on common Landmark Web column order:
                    # Reception#, Book/Page, DocType, RecordDate, Grantor, Grantee, Legal
                    reception_num = ""
                    doc_type = ""
                    recording_date = None
                    grantor = ""
                    grantee = ""

                    # Find reception/instrument number (usually first column with digits)
                    for text in cell_texts:
                        clean = text.replace("-", "").replace(" ", "")
                        if clean.isdigit() and len(clean) >= 6:
                            reception_num = text.strip()
                            break

                    if not reception_num or reception_num in seen_instruments:
                        continue

                    seen_instruments.add(reception_num)

                    # Find date (MM/DD/YYYY pattern)
                    import re
                    for text in cell_texts:
                        if re.match(r'\d{1,2}/\d{1,2}/\d{4}', text):
                            recording_date = self.parse_date(text)
                            break

                    # Find document type (usually a 2-4 letter code)
                    for text in cell_texts:
                        if len(text) >= 2 and len(text) <= 10 and text.isupper():
                            doc_type = text
                            break

                    # Names are usually in specific columns after doc type
                    if len(cell_texts) > 4:
                        # Try to identify grantor/grantee columns
                        for j, text in enumerate(cell_texts):
                            if j > 2 and text and not text.isdigit():
                                if not grantor and "/" not in text:
                                    grantor = text
                                elif not grantee and "/" not in text:
                                    grantee = text
                                    break

                    result = SearchResult(
                        instrument_number=reception_num,
                        document_type=self.classify_document_type(doc_type),
                        recording_date=recording_date,
                        grantor=[grantor] if grantor else [],
                        grantee=[grantee] if grantee else [],
                        download_url="",  # Will need to click into detail page
                        source_county="Larimer",
                        raw_data={
                            "doc_type_raw": doc_type,
                            "cell_texts": cell_texts
                        }
                    )
                    results.append(result)

                except Exception as e:
                    self.logger.debug(f"Failed to parse row {i}: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to parse search results: {e}")

        return results

    async def _has_next_page(self, page: Page) -> bool:
        """Check if there's a next page of results"""
        try:
            next_selectors = [
                "a:has-text('Next')",
                "a:has-text('>')",
                "input[value='Next']",
                ".pagination-next:not(.disabled)",
            ]

            for selector in next_selectors:
                next_btn = page.locator(selector)
                if await next_btn.count() > 0:
                    # Check if it's not disabled
                    classes = await next_btn.first.get_attribute("class") or ""
                    if "disabled" not in classes:
                        return True

        except Exception as e:
            self.logger.debug(f"Next page check failed: {e}")

        return False

    async def _go_to_next_page(self, page: Page):
        """Navigate to the next page of results"""
        try:
            next_selectors = [
                "a:has-text('Next')",
                "a:has-text('>')",
                "input[value='Next']",
            ]

            for selector in next_selectors:
                next_btn = page.locator(selector)
                if await next_btn.count() > 0:
                    await next_btn.first.click()
                    await page.wait_for_load_state("networkidle")
                    return

        except Exception as e:
            self.logger.error(f"Failed to go to next page: {e}")

    async def download_document(
        self,
        page: Page,
        result: SearchResult,
        download_path: str
    ) -> Optional[DownloadedDocument]:
        """Download a document from Larimer County"""
        try:
            if not result.instrument_number:
                return None

            self.logger.info(f"Downloading document: {result.instrument_number}")
            os.makedirs(download_path, exist_ok=True)

            # First, search for the document to get to its detail page
            await self.search_by_instrument(page, result.instrument_number)
            await asyncio.sleep(2)

            # Click on the document row to view details
            doc_link = page.locator(f"text='{result.instrument_number}'").first
            if await doc_link.count() > 0:
                await doc_link.click()
                await asyncio.sleep(3)

            # Look for image/download link
            download_selectors = [
                "a:has-text('View Image')",
                "a:has-text('Download')",
                "a[href*='ViewImage']",
                "a[href*='GetDocument']",
                "img[alt*='View']",
            ]

            for selector in download_selectors:
                download_link = page.locator(selector)
                if await download_link.count() > 0:
                    # Handle download
                    async with page.expect_download(timeout=60000) as download_info:
                        await download_link.first.click()

                    download = await download_info.value
                    filename = f"{result.instrument_number}.pdf"
                    file_path = os.path.join(download_path, filename)
                    await download.save_as(file_path)

                    file_size = os.path.getsize(file_path)
                    with open(file_path, "rb") as f:
                        content_hash = hashlib.sha256(f.read()).hexdigest()

                    self.logger.info(f"Downloaded: {file_path} ({file_size} bytes)")

                    return DownloadedDocument(
                        file_path=file_path,
                        file_name=filename,
                        file_size=file_size,
                        mime_type="application/pdf",
                        content_hash=content_hash,
                        instrument_number=result.instrument_number
                    )

            self.logger.warning(f"Could not find download link for {result.instrument_number}")
            self.logger.warning("Note: Larimer County may require registration to view images")

        except Exception as e:
            self.logger.error(f"Document download failed for {result.instrument_number}: {e}")
            await self.screenshot_on_error(page, f"download_error_{result.instrument_number}")

        return None

    async def check_health(self) -> bool:
        """Check if the Larimer County portal is accessible."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.BASE_URL,
                    follow_redirects=True,
                    timeout=30
                )
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
