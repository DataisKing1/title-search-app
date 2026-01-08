"""Generic county adapter for unsupported counties"""
from playwright.async_api import Page
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import os
import hashlib

from app.scraping.base_adapter import BaseCountyAdapter, SearchResult, DownloadedDocument


class GenericCountyAdapter(BaseCountyAdapter):
    """
    Generic adapter for counties without specific implementations.

    This adapter attempts to work with common county website patterns
    and falls back gracefully when specific features aren't available.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self._initialized = False

    async def initialize(self, page: Page) -> bool:
        """Initialize generic adapter - navigate to recorder URL"""
        try:
            if not self.base_url:
                self.logger.error(f"No recorder URL configured for {self.county_name}")
                return False

            self.logger.info(f"Initializing generic adapter for {self.county_name}")

            await page.goto(self.base_url, wait_until="networkidle")
            await asyncio.sleep(2)

            # Try to accept common disclaimers
            await self._accept_disclaimers(page)

            # Verify page loaded
            content = await page.content()
            if len(content) < 1000:
                self.logger.warning(f"Page content seems too short for {self.county_name}")

            self._initialized = True
            self.logger.info(f"Generic adapter initialized for {self.county_name}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize generic adapter: {e}")
            return False

    async def _accept_disclaimers(self, page: Page):
        """Try to accept common disclaimer patterns"""
        disclaimers = [
            "button:has-text('Accept')",
            "button:has-text('I Agree')",
            "button:has-text('Continue')",
            "button:has-text('Enter')",
            "input[type='submit'][value*='Accept']",
            "input[type='submit'][value*='Agree']",
            "a:has-text('Accept')",
            "#accept",
            "#agree",
            ".accept-button",
        ]

        for selector in disclaimers:
            try:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    await btn.first.click()
                    await asyncio.sleep(1)
                    self.logger.info(f"Accepted disclaimer with: {selector}")
                    break
            except Exception as e:
                self.logger.debug(f"Disclaimer selector {selector} failed: {e}")
                continue

    async def search_by_parcel(
        self,
        page: Page,
        parcel_number: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """Attempt generic parcel search"""
        results = []

        try:
            self.logger.info(f"Generic parcel search for {parcel_number} in {self.county_name}")

            # Try to find parcel input
            parcel_input = await self._find_input_by_keywords(
                page,
                ["parcel", "apn", "pin", "property", "legal"]
            )

            if not parcel_input:
                self.logger.warning(f"Could not find parcel input for {self.county_name}")
                return results

            # Fill parcel number
            await parcel_input.clear()
            await parcel_input.fill(parcel_number)

            # Try to set dates
            if start_date:
                await self._try_set_date(page, start_date, "start", "from", "begin")
            if end_date:
                await self._try_set_date(page, end_date, "end", "to", "through")

            # Submit search
            await self._submit_search(page)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            # Parse results
            results = await self._parse_generic_results(page)

            self.logger.info(f"Found {len(results)} documents via generic search")

        except Exception as e:
            self.logger.error(f"Generic parcel search failed: {e}")
            await self.screenshot_on_error(page, "generic_parcel_error")

        return results

    async def search_by_name(
        self,
        page: Page,
        name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """Attempt generic name search"""
        results = []

        try:
            self.logger.info(f"Generic name search for {name} in {self.county_name}")

            # Try to find name input
            name_input = await self._find_input_by_keywords(
                page,
                ["name", "grantor", "grantee", "party", "owner"]
            )

            if not name_input:
                self.logger.warning(f"Could not find name input for {self.county_name}")
                return results

            await name_input.clear()
            await name_input.fill(name)

            # Set dates
            if start_date:
                await self._try_set_date(page, start_date, "start", "from")
            if end_date:
                await self._try_set_date(page, end_date, "end", "to")

            # Submit
            await self._submit_search(page)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            results = await self._parse_generic_results(page)

            self.logger.info(f"Found {len(results)} documents via generic name search")

        except Exception as e:
            self.logger.error(f"Generic name search failed: {e}")
            await self.screenshot_on_error(page, "generic_name_error")

        return results

    async def download_document(
        self,
        page: Page,
        result: SearchResult,
        download_path: str
    ) -> Optional[DownloadedDocument]:
        """Attempt to download document"""
        try:
            if not result.download_url:
                self.logger.warning(f"No download URL for {result.instrument_number}")
                return None

            os.makedirs(download_path, exist_ok=True)

            # Try to download
            if result.download_url.startswith("http"):
                # Direct URL
                try:
                    async with page.expect_download(timeout=30000) as download_info:
                        await page.goto(result.download_url)
                    download = await download_info.value
                except Exception as e:
                    # Navigate to page and look for download button
                    self.logger.debug(f"Direct download failed, trying fallback: {e}")
                    await page.goto(result.download_url)
                    await asyncio.sleep(2)
                    download = await self._find_and_click_download(page)

            else:
                # Selector or action
                await page.click(result.download_url)
                await asyncio.sleep(2)
                download = await self._find_and_click_download(page)

            if download:
                filename = download.suggested_filename or f"{result.instrument_number}.pdf"
                file_path = os.path.join(download_path, filename)
                await download.save_as(file_path)

                file_size = os.path.getsize(file_path)
                with open(file_path, "rb") as f:
                    content_hash = hashlib.sha256(f.read()).hexdigest()

                return DownloadedDocument(
                    file_path=file_path,
                    file_name=filename,
                    file_size=file_size,
                    mime_type="application/pdf",
                    content_hash=content_hash,
                    instrument_number=result.instrument_number
                )

        except Exception as e:
            self.logger.error(f"Generic download failed: {e}")

        return None

    async def _find_input_by_keywords(self, page: Page, keywords: List[str]):
        """Find an input field matching any of the keywords"""
        for keyword in keywords:
            selectors = [
                f"input[name*='{keyword}' i]",
                f"input[id*='{keyword}' i]",
                f"input[placeholder*='{keyword}' i]",
                f"input[aria-label*='{keyword}' i]",
            ]

            for selector in selectors:
                try:
                    element = page.locator(selector)
                    if await element.count() > 0:
                        return element.first
                except Exception as e:
                    self.logger.debug(f"Input selector {selector} failed: {e}")
                    continue

        return None

    async def _try_set_date(self, page: Page, date: datetime, *keywords):
        """Try to set a date field"""
        date_str = date.strftime("%m/%d/%Y")

        for keyword in keywords:
            try:
                element = await self._find_input_by_keywords(page, [keyword, f"{keyword}date", f"date{keyword}"])
                if element:
                    await element.fill(date_str)
                    return
            except Exception as e:
                self.logger.debug(f"Date field {keyword} failed: {e}")
                continue

    async def _submit_search(self, page: Page):
        """Submit the search form"""
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']",
            "button:has-text('Search')",
            "button:has-text('Find')",
            "button:has-text('Submit')",
            "input[value*='Search' i]",
            "#search",
            ".search-button",
        ]

        for selector in submit_selectors:
            try:
                btn = page.locator(selector)
                if await btn.count() > 0:
                    await btn.first.click()
                    return
            except Exception as e:
                self.logger.debug(f"Submit selector {selector} failed: {e}")
                continue

        # Fallback to Enter key
        self.logger.debug("Falling back to Enter key for form submission")
        await page.keyboard.press("Enter")

    async def _parse_generic_results(self, page: Page) -> List[SearchResult]:
        """Parse results using generic patterns"""
        results = []

        try:
            # Try to find result table
            tables = await page.locator("table").all()

            for table in tables:
                rows = await table.locator("tbody tr, tr").all()

                # Skip header row
                for row in rows[1:] if len(rows) > 1 else rows:
                    try:
                        result = await self._parse_generic_row(row)
                        if result:
                            results.append(result)
                    except Exception as e:
                        self.logger.debug(f"Failed to parse row: {e}")
                        continue

            # If no table, try other patterns
            if not results:
                result_divs = await page.locator(".result, .record, [class*='result'], [class*='record']").all()
                for div in result_divs:
                    try:
                        result = await self._parse_generic_div(div)
                        if result:
                            results.append(result)
                    except Exception as e:
                        self.logger.debug(f"Failed to parse div: {e}")
                        continue

        except Exception as e:
            self.logger.error(f"Generic result parsing failed: {e}")

        return results

    async def _parse_generic_row(self, row) -> Optional[SearchResult]:
        """Parse a table row into SearchResult"""
        try:
            cells = await row.locator("td").all()
            if len(cells) < 2:
                return None

            text_content = await row.inner_text()
            if not text_content.strip():
                return None

            instrument_number = ""
            doc_type = "other"
            recording_date = None
            download_url = None

            # Look for instrument number (usually in first cell with link)
            for cell in cells:
                text = (await cell.inner_text()).strip()

                link = cell.locator("a")
                if await link.count() > 0 and not instrument_number:
                    instrument_number = text
                    download_url = await link.get_attribute("href")

                # Detect document type
                if any(word in text.lower() for word in ["deed", "mortgage", "lien", "trust"]):
                    doc_type = self.classify_document_type(text)

                # Detect date
                if "/" in text and len(text) <= 12:
                    parsed = self.parse_date(text)
                    if parsed:
                        recording_date = parsed

            if not instrument_number:
                # Try first cell as instrument number
                first_cell = (await cells[0].inner_text()).strip()
                if len(first_cell) > 3:
                    instrument_number = first_cell

            if not instrument_number:
                return None

            return SearchResult(
                instrument_number=instrument_number,
                document_type=doc_type,
                recording_date=recording_date,
                download_url=download_url,
                source_county=self.county_name
            )

        except Exception as e:
            self.logger.debug(f"Failed to parse generic row: {e}")
            return None

    async def _parse_generic_div(self, div) -> Optional[SearchResult]:
        """Parse a result div into SearchResult"""
        try:
            text = await div.inner_text()
            if not text.strip():
                return None

            # Try to extract instrument number from links
            link = div.locator("a").first
            instrument_number = ""
            download_url = None

            if await link.count() > 0:
                instrument_number = (await link.inner_text()).strip()
                download_url = await link.get_attribute("href")

            if not instrument_number:
                return None

            return SearchResult(
                instrument_number=instrument_number,
                document_type="other",
                download_url=download_url,
                source_county=self.county_name
            )

        except Exception as e:
            self.logger.debug(f"Failed to parse generic div: {e}")
            return None

    async def _find_and_click_download(self, page: Page):
        """Find and click download button, return download"""
        download_selectors = [
            "a:has-text('Download')",
            "button:has-text('Download')",
            "a:has-text('PDF')",
            "a[href*='.pdf']",
            "a:has-text('View')",
            ".download-btn",
        ]

        for selector in download_selectors:
            try:
                btn = page.locator(selector).first
                if await btn.count() > 0:
                    async with page.expect_download(timeout=30000) as download_info:
                        await btn.click()
                    return await download_info.value
            except Exception as e:
                self.logger.debug(f"Download selector {selector} failed: {e}")
                continue

        return None
