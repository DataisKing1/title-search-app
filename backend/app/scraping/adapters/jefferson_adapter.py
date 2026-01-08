"""Jefferson County Clerk & Recorder adapter for title searches.

Portal: https://landrecords.co.jefferson.co.us/
System: Aumentum Recorder by Harris Recording Solutions (ASP.NET)

Features:
- Free document images available
- Permanent Index from 01/01/1963
- Images from 01/01/1859
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


@register_adapter("jefferson")
class JeffersonCountyAdapter(BaseCountyAdapter):
    """
    Adapter for Jefferson County Clerk & Recorder public records search.

    Portal: https://landrecords.co.jefferson.co.us/
    System: Aumentum Recorder by Harris Recording Solutions
    """

    BASE_URL = "https://landrecords.co.jefferson.co.us"
    SEARCH_URL = f"{BASE_URL}/RealEstate/SearchEntry.aspx"

    # Form field selectors
    SELECTORS = {
        # Name search fields
        "party_name": "#cphNoMargin_f_txtParty",
        "grantor": "#cphNoMargin_f_txtGrantor",
        "grantee": "#cphNoMargin_f_txtGrantee",

        # Instrument/Book/Page
        "instrument_from": "#cphNoMargin_f_txtInstrumentNoFrom",
        "instrument_to": "#cphNoMargin_f_txtInstrumentNoTo",
        "book": "#cphNoMargin_f_txtBook",
        "page": "#cphNoMargin_f_txtPage",

        # Legal description fields
        "subdivision": "#cphNoMargin_f_txtLDSubdivision",
        "block": "#cphNoMargin_f_txtLDBlock",
        "lot": "#cphNoMargin_f_txtLDLot",
        "section": "#cphNoMargin_f_txtLDSection",
        "township": "#cphNoMargin_f_txtLDTown",
        "range": "#cphNoMargin_f_txtLDRange",
        "quarter": "#cphNoMargin_f_txtLDQtr",
        "address": "#cphNoMargin_f_txtLDAddress",

        # Buttons
        "search_button": "#cphNoMargin_SearchButtons1_btnSearch",
        "clear_button": "#cphNoMargin_SearchButtons1_btnClear",

        # Results
        "result_row": "tr:has(td.fauxDetailLink)",
        "result_link": "td.fauxDetailLink",

        # Detail page
        "image_viewer": "#cphNoMargin_ImageViewer1_ifrLTViewer",
    }

    # Table column indices based on debug output
    # [0]: row number, [1]: View, [3]: instrument, [7]: date, [9]: doc type, [11]: parties
    COLUMN_MAP = {
        "row_number": 0,
        "view_button": 1,
        "instrument_number": 3,
        "recorded_date": 7,
        "document_type": 9,
        "parties": 11,
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.county_name = "Jefferson"

    async def initialize(self, page: Page) -> bool:
        """Navigate to portal and verify access."""
        try:
            self.logger.info("Navigating to Jefferson County portal...")
            await page.goto(self.SEARCH_URL, wait_until="networkidle")
            await asyncio.sleep(2)

            # Verify we're on the search page
            party_input = page.locator(self.SELECTORS["party_name"])
            if await party_input.count() > 0:
                self.logger.info("Jefferson County adapter initialized successfully")
                return True
            else:
                self.logger.error("Could not find search form")
                return False

        except Exception as e:
            self.logger.error(f"Failed to initialize Jefferson adapter: {e}")
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
        """Search records by party name."""
        results = []

        try:
            self.logger.info(f"Searching Jefferson County by name: {name}")

            # Navigate to search page
            await page.goto(self.SEARCH_URL, wait_until="networkidle")
            await asyncio.sleep(2)

            # Click and type into the appropriate field
            # Note: Must use type() with delay, not fill(), for Infragistics controls
            if role == "grantor":
                input_selector = self.SELECTORS["grantor"]
            elif role == "grantee":
                input_selector = self.SELECTORS["grantee"]
            else:
                input_selector = self.SELECTORS["party_name"]

            input_field = page.locator(input_selector)
            await input_field.click()
            await asyncio.sleep(0.3)
            await input_field.type(name, delay=50)
            await asyncio.sleep(0.5)

            # Click search button (more reliable than Enter key)
            search_btn = page.locator(self.SELECTORS["search_button"])
            if await search_btn.count() > 0:
                await search_btn.click()
            else:
                # Fallback to Enter key
                await page.keyboard.press("Enter")

            # Wait for results page
            try:
                await page.wait_for_url("**/SearchResults**", timeout=15000)
            except:
                pass
            await asyncio.sleep(3)

            # Parse results
            if "SearchResults" in page.url:
                results = await self._parse_search_results(page)

                # Handle pagination
                while await self._has_next_page(page):
                    await self._go_to_next_page(page)
                    page_results = await self._parse_search_results(page)
                    results.extend(page_results)
                    await self.wait_between_requests()

            self.logger.info(f"Found {len(results)} documents for name {name}")

        except Exception as e:
            self.logger.error(f"Jefferson name search failed: {e}")
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
        Uses the legal description fields.
        """
        self.logger.warning("Jefferson County: Use search_by_legal() for parcel searches")
        return []

    async def search_by_instrument(
        self,
        page: Page,
        instrument_number: str,
    ) -> List[SearchResult]:
        """Search by instrument number."""
        results = []

        try:
            self.logger.info(f"Searching Jefferson by instrument: {instrument_number}")

            await page.goto(self.SEARCH_URL, wait_until="networkidle")
            await asyncio.sleep(2)

            # Fill instrument number fields
            from_input = page.locator(self.SELECTORS["instrument_from"])
            to_input = page.locator(self.SELECTORS["instrument_to"])

            await from_input.click()
            await from_input.type(instrument_number, delay=50)
            await asyncio.sleep(0.3)

            await to_input.click()
            await to_input.type(instrument_number, delay=50)
            await asyncio.sleep(0.5)

            # Click search button
            search_btn = page.locator(self.SELECTORS["search_button"])
            if await search_btn.count() > 0:
                await search_btn.click()
            else:
                await page.keyboard.press("Enter")

            try:
                await page.wait_for_url("**/SearchResults**", timeout=15000)
            except:
                pass
            await asyncio.sleep(3)

            if "SearchResults" in page.url:
                results = await self._parse_search_results(page)

            self.logger.info(f"Found {len(results)} documents for instrument {instrument_number}")

        except Exception as e:
            self.logger.error(f"Instrument search failed: {e}")
            await self.screenshot_on_error(page, "instrument_search_error")

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
            self.logger.info(f"Searching Jefferson by book/page: {book}/{page_num}")

            await page.goto(self.SEARCH_URL, wait_until="networkidle")
            await asyncio.sleep(2)

            book_input = page.locator(self.SELECTORS["book"])
            page_input = page.locator(self.SELECTORS["page"])

            await book_input.click()
            await book_input.type(book, delay=50)
            await asyncio.sleep(0.3)

            await page_input.click()
            await page_input.type(page_num, delay=50)
            await asyncio.sleep(0.5)

            # Click search button
            search_btn = page.locator(self.SELECTORS["search_button"])
            if await search_btn.count() > 0:
                await search_btn.click()
            else:
                await page.keyboard.press("Enter")

            try:
                await page.wait_for_url("**/SearchResults**", timeout=15000)
            except:
                pass
            await asyncio.sleep(3)

            if "SearchResults" in page.url:
                results = await self._parse_search_results(page)

            self.logger.info(f"Found {len(results)} documents for book {book} page {page_num}")

        except Exception as e:
            self.logger.error(f"Book/page search failed: {e}")
            await self.screenshot_on_error(page, "book_page_search_error")

        return results

    async def search_by_legal(
        self,
        page: Page,
        subdivision: Optional[str] = None,
        block: Optional[str] = None,
        lot: Optional[str] = None,
        section: Optional[str] = None,
        township: Optional[str] = None,
        range_val: Optional[str] = None,
        address: Optional[str] = None,
    ) -> List[SearchResult]:
        """Search by legal description components."""
        results = []

        try:
            self.logger.info("Searching Jefferson by legal description")

            await page.goto(self.SEARCH_URL, wait_until="networkidle")
            await asyncio.sleep(2)

            # Fill available legal description fields
            async def fill_field(selector: str, value: str):
                if value:
                    field = page.locator(selector)
                    await field.click()
                    await field.type(value, delay=50)
                    await asyncio.sleep(0.2)

            await fill_field(self.SELECTORS["subdivision"], subdivision)
            await fill_field(self.SELECTORS["block"], block)
            await fill_field(self.SELECTORS["lot"], lot)
            await fill_field(self.SELECTORS["section"], section)
            await fill_field(self.SELECTORS["township"], township)
            await fill_field(self.SELECTORS["range"], range_val)
            await fill_field(self.SELECTORS["address"], address)

            await asyncio.sleep(0.5)

            # Click search button
            search_btn = page.locator(self.SELECTORS["search_button"])
            if await search_btn.count() > 0:
                await search_btn.click()
            else:
                await page.keyboard.press("Enter")

            try:
                await page.wait_for_url("**/SearchResults**", timeout=15000)
            except:
                pass
            await asyncio.sleep(3)

            if "SearchResults" in page.url:
                results = await self._parse_search_results(page)

            self.logger.info(f"Found {len(results)} documents for legal search")

        except Exception as e:
            self.logger.error(f"Legal search failed: {e}")
            await self.screenshot_on_error(page, "legal_search_error")

        return results

    async def _parse_search_results(self, page: Page) -> List[SearchResult]:
        """Parse search results from the results page."""
        results = []

        try:
            if "SearchResults" not in page.url:
                self.logger.debug("Not on results page")
                return []

            # Get all fauxDetailLink cells
            faux_cells = await page.query_selector_all(self.SELECTORS["result_link"])
            self.logger.info(f"Found {len(faux_cells)} result rows")

            for cell in faux_cells:
                try:
                    # Get the parent row
                    row = await cell.evaluate_handle("cell => cell.closest('tr')")
                    cells = await row.query_selector_all("td")

                    if len(cells) < 12:
                        continue

                    # Extract data from cells based on column map
                    instrument_number = await cells[self.COLUMN_MAP["instrument_number"]].inner_text()
                    instrument_number = instrument_number.strip()

                    recorded_date_text = await cells[self.COLUMN_MAP["recorded_date"]].inner_text()
                    recorded_date_text = recorded_date_text.strip()

                    doc_type = await cells[self.COLUMN_MAP["document_type"]].inner_text()
                    doc_type = doc_type.strip()

                    parties_text = await cells[self.COLUMN_MAP["parties"]].inner_text()
                    parties_text = parties_text.strip()

                    # Parse date
                    recording_date = None
                    try:
                        recording_date = datetime.strptime(recorded_date_text, "%m/%d/%Y")
                    except ValueError:
                        pass

                    # Parse parties - format: "[R] SMITH (+) [E] JONES"
                    grantor_list = []
                    grantee_list = []

                    # Split by (+) to get multiple parties
                    party_parts = parties_text.split("(+)")
                    for part in party_parts:
                        part = part.strip()
                        if part.startswith("[R]"):
                            name = part.replace("[R]", "").strip()
                            if name:
                                grantor_list.append(name)
                        elif part.startswith("[E]"):
                            name = part.replace("[E]", "").strip()
                            if name:
                                grantee_list.append(name)

                    result = SearchResult(
                        instrument_number=instrument_number,
                        document_type=self.classify_document_type(doc_type) if doc_type else "other",
                        recording_date=recording_date,
                        grantor=grantor_list,
                        grantee=grantee_list,
                        download_url=None,
                        source_county=self.county_name,
                    )
                    results.append(result)

                except Exception as e:
                    self.logger.debug(f"Failed to parse row: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to parse results: {e}")
            import traceback
            traceback.print_exc()

        return results

    async def get_document_details(
        self,
        page: Page,
        result: SearchResult,
    ) -> Dict[str, Any]:
        """Navigate to document detail page and extract information."""
        try:
            # If on results page, click the document link
            if "SearchResults" in page.url:
                # Find and click the row with matching instrument number
                faux_cell = page.locator(f"td.fauxDetailLink:has-text('{result.instrument_number}')")
                if await faux_cell.count() > 0:
                    await faux_cell.first.click()
                    await asyncio.sleep(3)

            details = {
                "instrument_number": result.instrument_number,
                "image_available": False,
            }

            if "SearchDetail" in page.url:
                body = await page.locator("body").inner_text()

                # Extract number of pages
                pages_match = re.search(r"# Pages in Image:\s*(\d+)", body)
                if pages_match:
                    details["num_pages"] = int(pages_match.group(1))
                    details["image_available"] = True

                # Check for image viewer frame
                image_frame = page.locator(self.SELECTORS["image_viewer"])
                if await image_frame.count() > 0:
                    details["has_viewer"] = True

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
        Download document image from Jefferson County portal.

        Jefferson County offers free document images via GetImage.aspx endpoint.
        """
        try:
            os.makedirs(download_path, exist_ok=True)

            # Navigate to document detail if needed
            details = await self.get_document_details(page, result)

            if not details.get("image_available"):
                self.logger.warning(f"No image available for {result.instrument_number}")
                return None

            # Try to get the image from the viewer frame
            image_frame = page.frame("cphNoMargin_ImageViewer1_ifrLTViewer")
            if image_frame:
                frame_html = await image_frame.content()

                # Look for GetImage.aspx endpoint with IMAGE_ID
                get_image_pattern = r'GetImage\.aspx\?[^"\'>\s]+'
                matches = re.findall(get_image_pattern, frame_html)

                if matches:
                    # Get cookies for authenticated request
                    cookies = await page.context.cookies()
                    cookie_str = "; ".join([f'{c["name"]}={c["value"]}' for c in cookies])

                    import httpx

                    # Download all pages
                    all_images = []
                    num_pages = details.get("num_pages", 1)

                    for page_num in range(num_pages):
                        # Construct URL for each page
                        base_match = matches[0]
                        if "Fpg=" in base_match:
                            image_url = re.sub(r'Fpg=\d+', f'Fpg={page_num}', base_match)
                        else:
                            image_url = base_match

                        if not image_url.startswith("http"):
                            image_url = f"{self.BASE_URL}/Controls/{image_url}"

                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                image_url,
                                headers={
                                    "Cookie": cookie_str,
                                    "Referer": page.url,
                                },
                                follow_redirects=True,
                                timeout=30
                            )

                            if response.status_code == 200 and len(response.content) > 1000:
                                all_images.append(response.content)
                                self.logger.debug(f"Downloaded page {page_num + 1}/{num_pages}")

                    if all_images:
                        # Determine file extension from content type
                        # Jefferson County serves TIFF images
                        content_type = response.headers.get("content-type", "")
                        if "tiff" in content_type or "tif" in content_type:
                            ext = ".tif"
                        elif "png" in content_type:
                            ext = ".png"
                        elif "gif" in content_type:
                            ext = ".gif"
                        else:
                            ext = ".tif"  # Default to TIFF for Jefferson

                        if len(all_images) == 1:
                            # Single page - save directly
                            filename = f"{result.instrument_number}{ext}"
                            filepath = os.path.join(download_path, filename)

                            with open(filepath, "wb") as f:
                                f.write(all_images[0])

                            self.logger.info(f"Downloaded: {filepath}")

                            return DownloadedDocument(
                                file_path=filepath,
                                file_name=filename,
                                file_size=len(all_images[0]),
                                mime_type=content_type or f"image/{ext[1:]}",
                                content_hash=hashlib.sha256(all_images[0]).hexdigest(),
                                instrument_number=result.instrument_number,
                            )
                        else:
                            # Multi-page - save each page
                            for i, img_data in enumerate(all_images):
                                filename = f"{result.instrument_number}_p{i+1}{ext}"
                                filepath = os.path.join(download_path, filename)
                                with open(filepath, "wb") as f:
                                    f.write(img_data)

                            # Return info about first page
                            first_file = f"{result.instrument_number}_p1{ext}"
                            first_path = os.path.join(download_path, first_file)

                            self.logger.info(f"Downloaded {len(all_images)} pages for {result.instrument_number}")

                            return DownloadedDocument(
                                file_path=first_path,
                                file_name=first_file,
                                file_size=sum(len(img) for img in all_images),
                                mime_type=content_type or f"image/{ext[1:]}",
                                content_hash=hashlib.sha256(all_images[0]).hexdigest(),
                                instrument_number=result.instrument_number,
                            )

            # Fallback: capture page as PDF
            self.logger.info("Using PDF capture as fallback")
            filename = f"{result.instrument_number}.pdf"
            filepath = os.path.join(download_path, filename)

            await page.pdf(path=filepath)

            if os.path.exists(filepath):
                file_size = os.path.getsize(filepath)
                content_hash = hashlib.sha256(open(filepath, "rb").read()).hexdigest()

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
        """Check for next page in pagination."""
        # Jefferson uses numbered page links
        next_link = page.locator("a:has-text('Page'):not([href='#'])")
        # Check if there are any page links after the current one
        page_links = await page.query_selector_all("a[href*='Page']")
        return len(page_links) > 1

    async def _go_to_next_page(self, page: Page):
        """Navigate to next page of results."""
        # Find current page and click next
        current_page = await page.evaluate("""() => {
            const links = document.querySelectorAll('a[href*="Page"]');
            for (let link of links) {
                if (link.style.fontWeight === 'bold' || link.classList.contains('current')) {
                    return parseInt(link.innerText.replace('Page ', ''));
                }
            }
            return 1;
        }""")

        next_page = current_page + 1
        next_link = page.locator(f"a:has-text('Page {next_page}')")

        if await next_link.count() > 0:
            await next_link.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

    async def check_health(self) -> bool:
        """Check if the Jefferson County portal is accessible."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, timeout=30)
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
