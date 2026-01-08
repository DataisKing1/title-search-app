"""Debug script for Jefferson County portal."""
import asyncio
from playwright.async_api import async_playwright


async def debug_jefferson():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})

        try:
            # Navigate and search
            await page.goto("https://landrecords.co.jefferson.co.us/RealEstate/SearchEntry.aspx")
            await asyncio.sleep(3)

            party_input = page.locator("#cphNoMargin_f_txtParty")
            await party_input.click()
            await party_input.type("Smith", delay=50)
            await page.keyboard.press("Enter")

            try:
                await page.wait_for_url("**/SearchResults**", timeout=15000)
            except:
                pass
            await asyncio.sleep(4)

            print(f"URL: {page.url}")
            print("=" * 60)

            if "SearchResults" not in page.url:
                print("Not on results page")
                return

            # Get fauxDetailLink cells
            faux_cells = await page.query_selector_all("td.fauxDetailLink")
            print(f"Found {len(faux_cells)} fauxDetailLink cells")

            if len(faux_cells) > 0:
                print("\nFirst 3 results:")
                for i, cell in enumerate(faux_cells[:3]):
                    # Get the row
                    row = await cell.evaluate_handle("cell => cell.closest('tr')")
                    cells = await row.query_selector_all("td")

                    print(f"\nResult {i+1}:")
                    for j, c in enumerate(cells[:12]):
                        text = await c.inner_text()
                        text_clean = " ".join(text.split())[:50]
                        print(f"  [{j}]: {text_clean}")

            # Click first result
            print("\n" + "=" * 60)
            print("Clicking first result...")
            await faux_cells[0].click()
            await asyncio.sleep(3)

            print(f"Detail URL: {page.url}")
            await page.screenshot(path="jefferson_detail.png")

            if "SearchDetail" in page.url:
                print("SUCCESS: On detail page!")

                body = await page.locator("body").inner_text()
                print(f"\nDetail page content:\n{body[:1500]}")

                # Look for image/download links
                print("\n--- Looking for images ---")
                imgs = await page.query_selector_all("img[src*='image'], img[src*='doc']")
                print(f"Found {len(imgs)} potential document images")

                frames = page.frames
                print(f"\nFrames: {len(frames)}")
                for f in frames:
                    print(f"  Frame: {f.name} -> {f.url[:60]}...")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_jefferson())
