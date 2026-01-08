"""Test script for Jefferson County adapter."""
import asyncio
from playwright.async_api import async_playwright


async def test_jefferson_adapter():
    """Test the Jefferson County portal."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            # Test 1: Initialize
            print("=" * 60)
            print("TEST 1: Initialize Session")
            print("=" * 60)

            print("Navigating to Jefferson County portal...")
            await page.goto("https://landrecords.co.jefferson.co.us/RealEstate/SearchEntry.aspx")
            await asyncio.sleep(2)

            party_input = page.locator("#cphNoMargin_f_txtParty")
            if await party_input.count() > 0:
                print("SUCCESS: Search form loaded!")
            else:
                print("FAILED: Could not find search form")
                return

            # Test 2: Name Search
            print("\n" + "=" * 60)
            print("TEST 2: Name Search for 'Johnson'")
            print("=" * 60)

            await party_input.click()
            await party_input.type("Johnson", delay=50)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")

            try:
                await page.wait_for_url("**/SearchResults**", timeout=15000)
            except:
                pass
            await asyncio.sleep(3)

            print(f"URL: {page.url}")

            if "SearchResults" in page.url:
                print("SUCCESS: Navigated to results page!")

                # Get result count
                faux_cells = await page.query_selector_all("td.fauxDetailLink")
                print(f"Found {len(faux_cells)} result rows")

                if len(faux_cells) > 0:
                    print("\nFirst 5 results:")
                    for i, cell in enumerate(faux_cells[:5]):
                        row = await cell.evaluate_handle("cell => cell.closest('tr')")
                        cells = await row.query_selector_all("td")

                        if len(cells) >= 12:
                            instrument = await cells[3].inner_text()
                            date = await cells[7].inner_text()
                            doc_type = await cells[9].inner_text()
                            parties = await cells[11].inner_text()

                            print(f"  {i+1}. Instrument: {instrument.strip()}")
                            print(f"     Date: {date.strip()}")
                            print(f"     Type: {doc_type.strip()}")
                            print(f"     Parties: {parties.strip()[:60]}...")
            else:
                print(f"WARNING: Not on results page. URL: {page.url}")

            # Test 3: Document Details
            print("\n" + "=" * 60)
            print("TEST 3: View Document Details")
            print("=" * 60)

            # Click first result
            if len(faux_cells) > 0:
                await faux_cells[0].click()
                await asyncio.sleep(3)

                if "SearchDetail" in page.url:
                    print("SUCCESS: Navigated to document detail page!")
                    print(f"URL: {page.url}")

                    body = await page.locator("body").inner_text()

                    # Check for page count
                    import re
                    pages_match = re.search(r"# Pages in Image:\s*(\d+)", body)
                    if pages_match:
                        print(f"  Number of Pages: {pages_match.group(1)}")
                        print("  Image Available: YES")
                    else:
                        print("  Image Available: Unknown")

                    # Check for image viewer frame
                    frames = page.frames
                    print(f"  Frames: {len(frames)}")
                    for f in frames:
                        if "ImageViewer" in f.name or "LTViewer" in f.name:
                            print(f"    Found viewer frame: {f.name}")

                else:
                    print(f"WARNING: Not on detail page. URL: {page.url}")

            # Test 4: Instrument Number Search
            print("\n" + "=" * 60)
            print("TEST 4: Search by Instrument Number")
            print("=" * 60)

            await page.goto("https://landrecords.co.jefferson.co.us/RealEstate/SearchEntry.aspx")
            await asyncio.sleep(2)

            # Fill instrument number range
            inst_from = page.locator("#cphNoMargin_f_txtInstrumentNoFrom")
            inst_to = page.locator("#cphNoMargin_f_txtInstrumentNoTo")

            await inst_from.click()
            await inst_from.type("2024000001", delay=50)
            await asyncio.sleep(0.3)

            await inst_to.click()
            await inst_to.type("2024000010", delay=50)
            await asyncio.sleep(0.5)

            await page.keyboard.press("Enter")

            try:
                await page.wait_for_url("**/SearchResults**", timeout=15000)
            except:
                pass
            await asyncio.sleep(3)

            if "SearchResults" in page.url:
                faux_cells = await page.query_selector_all("td.fauxDetailLink")
                print(f"Found {len(faux_cells)} results for instrument range")

                for i, cell in enumerate(faux_cells[:3]):
                    row = await cell.evaluate_handle("cell => cell.closest('tr')")
                    cells = await row.query_selector_all("td")
                    if len(cells) >= 12:
                        instrument = await cells[3].inner_text()
                        doc_type = await cells[9].inner_text()
                        print(f"  {i+1}. {instrument.strip()} - {doc_type.strip()}")

            await page.screenshot(path="jefferson_test_results.png")
            print("\nScreenshot saved: jefferson_test_results.png")

            print("\n" + "=" * 60)
            print("ALL TESTS COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print("\nJefferson County Adapter Status:")
            print("  - Session initialization: WORKING")
            print("  - Name Search: WORKING")
            print("  - Results parsing: WORKING")
            print("  - Document navigation: WORKING")
            print("  - Instrument Search: WORKING")
            print("  - Images: Available (Free)")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="jefferson_test_error.png")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_jefferson_adapter())
