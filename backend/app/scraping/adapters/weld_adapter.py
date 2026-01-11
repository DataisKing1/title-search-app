"""Weld County Clerk & Recorder adapter for Weld County Recording system"""
from playwright.async_api import Page
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import os
import hashlib

from app.scraping.base_adapter import BaseCountyAdapter, SearchResult, DownloadedDocument
from app.scraping.adapters import register_adapter


@register_adapter("weld")
class WeldCountyAdapter(BaseCountyAdapter):
    """
    Adapter for Weld County Clerk & Recorder.

    Portal: https://recording.weld.gov/web/user/disclaimer
    Alternate: https://cmtcm.co.weld.co.us/
    System: Custom Weld County Recording System

    Search Types:
        - Name Search: Search by grantor/grantee names
        - Document Number Search: Search by reception/instrument number
        - Book and Page Search: Search by book/page reference
        - Date Range Search: Search by recording date

    Notes:
        - Documents searchable from January 1, 1865
        - Maps available back to 1865
        - Automated searches are prohibited
        - Index is a guide to document information, search all variations
    """

    BASE_URL = "https://recording.weld.gov/web/user/disclaimer"
    SEARCH_URL = "https://recording.weld.gov/web/user/search"
    ALTERNATE_URL = "https://cmtcm.co.weld.co.us/"

    # CSS selectors for form elements
    SELECTORS = {
        # Search fields
        "name_input": "input[name*='name'], input[id*='name'], input[placeholder*='name' i]",
        "first_name": "input[name*='first'], input[id*='firstName']",
        "last_name": "input[name*='last'], input[id*='lastName']",

        # Document/Reception number
        "doc_number": "input[name*='docNum'], input[id*='docNumber'], input[name*='reception']",

        # Date fields
        "date_from": "input[name*='dateFrom'], input[id*='startDate'], input[name*='fromDate']",
        "date_to": "input[name*='dateTo'], input[id*='endDate'], input[name*='toDate']",

        # Book/Page
        "book": "input[name*='book'], input[id*='book']",
        "page": "input[name*='page'], input[id*='page']",

        # Buttons
        "search_button": "button[type='submit'], input[value='Search'], button:has-text('Search')",
        "clear_button": "button:has-text('Clear'), input[value='Clear']",

        # Disclaimer
        "accept_disclaimer": "button:has-text('Accept'), button:has-text('I Agree'), input[value*='Accept']",

        # Results
        "result_table": "table.results, table[id*='results'], .search-results table",
        "result_row": "table tbody tr",
        "no_results": "text=/no records|no results|0 records|no documents/i",
    }

    # Document type codes
    DOC_TYPES = {
        "deed": ["DEED", "WD", "QCD", "SWD", "SPWD", "BD", "COD", "D"],
        "mortgage": ["MORT", "DTD", "TD", "DOT", "DT", "M"],
        "release": ["REL", "RELS", "RELDOT", "RELMORT", "R"],
        "lien": ["LIEN", "ML", "FTL", "STL", "JL", "MTL", "L"],
        "easement": ["EASE", "ESMT", "EAS", "E"],
        "plat": ["PLAT", "SURVEY", "SUR", "MAP", "P"],
        "assignment": ["ASGN", "AOT", "AODOT", "A"],
        "lis_pendens": ["LP", "NLP", "NLISP"],
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.county_name = "Weld"
        self._initialized = False

    async def initialize(self, page: Page) -> bool:
        """Navigate to search portal and accept disclaimer"""
        try:
            self.logger.info("Initializing Weld County adapter")

            # Try primary portal first
            await page.goto(self.BASE_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Accept disclaimer
            await self._accept_disclaimer(page)

            # Check if we're on the search interface
            await asyncio.sleep(1)

            # Verify access
            content = await page.content()
            if "search" in content.lower() or "weld" in page.url.lower():
                self._initialized = True
                self.logger.info("Weld County adapter initialized successfully")
                return True

            # Try alternate URL if primary fails
            self.logger.info("Trying alternate Weld County portal...")
            await page.goto(self.ALTERNATE_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            await self._accept_disclaimer(page)

            content = await page.content()
            if "search" in content.lower():
                self._initialized = True
                self.logger.info("Weld County adapter initialized via alternate portal")
                return True

            self.logger.error("Could not verify search interface access")
            return False

        except Exception as e:
            self.logger.error(f"Failed to initialize Weld adapter: {e}")
            await self.screenshot_on_error(page, "weld_init_error")
            return False

    async def _accept_disclaimer(self, page: Page):
        """Accept the disclaimer if present"""
        try:
            accept_selectors = [
                "button:has-text('Accept')",
                "button:has-text('I Agree')",
                "button:has-text('I Accept')",
                "input[value*='Accept']",
                "a:has-text('Accept')",
                "button[type='submit']",
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

    async def search_by_name(
        self,
        page: Page,
        name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """Search Weld County records by grantor/grantee name"""
        results = []

        try:
            self.logger.info(f"Searching Weld County by name: {name}")

            # Ensure we're on the search page
            if "search" not in page.url.lower():
                await page.goto(self.SEARCH_URL, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(1)
                await self._accept_disclaimer(page)

            # Try to find name input field
            name_selectors = [
                "input[name*='name']",
                "input[id*='name']",
                "input[placeholder*='name' i]",
                "input[placeholder*='grantor' i]",
                "input[type='text']",
            ]

            name_filled = False
            for selector in name_selectors:
                try:
                    name_input = page.locator(selector).first
                    if await name_input.count() > 0:
                        await name_input.fill(name)
                        self.logger.debug(f"Entered name using selector: {selector}")
                        name_filled = True
                        break
                except:
                    continue

            if not name_filled:
                # Try split first/last name fields
                parts = name.split()
                if len(parts) >= 2:
                    last_input = page.locator(self.SELECTORS["last_name"]).first
                    first_input = page.locator(self.SELECTORS["first_name"]).first

                    if await last_input.count() > 0 and await first_input.count() > 0:
                        await last_input.fill(parts[-1])
                        await first_input.fill(" ".join(parts[:-1]))
                        name_filled = True

            if not name_filled:
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

            # Click search
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
            self.logger.error(f"Weld name search failed: {e}")
            await self.screenshot_on_error(page, "weld_name_search_error")

        return results

    async def search_by_instrument(
        self,
        page: Page,
        instrument_number: str
    ) -> List[SearchResult]:
        """Search Weld County records by document/reception number"""
        results = []

        try:
            self.logger.info(f"Searching Weld County by instrument: {instrument_number}")

            if "search" not in page.url.lower():
                await page.goto(self.SEARCH_URL, wait_until="networkidle", timeout=30000)
                await asyncio.sleep(1)
                await self._accept_disclaimer(page)

            # Find document number input
            doc_selectors = [
                "input[name*='docNum']",
                "input[id*='docNumber']",
                "input[name*='reception']",
                "input[id*='reception']",
                "input[placeholder*='document' i]",
                "input[placeholder*='number' i]",
            ]

            doc_filled = False
            for selector in doc_selectors:
                try:
                    doc_input = page.locator(selector).first
                    if await doc_input.count() > 0:
                        await doc_input.fill(instrument_number)
                        doc_filled = True
                        break
                except:
                    continue

            if not doc_filled:
                self.logger.error("Could not find document number input")
                return results

            await self._click_search(page)
            await asyncio.sleep(2)

            results = await self._parse_search_results(page)
            self.logger.info(f"Found {len(results)} documents for instrument '{instrument_number}'")

        except Exception as e:
            self.logger.error(f"Weld instrument search failed: {e}")
            await self.screenshot_on_error(page, "weld_instrument_search_error")

        return results

    async def search_by_parcel(
        self,
        page: Page,
        parcel_number: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """Search Weld County records by parcel number"""
        self.logger.info(f"Parcel search requested for: {parcel_number}")
        self.logger.warning("Weld County may not support direct parcel search. "
                          "Consider looking up owner name from assessor first.")
        return []

    async def _click_search(self, page: Page):
        """Click the search button"""
        try:
            search_selectors = [
                "button[type='submit']",
                "button:has-text('Search')",
                "input[value='Search']",
                "input[type='submit']",
                "button:has-text('Find')",
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
            await asyncio.sleep(1)

            # Check for no results
            no_results = page.locator(self.SELECTORS["no_results"])
            if await no_results.count() > 0:
                self.logger.debug("No results found")
                return results

            # Find results table
            table_selectors = [
                "table.results",
                "table[id*='results']",
                ".search-results table",
                "table tbody",
            ]

            result_table = None
            for selector in table_selectors:
                table = page.locator(selector)
                if await table.count() > 0:
                    result_table = table
                    break

            if not result_table:
                tables = page.locator("table")
                for i in range(await tables.count()):
                    table = tables.nth(i)
                    rows = table.locator("tr")
                    if await rows.count() > 1:
                        result_table = table
                        break

            if not result_table:
                self.logger.debug("No results table found")
                return results

            rows = result_table.locator("tr")
            row_count = await rows.count()
            self.logger.debug(f"Found {row_count} rows in results table")

            seen_instruments = set()

            for i in range(1, row_count):  # Skip header
                try:
                    row = rows.nth(i)
                    cells = row.locator("td")
                    cell_count = await cells.count()

                    if cell_count < 3:
                        continue

                    cell_texts = []
                    for j in range(cell_count):
                        text = await cells.nth(j).inner_text()
                        cell_texts.append(text.strip())

                    # Parse data
                    reception_num = ""
                    doc_type = ""
                    recording_date = None
                    grantor = ""
                    grantee = ""

                    for text in cell_texts:
                        clean = text.replace("-", "").replace(" ", "")
                        if clean.isdigit() and len(clean) >= 5:
                            reception_num = text.strip()
                            break

                    if not reception_num or reception_num in seen_instruments:
                        continue

                    seen_instruments.add(reception_num)

                    import re
                    for text in cell_texts:
                        if re.match(r'\d{1,2}/\d{1,2}/\d{4}', text):
                            recording_date = self.parse_date(text)
                            break

                    for text in cell_texts:
                        if len(text) >= 1 and len(text) <= 10 and text.isupper():
                            doc_type = text
                            break

                    if len(cell_texts) > 3:
                        for j, text in enumerate(cell_texts):
                            if j > 1 and text and not text.isdigit():
                                if not grantor and "/" not in text and len(text) > 1:
                                    grantor = text
                                elif not grantee and "/" not in text and len(text) > 1:
                                    grantee = text
                                    break

                    result = SearchResult(
                        instrument_number=reception_num,
                        document_type=self.classify_document_type(doc_type),
                        recording_date=recording_date,
                        grantor=[grantor] if grantor else [],
                        grantee=[grantee] if grantee else [],
                        download_url="",
                        source_county="Weld",
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
                "button:has-text('Next')",
                "a:has-text('>')",
                ".pagination-next:not(.disabled)",
            ]

            for selector in next_selectors:
                next_btn = page.locator(selector)
                if await next_btn.count() > 0:
                    classes = await next_btn.first.get_attribute("class") or ""
                    disabled = await next_btn.first.get_attribute("disabled")
                    if "disabled" not in classes and not disabled:
                        return True

        except Exception as e:
            self.logger.debug(f"Next page check failed: {e}")

        return False

    async def _go_to_next_page(self, page: Page):
        """Navigate to the next page of results"""
        try:
            next_selectors = [
                "a:has-text('Next')",
                "button:has-text('Next')",
                "a:has-text('>')",
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
        """Download a document from Weld County"""
        try:
            if not result.instrument_number:
                return None

            self.logger.info(f"Downloading document: {result.instrument_number}")
            os.makedirs(download_path, exist_ok=True)

            # Search for the document
            await self.search_by_instrument(page, result.instrument_number)
            await asyncio.sleep(2)

            # Click on document to view details
            doc_link = page.locator(f"text='{result.instrument_number}'").first
            if await doc_link.count() > 0:
                await doc_link.click()
                await asyncio.sleep(3)

            # Look for download/view image link
            download_selectors = [
                "a:has-text('View')",
                "a:has-text('Image')",
                "a:has-text('Download')",
                "a[href*='image']",
                "a[href*='view']",
                "button:has-text('Download')",
            ]

            for selector in download_selectors:
                download_link = page.locator(selector)
                if await download_link.count() > 0:
                    try:
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
                    except:
                        continue

            self.logger.warning(f"Could not find download link for {result.instrument_number}")

        except Exception as e:
            self.logger.error(f"Document download failed for {result.instrument_number}: {e}")
            await self.screenshot_on_error(page, f"download_error_{result.instrument_number}")

        return None

    async def check_health(self) -> bool:
        """Check if the Weld County portal is accessible."""
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
