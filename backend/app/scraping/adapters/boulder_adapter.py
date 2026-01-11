"""Boulder County Clerk & Recorder adapter for KoFile County Fusion system"""
from playwright.async_api import Page, FrameLocator
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import os
import hashlib

from app.scraping.base_adapter import BaseCountyAdapter, SearchResult, DownloadedDocument
from app.scraping.adapters import register_adapter


@register_adapter("boulder")
class BoulderCountyAdapter(BaseCountyAdapter):
    """
    Adapter for Boulder County Clerk & Recorder - KoFile County Fusion system.

    Portal: https://countyfusion2.kofiletech.us/countyweb/loginDisplay.action?countyname=Boulder
    System: KoFile County Fusion 2 (GovOS)

    Page Structure:
        - Main page with multiple iframes
        - bodyframe > dynSearchFrame > criteriaframe (search form)
        - bodyframe > resultFrame (search results)

    Search Types:
        - Names (grantor/grantee search)
        - Reception Number (instrument number search)
        - Book - Page

    Note: Very similar to Adams and Denver County adapters.
    """

    BASE_URL = "https://countyfusion2.kofiletech.us/countyweb"
    LOGIN_URL = f"{BASE_URL}/loginDisplay.action?countyname=Boulder"
    GUEST_LOGIN_URL = f"{BASE_URL}/login.action?countyname=Boulder&guest=true"

    # Search type row IDs (in dynSearchFrame)
    SEARCH_TYPES = {
        "names": "SEARCHTYPE_datagrid-row-r2-2-0",
        "reception_number": "SEARCHTYPE_datagrid-row-r2-2-1",
        "book_page": "SEARCHTYPE_datagrid-row-r2-2-2",
    }

    # Document type codes for filtering
    DOC_TYPES = {
        "deed": ["DEED", "WD", "QCD", "SWD", "SPWD", "BD"],
        "mortgage": ["MORT", "DTD", "TD", "DOT"],
        "release": ["REL", "RELDT", "RELMORT", "REC"],
        "lien": ["LIEN", "FSTL", "MECHL", "TAXL", "FTL"],
        "easement": ["EASE", "ESMT"],
        "plat": ["PLAT", "SURVEY"],
        "assignment": ["ASGN", "AOT"],
    }

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.county_name = "Boulder"
        self._body_frame: Optional[FrameLocator] = None
        self._dyn_frame: Optional[FrameLocator] = None
        self._criteria_frame: Optional[FrameLocator] = None
        self._result_frame: Optional[FrameLocator] = None

    async def initialize(self, page: Page) -> bool:
        """Navigate to search page, login as guest, and accept disclaimers"""
        try:
            self.logger.info("Initializing Boulder County KoFile adapter")

            # Navigate to login page
            await page.goto(self.LOGIN_URL, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)

            # Click "Search Records as Guest" button
            guest_button = page.locator("input[value*='Guest'], button:has-text('Guest'), input[type='button'][value*='Search Records as Guest']")
            if await guest_button.count() > 0:
                await guest_button.first.click()
                self.logger.info("Clicked guest login button")
            else:
                # Try direct guest login URL
                await page.goto(self.GUEST_LOGIN_URL, wait_until="networkidle", timeout=30000)

            await asyncio.sleep(2)
            await page.wait_for_load_state("networkidle")

            # Accept disclaimer if present
            await self._accept_disclaimer(page)

            # Wait for main content to load
            await asyncio.sleep(2)

            # Set up frame references
            await self._setup_frames(page)

            # Verify we can access the search form
            if not self._criteria_frame:
                self.logger.error("Could not access search form frames")
                return False

            self.logger.info("Boulder County adapter initialized successfully")
            return True

        except Exception as e:
            self.logger.error(f"Failed to initialize Boulder adapter: {e}")
            await self.screenshot_on_error(page, "boulder_init_error")
            return False

    async def _accept_disclaimer(self, page: Page):
        """Accept the disclaimer dialog if present"""
        try:
            body_frame = page.frame("bodyframe")

            if not body_frame:
                self.logger.warning("Could not find bodyframe")
                return

            # Check if we're on the disclaimer page
            if "disclaimer" in body_frame.url.lower():
                self.logger.info("On disclaimer page, accepting...")

                try:
                    await body_frame.evaluate('() => executeCommand("Accept")')
                    self.logger.info("Executed executeCommand('Accept')")
                except Exception as e:
                    self.logger.debug(f"executeCommand failed, trying form submit: {e}")
                    try:
                        await body_frame.evaluate('() => document.disclaimerform.submit()')
                    except:
                        pass

                await asyncio.sleep(3)
                await page.wait_for_load_state("networkidle")

                for _ in range(10):
                    await asyncio.sleep(1)
                    body_frame = page.frame("bodyframe")
                    if body_frame and "searchMain" in body_frame.url:
                        self.logger.info("Search interface loaded successfully")
                        return

                self.logger.warning("Search interface may not have loaded")
            else:
                self.logger.debug(f"Not on disclaimer page: {body_frame.url}")

        except Exception as e:
            self.logger.error(f"Disclaimer handling error: {e}")

    async def _setup_frames(self, page: Page):
        """Set up references to the nested iframes"""
        try:
            self._body_frame = page.frame_locator("iframe[name='bodyframe']")
            self._dyn_frame = self._body_frame.frame_locator("iframe[name='dynSearchFrame']")
            self._criteria_frame = self._dyn_frame.frame_locator("iframe#criteriaframe")
            self._result_frame = self._body_frame.frame_locator("iframe[name='resultFrame']")

            await self._wait_for_loading(page)
            await self._dismiss_notifications(page)

            self.logger.debug("Frame references established")

        except Exception as e:
            self.logger.error(f"Failed to setup frames: {e}")
            raise

    async def _dismiss_notifications(self, page: Page):
        """Dismiss any notification popups"""
        try:
            body_frame = page.frame("bodyframe")
            if body_frame:
                result = await body_frame.evaluate("""() => {
                    if (typeof hideDialog === 'function') {
                        hideDialog();
                        return 'hideDialog called';
                    }
                    if (typeof hideNotification === 'function') {
                        hideNotification();
                        return 'hideNotification called';
                    }
                    let dialogFrame = document.querySelector('iframe[name="dialogframe"]');
                    if (dialogFrame) {
                        dialogFrame.style.display = 'none';
                        dialogFrame.style.visibility = 'hidden';
                        return 'dialogframe hidden';
                    }
                    return 'no action';
                }""")
                if result != 'no action':
                    self.logger.info(f"Dismissed notification: {result}")
                    await asyncio.sleep(0.5)

        except Exception as e:
            self.logger.debug(f"Notification dismiss error (may be normal): {e}")

    async def _wait_for_loading(self, page: Page, timeout: int = 10):
        """Wait for loading overlays to disappear"""
        try:
            disable_div = self._dyn_frame.locator("#disablediv, .loading, .overlay")
            for _ in range(timeout):
                try:
                    if await disable_div.count() == 0:
                        return
                    is_visible = await disable_div.first.is_visible()
                    if not is_visible:
                        return
                except:
                    return
                await asyncio.sleep(1)
        except:
            pass

    async def _select_search_type(self, page: Page, search_type: str = "names"):
        """Select the search type from the left panel"""
        try:
            await self._wait_for_loading(page)

            type_text_map = {
                "names": "Names",
                "reception_number": "Reception Number",
                "book_page": "Book - Page",
            }

            search_text = type_text_map.get(search_type, "Names")

            if search_type == "names":
                selected = self._dyn_frame.locator("tr.datagrid-row-selected")
                if await selected.count() > 0:
                    text = await selected.first.inner_text()
                    if "Names" in text:
                        self.logger.debug("Names search type already selected")
                        return

            row_id = self.SEARCH_TYPES.get(search_type, self.SEARCH_TYPES["names"])
            search_row = self._dyn_frame.locator(f"tr#{row_id}")
            if await search_row.count() > 0:
                try:
                    await search_row.click(force=True, timeout=5000)
                    await asyncio.sleep(1)
                    await self._wait_for_loading(page)
                    self.logger.info(f"Selected search type: {search_type}")
                    return
                except Exception as e:
                    self.logger.debug(f"Click failed: {e}")

            all_rows = self._dyn_frame.locator("tr.datagrid-row")
            count = await all_rows.count()
            for i in range(count):
                row = all_rows.nth(i)
                try:
                    text = await row.inner_text()
                    if search_text.lower() in text.lower():
                        await row.click(force=True, timeout=5000)
                        await asyncio.sleep(1)
                        self.logger.info(f"Selected search type from datagrid: {search_type}")
                        return
                except:
                    continue

            self.logger.warning(f"Search type not found: {search_type}")

        except Exception as e:
            self.logger.error(f"Failed to select search type: {e}")

    async def search_by_name(
        self,
        page: Page,
        name: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """Search Boulder County records by grantor/grantee name"""
        results = []

        try:
            self.logger.info(f"Searching Boulder County by name: {name}")

            if not self._criteria_frame:
                await self._setup_frames(page)

            await self._select_search_type(page, "names")
            await asyncio.sleep(1)

            await self._click_clear(page)
            await asyncio.sleep(0.5)

            name_selectors = [
                "input#allNames",
                "input[id*='allNames']",
                "input[name*='NAME']",
                "input[id*='name']",
                "input.textbox-text",
                "input[type='text']",
            ]

            name_filled = False
            for selector in name_selectors:
                try:
                    name_input = self._criteria_frame.locator(selector).first
                    if await name_input.count() > 0:
                        await name_input.fill(name, timeout=5000)
                        self.logger.debug(f"Entered name using selector: {selector}")
                        name_filled = True
                        break
                except Exception as e:
                    self.logger.debug(f"Selector {selector} failed: {e}")
                    continue

            if not name_filled:
                self.logger.error("Could not find name input field")
                return results

            if start_date:
                date_str = start_date.strftime("%m/%d/%Y")
                from_date_selectors = [
                    "span:has(input#FROMDATE) input.textbox-text",
                    "input.textbox-text[comboname='FROMDATE']",
                ]
                for selector in from_date_selectors:
                    try:
                        from_date = self._criteria_frame.locator(selector).first
                        if await from_date.count() > 0 and await from_date.is_visible():
                            await from_date.fill(date_str, timeout=5000)
                            self.logger.debug(f"Set from date: {date_str}")
                            break
                    except:
                        continue

            if end_date:
                date_str = end_date.strftime("%m/%d/%Y")
                to_date_selectors = [
                    "span:has(input#TODATE) input.textbox-text",
                    "input.textbox-text[comboname='TODATE']",
                ]
                for selector in to_date_selectors:
                    try:
                        to_date = self._criteria_frame.locator(selector).first
                        if await to_date.count() > 0 and await to_date.is_visible():
                            await to_date.fill(date_str, timeout=5000)
                            self.logger.debug(f"Set to date: {date_str}")
                            break
                    except:
                        continue

            try:
                all_parties = self._criteria_frame.locator("input#partyRBBoth")
                if await all_parties.count() > 0:
                    await all_parties.check(force=True, timeout=3000)
            except Exception as e:
                self.logger.debug(f"Could not check all parties radio: {e}")

            await self._click_search(page)
            await asyncio.sleep(5)

            warning = await self._check_for_warnings(page)
            if warning:
                self.logger.warning(f"Search warning: {warning}")
                if "exceeds maximum" in warning.lower():
                    return results
                if "no documents" in warning.lower():
                    return results

            results = await self._parse_search_results(page)

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
            self.logger.error(f"Boulder name search failed: {e}")
            await self.screenshot_on_error(page, "boulder_name_search_error")

        return results

    async def search_by_instrument(
        self,
        page: Page,
        instrument_number: str
    ) -> List[SearchResult]:
        """Search Boulder County records by reception/instrument number"""
        results = []

        try:
            self.logger.info(f"Searching Boulder County by instrument: {instrument_number}")

            if not self._criteria_frame:
                await self._setup_frames(page)

            await self._select_search_type(page, "reception_number")
            await asyncio.sleep(1)

            await self._click_clear(page)
            await asyncio.sleep(0.5)

            reception_input = self._criteria_frame.locator(
                "input[id*='reception'], input[name*='RECEPTION'], input[id*='instrument']"
            ).first

            if await reception_input.count() > 0:
                await reception_input.fill(instrument_number)
            else:
                self.logger.warning("Reception number input not found")
                return results

            await self._click_search(page)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            results = await self._parse_search_results(page)
            self.logger.info(f"Found {len(results)} documents for instrument '{instrument_number}'")

        except Exception as e:
            self.logger.error(f"Boulder instrument search failed: {e}")
            await self.screenshot_on_error(page, "boulder_instrument_search_error")

        return results

    async def search_by_parcel(
        self,
        page: Page,
        parcel_number: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SearchResult]:
        """Search Boulder County records by parcel number - not directly supported"""
        self.logger.info(f"Parcel search requested for: {parcel_number}")
        self.logger.warning("Boulder County KoFile doesn't support direct parcel search. "
                          "Consider looking up owner name from assessor first.")
        return []

    async def _check_for_warnings(self, page: Page) -> Optional[str]:
        """Check for warning messages"""
        try:
            warning_selectors = [
                ".warning, .error, [style*='color: red'], [style*='color:red']",
                "span[style*='red'], div[style*='red']",
                "font[color='red']",
            ]

            for selector in warning_selectors:
                try:
                    warning = self._criteria_frame.locator(selector)
                    if await warning.count() > 0:
                        text = await warning.first.inner_text()
                        if text.strip():
                            return text.strip()
                except:
                    continue

            for selector in warning_selectors:
                try:
                    warning = self._dyn_frame.locator(selector)
                    if await warning.count() > 0:
                        text = await warning.first.inner_text()
                        if text.strip():
                            return text.strip()
                except:
                    continue

        except Exception as e:
            self.logger.debug(f"Warning check failed: {e}")

        return None

    async def _click_search(self, page: Page):
        """Click the search button"""
        try:
            await self._wait_for_loading(page)

            search_btn = self._dyn_frame.locator("img#imgSearch")
            if await search_btn.count() > 0:
                await search_btn.click(force=True, timeout=5000)
                self.logger.debug("Clicked search button")
            else:
                alt_btn = self._dyn_frame.locator(
                    "input[value='Search'], button:has-text('Search'), img[alt*='Search']"
                ).first
                await alt_btn.click(force=True, timeout=5000)

        except Exception as e:
            self.logger.error(f"Failed to click search: {e}")

    async def _click_clear(self, page: Page):
        """Click the clear button"""
        try:
            await self._wait_for_loading(page)
            clear_btn = self._dyn_frame.locator("img#imgClear")
            if await clear_btn.count() > 0:
                await clear_btn.click(force=True, timeout=5000)
                await asyncio.sleep(0.5)
        except Exception as e:
            self.logger.debug(f"Clear button click failed: {e}")

    async def _parse_search_results(self, page: Page) -> List[SearchResult]:
        """Parse search results from the result frame"""
        results = []

        try:
            result_list_frame = page.frame("resultListFrame")
            if not result_list_frame:
                self.logger.debug("resultListFrame not found")
                return results

            tables = await result_list_frame.query_selector_all("table")
            self.logger.debug(f"Found {len(tables)} tables in resultListFrame")

            data_table = None
            max_rows = 0
            for table in tables:
                rows = await table.query_selector_all("tr")
                if len(rows) > max_rows:
                    max_rows = len(rows)
                    data_table = table

            if not data_table or max_rows < 2:
                self.logger.debug("No data table found with results")
                return results

            self.logger.debug(f"Using data table with {max_rows} rows")
            rows = await data_table.query_selector_all("tr")

            seen_reception_nums = set()

            for row in rows:
                try:
                    cells = await row.query_selector_all("td")
                    if len(cells) < 6:
                        continue

                    cell_texts = []
                    for cell in cells:
                        text = await cell.inner_text()
                        cell_texts.append(text.strip())

                    reception_num = ""
                    for text in cell_texts:
                        clean = text.replace("+", "").replace("\n", "").replace("\t", "").replace("\xa0", "").strip()
                        if clean.isdigit() and len(clean) >= 7:
                            reception_num = clean
                            break

                    if not reception_num or reception_num in seen_reception_nums:
                        continue

                    seen_reception_nums.add(reception_num)

                    grantor = ""
                    grantee = ""
                    doc_type = ""
                    recording_date_str = ""

                    for i, text in enumerate(cell_texts):
                        if text == "GR" and i + 1 < len(cell_texts):
                            grantor = cell_texts[i + 1]
                        elif text == "GE" and i + 1 < len(cell_texts):
                            grantee = cell_texts[i + 1]

                    import re
                    for i in range(len(cell_texts) - 1, -1, -1):
                        text = cell_texts[i]
                        if re.match(r'\d{2}/\d{2}/\d{4}', text):
                            recording_date_str = text
                            if i > 0 and cell_texts[i-1] not in ["GR", "GE", ""]:
                                doc_type = cell_texts[i-1]
                            break

                    if not recording_date_str:
                        for text in reversed(cell_texts):
                            if text and "/" in text:
                                recording_date_str = text
                                break

                    recording_date = self.parse_date(recording_date_str) if recording_date_str else None

                    result = SearchResult(
                        instrument_number=reception_num,
                        document_type=self.classify_document_type(doc_type),
                        recording_date=recording_date,
                        grantor=[grantor] if grantor else [],
                        grantee=[grantee] if grantee else [],
                        download_url=f"javascript:viewDoc('{reception_num}')",
                        source_county="Boulder",
                        raw_data={"doc_type_raw": doc_type, "date_raw": recording_date_str}
                    )
                    results.append(result)

                except Exception as e:
                    self.logger.debug(f"Failed to parse row: {e}")
                    continue

        except Exception as e:
            self.logger.error(f"Failed to parse search results: {e}")

        return results

    async def _has_next_page(self, page: Page) -> bool:
        """Check if there's a next page of results"""
        try:
            next_btn = self._result_frame.locator(
                "a:has-text('Next'), span.pagination-next:not(.disabled), "
                "a[onclick*='next'], img[alt*='Next']"
            )

            if await next_btn.count() > 0:
                first_btn = next_btn.first
                classes = await first_btn.get_attribute("class") or ""
                onclick = await first_btn.get_attribute("onclick") or ""

                if "disabled" not in classes and onclick:
                    return True

        except Exception as e:
            self.logger.debug(f"Next page check failed: {e}")

        return False

    async def _go_to_next_page(self, page: Page):
        """Navigate to the next page of results"""
        try:
            next_btn = self._result_frame.locator(
                "a:has-text('Next'), a[onclick*='next']"
            ).first

            if await next_btn.count() > 0:
                await next_btn.click()
                await page.wait_for_load_state("networkidle")

        except Exception as e:
            self.logger.error(f"Failed to go to next page: {e}")

    async def download_document(
        self,
        page: Page,
        result: SearchResult,
        download_path: str
    ) -> Optional[DownloadedDocument]:
        """Download a document from Boulder County"""
        try:
            if not result.instrument_number:
                return None

            self.logger.info(f"Downloading document: {result.instrument_number}")

            os.makedirs(download_path, exist_ok=True)

            result_list_frame = page.frame("resultListFrame")
            if not result_list_frame:
                self.logger.error("resultListFrame not found")
                return None

            doc_link = await result_list_frame.query_selector(
                f'a[onclick*="loadRecord"]:has-text("{result.instrument_number}")'
            )

            if not doc_link:
                links = await result_list_frame.query_selector_all('a[onclick*="loadRecord"]')
                for link in links:
                    text = await link.inner_text()
                    if result.instrument_number in text:
                        doc_link = link
                        break

            if not doc_link:
                self.logger.error(f"Document link not found for {result.instrument_number}")
                return None

            await doc_link.click()
            await asyncio.sleep(5)

            img_frame = page.frame("docImgViewFrame")
            if not img_frame:
                self.logger.error("docImgViewFrame not found")
                return None

            for _ in range(10):
                if "blank" not in img_frame.url.lower():
                    break
                await asyncio.sleep(0.5)

            images = await img_frame.query_selector_all('img[src*="viewImagePNG"]')
            if not images:
                self.logger.error("No document image found in viewer")
                return None

            img_url = await images[0].get_attribute("src")
            if not img_url:
                self.logger.error("Could not get image URL")
                return None

            context = page.context
            cookies = await context.cookies()
            cookie_str = "; ".join([f'{c["name"]}={c["value"]}' for c in cookies])

            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    img_url,
                    headers={
                        "Cookie": cookie_str,
                        "Referer": "https://countyfusion2.kofiletech.us/"
                    },
                    follow_redirects=True,
                    timeout=60.0
                )

                if response.status_code != 200:
                    self.logger.error(f"Image download failed: HTTP {response.status_code}")
                    return None

                filename = f"{result.instrument_number}.png"
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
                    mime_type="image/png",
                    content_hash=content_hash,
                    instrument_number=result.instrument_number
                )

        except Exception as e:
            self.logger.error(f"Document download failed for {result.instrument_number}: {e}")
            await self.screenshot_on_error(page, f"download_error_{result.instrument_number}")

        return None

    async def check_health(self) -> bool:
        """Check if the Boulder County portal is accessible."""
        try:
            import httpx
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.LOGIN_URL,
                    follow_redirects=True,
                    timeout=30
                )
                return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Health check failed: {e}")
            return False
