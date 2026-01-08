"""El Paso County Clerk & Recorder adapter for title searches.

Portal: https://publicrecordsearch.elpasoco.com/
System: Aumentum Recorder by Harris Recording Solutions (ASP.NET)

NOTE: Many document images are NOT available for online viewing.
The portal displays: "Image for this record is not available on this website.
Please contact the Recording Copy Department if you would like to purchase a copy."
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


@register_adapter("el paso")
class ElPasoCountyAdapter(BaseCountyAdapter):
    """
    Adapter for El Paso County Clerk & Recorder public records search.

    Portal: https://publicrecordsearch.elpasoco.com/
    System: Aumentum Recorder by Harris Recording Solutions
    """

    BASE_URL = "https://publicrecordsearch.elpasoco.com"
    SEARCH_URL = f"{BASE_URL}/RealEstate/SearchEntry.aspx"

    # Real form field selectors discovered from portal
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

        # Date range - Infragistics DatePicker inputs
        # The visible input is a sibling of the hidden clientState field
        "date_from": "input[id$='ddcDateFiledFrom_input']",
        "date_to": "input[id$='ddcDateFiledTo_input']",

        # Legal description
        "subdivision": "#cphNoMargin_f_ddlSubdivision",
        "block": "#cphNoMargin_f_txtBlock",
        "lot": "#cphNoMargin_f_txtLot",
        "section": "#cphNoMargin_f_txtSection",
        "township": "#cphNoMargin_f_txtTownship",
        "range": "#cphNoMargin_f_txtRange",

        # Buttons - correct selectors
        "search_button": "#cphNoMargin_SearchButtons1_btnSearch",
        "clear_button": "#cphNoMargin_SearchButtons1_btnClear",

        # Results
        "result_row": "tr:has(td.fauxDetailLink)",
        "result_link": "td.fauxDetailLink span",

        # Detail page
        "document_info": "#cphNoMargin_SearchDetail1_DocumentInfo",
        "image_container": "#cphNoMargin_SearchDetail1_pnlDocumentImages",
    }

    # Document type checkboxes
    DOC_TYPE_CHECKBOXES = {
        "deed": "#cphNoMargin_f_cblDocumentType_0",
        "deed_of_trust": "#cphNoMargin_f_cblDocumentType_1",
        "release": "#cphNoMargin_f_cblDocumentType_2",
        "assignment": "#cphNoMargin_f_cblDocumentType_3",
        "lien": "#cphNoMargin_f_cblDocumentType_4",
        "lis_pendens": "#cphNoMargin_f_cblDocumentType_5",
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.county_name = "El Paso"

    async def initialize(self, page: Page) -> bool:
        """Navigate to portal, accept disclaimer, and navigate to search via menu."""
        try:
            self.logger.info("Navigating to El Paso County portal...")
            await page.goto(self.BASE_URL, wait_until="networkidle")
            await asyncio.sleep(2)

            # Look for disclaimer acknowledgment link
            disclaimer_link = page.locator("a:has-text('Click here to acknowledge')")
            if await disclaimer_link.count() > 0:
                self.logger.info("Accepting disclaimer...")
                await disclaimer_link.click()
                await asyncio.sleep(2)

            # Navigate via menu clicks (required to establish session)
            # Click Real Estate menu
            real_estate_link = page.locator("a:has-text('Real Estate')").first
            if await real_estate_link.count() > 0:
                self.logger.info("Clicking Real Estate menu...")
                await real_estate_link.click()
                await asyncio.sleep(1)

                # Click Search Real Estate Index submenu
                search_link = page.locator("a:has-text('Search Real Estate Index')")
                if await search_link.count() > 0:
                    self.logger.info("Clicking Search Real Estate Index...")
                    await search_link.click()
                    await asyncio.sleep(3)

            # Verify we're on the search page
            search_btn = page.locator(self.SELECTORS["search_button"])
            if await search_btn.count() > 0:
                self.logger.info("El Paso County adapter initialized successfully")
                return True

            # Fallback: try direct navigation (might work if session is established)
            self.logger.info("Trying direct navigation to search page...")
            await page.goto(self.SEARCH_URL, wait_until="networkidle")
            await asyncio.sleep(2)

            search_btn = page.locator(self.SELECTORS["search_button"])
            if await search_btn.count() > 0:
                self.logger.info("El Paso County adapter initialized successfully (direct)")
                return True
            else:
                self.logger.error("Could not find search form")
                return False

        except Exception as e:
            self.logger.error(f"Failed to initialize El Paso adapter: {e}")
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
            self.logger.info(f"Searching El Paso County by name: {name}")

            # Clear any previous search
            clear_btn = page.locator(self.SELECTORS["clear_button"])
            if await clear_btn.count() > 0:
                await clear_btn.click()
                await asyncio.sleep(0.5)

            # Enter name in appropriate field
            if role == "grantor":
                await page.fill(self.SELECTORS["grantor"], name)
            elif role == "grantee":
                await page.fill(self.SELECTORS["grantee"], name)
            else:
                await page.fill(self.SELECTORS["party_name"], name)

            # Set date range if provided
            # Infragistics DatePicker needs special handling
            if start_date:
                date_str = start_date.strftime("%m/%d/%Y")
                await self._set_date_field(page, "from", date_str)
            if end_date:
                date_str = end_date.strftime("%m/%d/%Y")
                await self._set_date_field(page, "to", date_str)

            # Click search
            await page.click(self.SELECTORS["search_button"])
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            # Parse results
            results = await self._parse_search_results(page)

            # Handle pagination
            while await self._has_next_page(page):
                await self._go_to_next_page(page)
                page_results = await self._parse_search_results(page)
                results.extend(page_results)
                await self.wait_between_requests()

            self.logger.info(f"Found {len(results)} documents for name {name}")

        except Exception as e:
            self.logger.error(f"El Paso name search failed: {e}")
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
        Search El Paso records by parcel number.

        Note: El Paso portal doesn't have direct parcel search.
        Use search_by_legal() for legal description searches.
        """
        self.logger.warning("El Paso County does not support direct parcel search. Use legal description search.")
        return []

    async def search_by_instrument(
        self,
        page: Page,
        instrument_number: str,
    ) -> List[SearchResult]:
        """Search by instrument number (OPRID)."""
        results = []

        try:
            self.logger.info(f"Searching El Paso by instrument: {instrument_number}")

            clear_btn = page.locator(self.SELECTORS["clear_button"])
            if await clear_btn.count() > 0:
                await clear_btn.click()
                await asyncio.sleep(0.5)

            await page.fill(self.SELECTORS["instrument_from"], instrument_number)
            await page.fill(self.SELECTORS["instrument_to"], instrument_number)

            await page.click(self.SELECTORS["search_button"])
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

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
            self.logger.info(f"Searching El Paso by book/page: {book}/{page_num}")

            clear_btn = page.locator(self.SELECTORS["clear_button"])
            if await clear_btn.count() > 0:
                await clear_btn.click()
                await asyncio.sleep(0.5)

            await page.fill(self.SELECTORS["book"], book)
            await page.fill(self.SELECTORS["page"], page_num)

            await page.click(self.SELECTORS["search_button"])
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

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
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> List[SearchResult]:
        """Search by legal description components."""
        results = []

        try:
            self.logger.info("Searching El Paso by legal description")

            clear_btn = page.locator(self.SELECTORS["clear_button"])
            if await clear_btn.count() > 0:
                await clear_btn.click()
                await asyncio.sleep(0.5)

            if subdivision:
                # Subdivision is a dropdown - select by visible text
                await page.select_option(self.SELECTORS["subdivision"], label=subdivision)
            if block:
                await page.fill(self.SELECTORS["block"], block)
            if lot:
                await page.fill(self.SELECTORS["lot"], lot)
            if section:
                await page.fill(self.SELECTORS["section"], section)
            if township:
                await page.fill(self.SELECTORS["township"], township)
            if range_val:
                await page.fill(self.SELECTORS["range"], range_val)

            # Set date range using helper
            if start_date:
                date_str = start_date.strftime("%m/%d/%Y")
                await self._set_date_field(page, "from", date_str)
            if end_date:
                date_str = end_date.strftime("%m/%d/%Y")
                await self._set_date_field(page, "to", date_str)

            await page.click(self.SELECTORS["search_button"])
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

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
            # Check if we're on results page
            if "SearchResults.aspx" not in page.url:
                self.logger.debug("Not on results page")
                return []

            # Use JavaScript to extract data from the Infragistics grid
            # The grid has complex nested structure - fauxDetailLink cells contain OPRID
            raw_results = await page.evaluate("""() => {
                const results = [];
                // Find all fauxDetailLink cells which contain OPRID links
                const fauxCells = document.querySelectorAll('td.fauxDetailLink');

                fauxCells.forEach(cell => {
                    const row = cell.closest('tr');
                    if (!row) return;

                    const cells = row.querySelectorAll('td');
                    if (cells.length < 20) return;

                    // Extract OPRID from the cell text
                    const opridText = cell.innerText.trim();
                    const opridMatch = opridText.match(/OPRID:(\\d+)/);
                    if (!opridMatch) return;

                    const instrumentNumber = opridMatch[1];

                    // Grid structure based on debug:
                    // [0]: Row number
                    // [3]/[4]: OPRID
                    // [11]: Names [E]/[R] markers
                    // [14]: Legal description
                    // [17]: Document type
                    // [20]: Status
                    // [25]: Clean instrument number

                    // Try to extract names from cell 11
                    let grantor = '';
                    let grantee = '';
                    if (cells.length > 11) {
                        const namesText = cells[11].innerText.trim();
                        // Names format: "[E] Name1\\n[R] Name2"
                        const lines = namesText.split('\\n');
                        lines.forEach(line => {
                            if (line.includes('[E]')) {
                                grantee = line.replace('[E]', '').trim();
                            } else if (line.includes('[R]')) {
                                grantor = line.replace('[R]', '').trim();
                            }
                        });
                    }

                    // Document type from cell 17
                    let docType = '';
                    if (cells.length > 17) {
                        docType = cells[17].innerText.trim();
                    }

                    // Try to find recording date - check various cells
                    let recordDate = '';
                    for (let i = 5; i < Math.min(15, cells.length); i++) {
                        const text = cells[i].innerText.trim();
                        if (/^\\d{1,2}\\/\\d{1,2}\\/\\d{4}$/.test(text)) {
                            recordDate = text;
                            break;
                        }
                    }

                    results.push({
                        instrument_number: instrumentNumber,
                        document_type: docType,
                        recording_date: recordDate,
                        grantor: grantor,
                        grantee: grantee
                    });
                });

                return results;
            }""")

            self.logger.info(f"Extracted {len(raw_results)} results from grid")

            for raw in raw_results:
                # Parse date
                recording_date = None
                if raw.get("recording_date"):
                    try:
                        recording_date = datetime.strptime(raw["recording_date"], "%m/%d/%Y")
                    except ValueError:
                        pass

                # Parse grantor/grantee - filter out "DATA MISSING"
                grantor = raw.get("grantor", "")
                grantee = raw.get("grantee", "")

                if "DATA MISSING" in grantor:
                    grantor = ""
                if "DATA MISSING" in grantee:
                    grantee = ""

                grantor_list = [g.strip() for g in grantor.split(",") if g.strip()]
                grantee_list = [g.strip() for g in grantee.split(",") if g.strip()]

                doc_type = raw.get("document_type", "")
                if "DATA MISSING" in doc_type:
                    doc_type = ""

                result = SearchResult(
                    instrument_number=raw["instrument_number"],
                    document_type=self.classify_document_type(doc_type) if doc_type else "other",
                    recording_date=recording_date,
                    grantor=grantor_list,
                    grantee=grantee_list,
                    download_url=None,
                    source_county=self.county_name,
                )
                results.append(result)

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
        """Navigate to document detail page and extract full information."""
        try:
            # If we're on results page, click the document link
            if "SearchResults.aspx" in page.url:
                # Find and click the OPRID link span
                oprid_span = page.locator(f"span:has-text('OPRID:{result.instrument_number}')")
                if await oprid_span.count() > 0:
                    await oprid_span.click()
                    await page.wait_for_load_state("networkidle")
                    await asyncio.sleep(1)
                else:
                    # Try partial match
                    oprid_span = page.locator(f"span:has-text('{result.instrument_number}')")
                    if await oprid_span.count() > 0:
                        await oprid_span.first.click()
                        await page.wait_for_load_state("networkidle")
                        await asyncio.sleep(1)

            # Now on detail page - extract information
            details = {
                "instrument_number": result.instrument_number,
                "image_available": False,
            }

            # Check for "no image" message
            no_image = page.locator("text=Image for this record is not available")
            if await no_image.count() > 0:
                details["image_available"] = False
                details["image_note"] = "Image not available online. Contact Recording Copy Department."
            else:
                # Check for actual image
                img = page.locator(f"{self.SELECTORS['image_container']} img")
                if await img.count() > 0:
                    details["image_available"] = True
                    details["image_url"] = await img.get_attribute("src")

            # Get document info text
            doc_info = page.locator(self.SELECTORS["document_info"])
            if await doc_info.count() > 0:
                details["document_info"] = await doc_info.inner_text()

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
        Download document image from El Paso County portal.

        NOTE: Many documents do not have images available online.
        The portal will display a message directing users to contact
        the Recording Copy Department.
        """
        try:
            os.makedirs(download_path, exist_ok=True)

            # Get document details first (this navigates to detail page)
            details = await self.get_document_details(page, result)

            if not details.get("image_available"):
                self.logger.warning(
                    f"Image not available for {result.instrument_number}. "
                    "Contact Recording Copy Department for copies."
                )
                return None

            # If image is available, download it
            image_url = details.get("image_url")
            if not image_url:
                self.logger.error("No image URL found")
                return None

            # Make absolute URL if needed
            if image_url.startswith("/"):
                image_url = f"{self.BASE_URL}{image_url}"

            # Get cookies for authenticated download
            context = page.context
            cookies = await context.cookies()
            cookie_str = "; ".join([f'{c["name"]}={c["value"]}' for c in cookies])

            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    image_url,
                    headers={
                        "Cookie": cookie_str,
                        "Referer": page.url,
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    },
                    follow_redirects=True,
                )

                if response.status_code == 200:
                    # Determine file extension from content type
                    content_type = response.headers.get("content-type", "")
                    if "png" in content_type:
                        ext = ".png"
                    elif "jpeg" in content_type or "jpg" in content_type:
                        ext = ".jpg"
                    elif "pdf" in content_type:
                        ext = ".pdf"
                    elif "tiff" in content_type or "tif" in content_type:
                        ext = ".tif"
                    else:
                        ext = ".bin"

                    filename = f"{result.instrument_number}{ext}"
                    file_path = os.path.join(download_path, filename)

                    with open(file_path, "wb") as f:
                        f.write(response.content)

                    file_size = len(response.content)
                    content_hash = hashlib.sha256(response.content).hexdigest()

                    self.logger.info(f"Downloaded: {file_path} ({file_size} bytes)")

                    return DownloadedDocument(
                        file_path=file_path,
                        file_name=filename,
                        file_size=file_size,
                        mime_type=content_type,
                        content_hash=content_hash,
                        instrument_number=result.instrument_number,
                    )
                else:
                    self.logger.error(f"Download failed with status {response.status_code}")
                    return None

        except Exception as e:
            self.logger.error(f"Download failed: {e}")
            await self.screenshot_on_error(page, "download_error")
            return None

    async def _has_next_page(self, page: Page) -> bool:
        """Check for next page in pagination."""
        # El Paso uses Infragistics grid with paging
        next_btn = page.locator("a:has-text('Next'), .igdPagerNext:not(.disabled)")
        if await next_btn.count() > 0:
            # Check if it's not disabled
            classes = await next_btn.first.get_attribute("class") or ""
            return "disabled" not in classes.lower()
        return False

    async def _go_to_next_page(self, page: Page):
        """Navigate to next page of results."""
        next_btn = page.locator("a:has-text('Next'), .igdPagerNext").first
        if await next_btn.count() > 0:
            await next_btn.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(1)

    async def _set_date_field(self, page: Page, field_type: str, date_str: str):
        """Set date field value using JavaScript for Infragistics DatePicker."""
        try:
            if field_type == "from":
                selector = self.SELECTORS["date_from"]
                input_id = "cphNoMargin_f_ddcDateFiledFrom"
            else:
                selector = self.SELECTORS["date_to"]
                input_id = "cphNoMargin_f_ddcDateFiledTo"

            # Try direct fill first
            date_field = page.locator(selector)
            if await date_field.count() > 0:
                await date_field.fill(date_str)
                return

            # Fallback: Use JavaScript to set the value
            await page.evaluate(f"""(dateStr) => {{
                // Find input by partial ID match
                const inputs = document.querySelectorAll('input[id*="{input_id}"]');
                inputs.forEach(input => {{
                    if (input.type === 'text' && !input.id.includes('clientState')) {{
                        input.value = dateStr;
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                }});
            }}""", date_str)
        except Exception as e:
            self.logger.debug(f"Could not set date field {field_type}: {e}")

    async def check_health(self) -> bool:
        """Check if the El Paso County portal is accessible."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(self.BASE_URL, timeout=30)
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
