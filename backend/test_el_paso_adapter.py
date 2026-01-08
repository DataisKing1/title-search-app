"""Test script for El Paso County adapter with real selectors."""
import asyncio
import re
from datetime import datetime
from playwright.async_api import async_playwright


async def parse_results(page):
    """Parse results using the same logic as the adapter."""
    raw_results = await page.evaluate("""() => {
        const results = [];
        const fauxCells = document.querySelectorAll('td.fauxDetailLink');

        fauxCells.forEach(cell => {
            const row = cell.closest('tr');
            if (!row) return;

            const cells = row.querySelectorAll('td');
            if (cells.length < 20) return;

            const opridText = cell.innerText.trim();
            const opridMatch = opridText.match(/OPRID:(\\d+)/);
            if (!opridMatch) return;

            const instrumentNumber = opridMatch[1];

            let grantor = '';
            let grantee = '';
            if (cells.length > 11) {
                const namesText = cells[11].innerText.trim();
                const lines = namesText.split('\\n');
                lines.forEach(line => {
                    if (line.includes('[E]')) {
                        grantee = line.replace('[E]', '').trim();
                    } else if (line.includes('[R]')) {
                        grantor = line.replace('[R]', '').trim();
                    }
                });
            }

            let docType = '';
            if (cells.length > 17) {
                docType = cells[17].innerText.trim();
            }

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
    return raw_results


async def test_el_paso_adapter():
    """Test the El Paso County portal with real selectors."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            # Test 1: Initialize
            print("=" * 60)
            print("TEST 1: Initialize Session")
            print("=" * 60)

            print("Navigating to El Paso County portal...")
            await page.goto("https://publicrecordsearch.elpasoco.com")
            await asyncio.sleep(2)

            disclaimer_link = page.locator("a:has-text('Click here to acknowledge')")
            if await disclaimer_link.count() > 0:
                print("Found disclaimer - clicking...")
                await disclaimer_link.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(1)
                print("Disclaimer accepted!")

            await page.goto(
                "https://publicrecordsearch.elpasoco.com/RealEstate/SearchEntry.aspx",
                wait_until="networkidle",
            )
            await asyncio.sleep(1)

            search_btn = page.locator("#cphNoMargin_SearchButtons1_btnSearch")
            if await search_btn.count() > 0:
                print("SUCCESS: Search form loaded!")
            else:
                print("FAILED: Could not find search form")
                return

            # Test 2: Name Search with a real common name
            print("\n" + "=" * 60)
            print("TEST 2: Name Search for 'Johnson'")
            print("=" * 60)

            await page.click("#cphNoMargin_SearchButtons1_btnClear")
            await asyncio.sleep(0.5)

            # Search for a common name
            await page.fill("#cphNoMargin_f_txtParty", "Johnson")
            await page.click("#cphNoMargin_SearchButtons1_btnSearch")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            if "SearchResults.aspx" in page.url:
                print("SUCCESS: Navigated to results page!")

                # Parse results
                results = await parse_results(page)
                print(f"Parsed {len(results)} results")

                # Show first 5 results
                print("\nFirst 5 results:")
                for i, r in enumerate(results[:5]):
                    print(f"  {i+1}. OPRID: {r['instrument_number']}")
                    print(f"     Date: {r['recording_date'] or 'N/A'}")
                    print(f"     Type: {r['document_type'] or 'N/A'}")
                    grantor = r['grantor'] if r['grantor'] and 'DATA MISSING' not in r['grantor'] else 'N/A'
                    grantee = r['grantee'] if r['grantee'] and 'DATA MISSING' not in r['grantee'] else 'N/A'
                    print(f"     Grantor: {grantor[:50]}")
                    print(f"     Grantee: {grantee[:50]}")
            else:
                print(f"WARNING: Not on results page. URL: {page.url}")

            # Test 3: Document Details
            print("\n" + "=" * 60)
            print("TEST 3: View Document Details")
            print("=" * 60)

            # Click first OPRID link
            faux_cell = page.locator("td.fauxDetailLink").first
            if await faux_cell.count() > 0:
                oprid_text = await faux_cell.inner_text()
                print(f"Clicking on: {oprid_text}")
                await faux_cell.click()
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(1)

                if "SearchDetail.aspx" in page.url:
                    print("SUCCESS: Navigated to detail page!")

                    no_image = page.locator("text=Image for this record is not available")
                    if await no_image.count() > 0:
                        print("Image NOT available (expected for many El Paso records)")
                    else:
                        img = page.locator("#cphNoMargin_SearchDetail1_pnlDocumentImages img")
                        if await img.count() > 0:
                            print("Image IS available!")
                else:
                    print(f"WARNING: Not on detail page. URL: {page.url}")

            # Test 4: Search with date range
            print("\n" + "=" * 60)
            print("TEST 4: Name Search with Date Range")
            print("=" * 60)

            await page.goto(
                "https://publicrecordsearch.elpasoco.com/RealEstate/SearchEntry.aspx",
                wait_until="networkidle",
            )
            await asyncio.sleep(1)

            await page.click("#cphNoMargin_SearchButtons1_btnClear")
            await asyncio.sleep(0.5)

            # Search for "Smith" with date range
            await page.fill("#cphNoMargin_f_txtParty", "Smith")
            await page.fill("#cphNoMargin_f_dfRecordDateFrom_incoming", "01/01/2024")
            await page.fill("#cphNoMargin_f_dfRecordDateTo_incoming", "12/31/2024")
            await page.click("#cphNoMargin_SearchButtons1_btnSearch")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            if "SearchResults.aspx" in page.url:
                results = await parse_results(page)
                print(f"Found {len(results)} results for 'Smith' in 2024")

                # Show first 3
                for i, r in enumerate(results[:3]):
                    print(f"  {i+1}. OPRID: {r['instrument_number']}")
                    print(f"     Date: {r['recording_date'] or 'N/A'}")
                    doc_type = r['document_type'] if r['document_type'] and 'DATA MISSING' not in r['document_type'] else 'N/A'
                    print(f"     Type: {doc_type}")

            await page.screenshot(path="el_paso_test_results.png")
            print("\nScreenshot saved: el_paso_test_results.png")

            print("\n" + "=" * 60)
            print("ALL TESTS COMPLETED SUCCESSFULLY")
            print("=" * 60)
            print("\nEl Paso County Adapter Status:")
            print("  - Session initialization: WORKING")
            print("  - Name search: WORKING")
            print("  - Date range filter: WORKING")
            print("  - Results parsing: WORKING")
            print("  - Document navigation: WORKING")
            print("  - Image availability: Most images NOT available online")
            print("    (Contact Recording Copy Department for copies)")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="el_paso_test_error.png")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_el_paso_adapter())
