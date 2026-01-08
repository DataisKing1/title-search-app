"""Arapahoe County Clerk & Recorder adapter for title searches.

Portal: https://arapahoe.co.publicsearch.us/
System: PublicSearch.us - Modern React-based portal

Features:
- Quick Search and Advanced Search options
- Free document downloads (PDF)
- Document images with signed URLs
- Date range filtering
- Document type filtering
"""
import asyncio
import re
import os
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any
from playwright.async_api import Page

from app.scraping.base_adapter import BaseCountyAdapter, SearchResult, DownloadedDocument
from app.scraping.adapters import register_adapter


@register_adapter("arapahoe")
class ArapahoeCountyAdapter(BaseCountyAdapter):
    """
    Adapter for Arapahoe County Clerk & Recorder public records search.

    Portal: https://arapahoe.co.publicsearch.us/
    System: PublicSearch.us (React-based modern interface)
    """

    BASE_URL = "https://arapahoe.co.publicsearch.us"
    QUICK_SEARCH_URL = BASE_URL
    ADVANCED_SEARCH_URL = f"{BASE_URL}/search/advanced"

    # CSS selectors for the React-based UI
    SELECTORS = {
        # Quick Search
        "quick_search_input": "input[placeholder*='grantor' i]",

        # Advanced Search fields
        "grantor": "input[placeholder*='Insert part' i][id*='downshift']",
        "grantee": "input[placeholder*='Insert grantee' i]",
        "date_range": "#recordedDateRange",
        "doc_types": "#docTypes-input",
        "reception_number": "#documentNumber",
        "book": "#volume",
        "page": "#page",
        "ocr_text": "#ocrText",

        # Buttons
        "search_button": "button:has-text('Search')",
        "clear_button": "button:has-text('Clear')",

        # Results
        "result_row": "tbody tr",
        "result_count": "text=/\\d+ results?/",

        # Document detail
        "download_button": "button:has-text('Download')",
        "doc_title": "text=/DOC #/",
    }

    # Table column indices (based on class names col-0 through col-11)
    COLUMN_MAP = {
        "reception_number": 3,
        "book": 4,
        "page": 5,
        "doc_type": 6,
        "grantor": 7,
        "grantee": 8,
        "recorded_date": 9,
        "legal_description": 10,
        "references": 11,
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.county_name = "Arapahoe"

    async def initialize(self, page: Page) -> bool:
        """Navigate to the portal and verify access."""
        try:
            self.logger.info("Navigating to Arapahoe County portal...")
            await page.goto(self.BASE_URL, wait_until="networkidle")
            await asyncio.sleep(2)

            # Verify we're on the search page
            search_input = page.locator(self.SELECTORS["quick_search_input"])
            if await search_input.count() > 0:
                self.logger.info("Arapahoe County adapter initialized successfully")
                return True
            else:
                self.logger.error("Could not find search form")
                return False

        except Exception as e:
            self.logger.error(f"Failed to initialize Arapahoe adapter: {e}")
            await self.screenshot_on_error(page, "init_error")
            return False

    async def search_by_name(
        self,
        page: Page,
        name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        role: str = "both",  # "grantor", "grantee", or "both"
    ) -> List[SearchResult]:
        """Search records by party name using Quick Search."""
        results = []

        try:
            self.logger.info(f"Searching Arapahoe County by name: {name}")

            # Navigate to quick search
            await page.goto(self.BASE_URL, wait_until="networkidle")
            await asyncio.sleep(1)

            # Fill the search input
            search_input = page.locator(self.SELECTORS["quick_search_input"])
            await search_input.fill(name)
            await asyncio.sleep(0.5)

            # Press Enter to search
            await search_input.press("Enter")
            await asyncio.sleep(3)

            # Wait for results to load
            try:
                await page.wait_for_selector(self.SELECTORS["result_row"], timeout=10000)
            except:
                self.logger.warning("No results found or timeout waiting for results")
                return []

            # Parse results
            results = await self._parse_search_results(page)

            # Apply date filter in post-processing if needed
            if start_date or end_date:
                results = self._filter_by_date(results, start_date, end_date)

            self.logger.info(f"Found {len(results)} documents for name {name}")

        except Exception as e:
            self.logger.error(f"Arapahoe name search failed: {e}")
            await self.screenshot_on_error(page, "name_search_error")

        return results

    async def search_by_parcel(
        self,
        page: Page,
        parcel_number: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """
        Search by parcel/legal description.

        Note: Uses the OCR text search or legal description fields.
        """
        return await self.search_by_ocr_text(page, parcel_number, start_date, end_date)

    async def search_by_reception(
        self,
        page: Page,
        reception_number: str,
    ) -> List[SearchResult]:
        """Search by reception number (document number)."""
        results = []

        try:
            self.logger.info(f"Searching Arapahoe by reception: {reception_number}")

            await page.goto(self.ADVANCED_SEARCH_URL, wait_until="networkidle")
            await asyncio.sleep(1)

            # Fill reception number
            reception_input = page.locator(self.SELECTORS["reception_number"])
            await reception_input.fill(reception_number)
            await asyncio.sleep(0.5)

            # Click search
            await page.click(self.SELECTORS["search_button"])
            await asyncio.sleep(3)

            # Wait for results
            try:
                await page.wait_for_selector(self.SELECTORS["result_row"], timeout=10000)
                results = await self._parse_search_results(page)
            except:
                self.logger.debug("No results found")

            self.logger.info(f"Found {len(results)} documents for reception {reception_number}")

        except Exception as e:
            self.logger.error(f"Reception search failed: {e}")
            await self.screenshot_on_error(page, "reception_search_error")

        return results

    async def search_by_book_page(
        self,
        page: Page,
        book: str,
        page_num: str,
    ) -> List[SearchResult]:
        """Search by book and page number."""
        results = []

        try:
            self.logger.info(f"Searching Arapahoe by book/page: {book}/{page_num}")

            await page.goto(self.ADVANCED_SEARCH_URL, wait_until="networkidle")
            await asyncio.sleep(1)

            # Fill book and page
            book_input = page.locator(self.SELECTORS["book"])
            page_input = page.locator(self.SELECTORS["page"])

            await book_input.fill(book)
            await page_input.fill(page_num)
            await asyncio.sleep(0.5)

            # Click search
            await page.click(self.SELECTORS["search_button"])
            await asyncio.sleep(3)

            try:
                await page.wait_for_selector(self.SELECTORS["result_row"], timeout=10000)
                results = await self._parse_search_results(page)
            except:
                self.logger.debug("No results found")

            self.logger.info(f"Found {len(results)} documents for book {book} page {page_num}")

        except Exception as e:
            self.logger.error(f"Book/page search failed: {e}")
            await self.screenshot_on_error(page, "book_page_search_error")

        return results

    async def search_by_ocr_text(
        self,
        page: Page,
        search_text: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[SearchResult]:
        """Search by full document text (OCR)."""
        results = []

        try:
            self.logger.info(f"Searching Arapahoe by OCR text: {search_text}")

            await page.goto(self.ADVANCED_SEARCH_URL, wait_until="networkidle")
            await asyncio.sleep(1)

            # Fill OCR text field
            ocr_input = page.locator(self.SELECTORS["ocr_text"])
            await ocr_input.fill(search_text)
            await asyncio.sleep(0.5)

            # Click search
            await page.click(self.SELECTORS["search_button"])
            await asyncio.sleep(5)  # OCR search takes longer

            try:
                await page.wait_for_selector(self.SELECTORS["result_row"], timeout=15000)
                results = await self._parse_search_results(page)
            except:
                self.logger.debug("No results found")

            if start_date or end_date:
                results = self._filter_by_date(results, start_date, end_date)

            self.logger.info(f"Found {len(results)} documents for OCR text {search_text}")

        except Exception as e:
            self.logger.error(f"OCR search failed: {e}")
            await self.screenshot_on_error(page, "ocr_search_error")

        return results

    async def _parse_search_results(self, page: Page) -> List[SearchResult]:
        """Parse search results from the results table."""
        results = []

        try:
            # Check we're on results page
            if "/results" not in page.url:
                self.logger.debug("Not on results page")
                return []

            # Wait for table to be fully loaded
            await asyncio.sleep(1)

            # Use JavaScript to extract data from the table
            raw_results = await page.evaluate("""() => {
                const results = [];
                const rows = document.querySelectorAll('tbody tr');

                rows.forEach(row => {
                    const cells = row.querySelectorAll('td');
                    if (cells.length < 10) return;

                    // Column indices based on class names
                    // col-3: reception number, col-6: doc type, col-7: grantor
                    // col-8: grantee, col-9: recorded date, col-10: legal

                    const getCellText = (index) => {
                        if (cells[index]) {
                            return cells[index].innerText.trim();
                        }
                        return '';
                    };

                    const receptionNumber = getCellText(3);
                    if (!receptionNumber || receptionNumber === 'N/A') return;

                    results.push({
                        reception_number: receptionNumber,
                        book: getCellText(4),
                        page: getCellText(5),
                        doc_type: getCellText(6),
                        grantor: getCellText(7),
                        grantee: getCellText(8),
                        recorded_date: getCellText(9),
                        legal_description: getCellText(10),
                        references: getCellText(11)
                    });
                });

                return results;
            }""")

            self.logger.info(f"Extracted {len(raw_results)} results from table")

            for raw in raw_results:
                # Parse date
                recording_date = None
                if raw.get("recorded_date"):
                    try:
                        recording_date = datetime.strptime(raw["recorded_date"], "%m/%d/%Y")
                    except ValueError:
                        pass

                # Parse grantor/grantee
                grantor = raw.get("grantor", "")
                grantee = raw.get("grantee", "")

                if grantor and grantor != "N/A":
                    grantor_list = [g.strip() for g in grantor.split("\n") if g.strip()]
                else:
                    grantor_list = []

                if grantee and grantee != "N/A":
                    grantee_list = [g.strip() for g in grantee.split("\n") if g.strip()]
                else:
                    grantee_list = []

                doc_type = raw.get("doc_type", "")
                if doc_type == "N/A":
                    doc_type = ""

                result = SearchResult(
                    instrument_number=raw["reception_number"],
                    document_type=self.classify_document_type(doc_type) if doc_type else "other",
                    recording_date=recording_date,
                    grantor=grantor_list,
                    grantee=grantee_list,
                    book=raw.get("book") if raw.get("book") != "N/A" else None,
                    page=raw.get("page") if raw.get("page") != "N/A" else None,
                    legal_description=raw.get("legal_description") if raw.get("legal_description") != "N/A" else None,
                    download_url=None,  # Will be set when viewing document
                    source_county=self.county_name,
                )
                results.append(result)

        except Exception as e:
            self.logger.error(f"Failed to parse results: {e}")
            import traceback
            traceback.print_exc()

        return results

    def _filter_by_date(
        self,
        results: List[SearchResult],
        start_date: Optional[datetime],
        end_date: Optional[datetime]
    ) -> List[SearchResult]:
        """Filter results by date range."""
        filtered = []
        for result in results:
            if result.recording_date:
                if start_date and result.recording_date < start_date:
                    continue
                if end_date and result.recording_date > end_date:
                    continue
            filtered.append(result)
        return filtered

    async def get_document_details(
        self,
        page: Page,
        result: SearchResult,
    ) -> Dict[str, Any]:
        """Navigate to document detail page and extract full information."""
        try:
            # If we're on results page, find and click the row
            if "/results" in page.url:
                # Find the row with matching reception number
                row = page.locator(f"tbody tr:has-text('{result.instrument_number}')").first
                if await row.count() > 0:
                    await row.click()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(2)

            # Now on detail page - extract information
            details = {
                "instrument_number": result.instrument_number,
                "download_available": False,
            }

            # Check for download button
            download_btn = page.locator(self.SELECTORS["download_button"])
            if await download_btn.count() > 0:
                details["download_available"] = True
                btn_text = await download_btn.inner_text()
                details["download_free"] = "Free" in btn_text

            # Get document info from page
            page_content = await page.locator("body").inner_text()

            # Extract number of pages
            pages_match = re.search(r"Number of Pages:\s*(\d+)", page_content)
            if pages_match:
                details["num_pages"] = int(pages_match.group(1))

            # Extract consideration if present
            consideration_match = re.search(r"Consideration:\s*\$?([\d,]+)", page_content)
            if consideration_match:
                details["consideration"] = consideration_match.group(1)

            # Get document ID from URL for download
            doc_id_match = re.search(r"/doc/(\d+)", page.url)
            if doc_id_match:
                details["doc_id"] = doc_id_match.group(1)

            return details

        except Exception as e:
            self.logger.error(f"Failed to get document details: {e}")
            return {"error": str(e)}

    async def download_document(
        self,
        page: Page,
        result: SearchResult,
        download_path: str
    ) -> Optional[DownloadedDocument]:
        """
        Download document from Arapahoe County portal.

        Uses the "Download (Free)" button when available, or captures
        the document view as PDF.
        """
        try:
            os.makedirs(download_path, exist_ok=True)

            # Get document details first (navigates to detail page)
            details = await self.get_document_details(page, result)

            if not details.get("download_available"):
                self.logger.warning(f"Download not available for {result.instrument_number}")
                return None

            doc_id = details.get("doc_id")
            if not doc_id:
                self.logger.error("Could not determine document ID")
                return None

            # Method 1: Try to capture all page images from the HTML
            html = await page.content()
            image_pattern = r'(https://arapahoe\.co\.publicsearch\.us/files/documents/\d+/images/[^"&\s]+)'
            image_urls = re.findall(image_pattern, html)

            if image_urls:
                # Download all page images
                import httpx

                cookies = await page.context.cookies()
                cookie_str = "; ".join([f'{c["name"]}={c["value"]}' for c in cookies])

                downloaded_files = []
                async with httpx.AsyncClient() as client:
                    for i, img_url in enumerate(image_urls):
                        # Clean up URL (remove HTML entities)
                        img_url = img_url.replace("&amp;", "&")

                        response = await client.get(
                            img_url,
                            headers={
                                "Cookie": cookie_str,
                                "Referer": page.url,
                            },
                            follow_redirects=True,
                            timeout=30
                        )

                        if response.status_code == 200 and len(response.content) > 1000:
                            filename = f"{result.instrument_number}_page{i+1}.png"
                            filepath = os.path.join(download_path, filename)
                            with open(filepath, "wb") as f:
                                f.write(response.content)
                            downloaded_files.append(filepath)
                            self.logger.debug(f"Downloaded page {i+1}")

                if downloaded_files:
                    # Return info about first file, note total pages
                    return DownloadedDocument(
                        file_path=downloaded_files[0],
                        file_name=os.path.basename(downloaded_files[0]),
                        file_size=os.path.getsize(downloaded_files[0]),
                        mime_type="image/png",
                        content_hash=hashlib.sha256(
                            open(downloaded_files[0], "rb").read()
                        ).hexdigest(),
                        instrument_number=result.instrument_number,
                        metadata={"total_pages": len(downloaded_files)}
                    )

            # Method 2: Fallback - capture page as PDF
            self.logger.info("Using PDF capture as fallback")
            filename = f"{result.instrument_number}.pdf"
            filepath = os.path.join(download_path, filename)

            await page.pdf(path=filepath)

            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                content_hash = hashlib.sha256(open(filepath, "rb").read()).hexdigest()

                self.logger.info(f"Downloaded: {filepath} ({file_size} bytes)")

                return DownloadedDocument(
                    file_path=filepath,
                    file_name=filename,
                    file_size=file_size,
                    mime_type="application/pdf",
                    content_hash=content_hash,
                    instrument_number=result.instrument_number,
                )

            return None

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            await self.screenshot_on_error(page, "download_error")
            return None

    async def _has_next_page(self, page: Page) -> bool:
        """Check for next page in results pagination."""
        # Look for pagination controls
        next_btn = page.locator("button:has-text('Next'), a:has-text('Next'), [aria-label='Next page']")
        if await next_btn.count() > 0:
            is_disabled = await next_btn.first.get_attribute("disabled")
            return is_disabled is None
        return False

    async def _go_to_next_page(self, page: Page):
        """Navigate to next page of results."""
        next_btn = page.locator("button:has-text('Next'), a:has-text('Next'), [aria-label='Next page']").first
        if await next_btn.count() > 0:
            await next_btn.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

    async def check_health(self) -> bool:
        """Check if the Arapahoe County portal is accessible."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, timeout=30)
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
