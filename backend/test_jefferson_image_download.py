"""Test Jefferson County direct image download."""
import asyncio
import os
import re
from playwright.async_api import async_playwright
import httpx


async def test_image_download():
    """Test downloading actual document images from Jefferson County."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            print("=" * 60)
            print("Jefferson County Image Download Test")
            print("=" * 60)

            # Navigate and search
            print("\n1. Navigating to search...")
            await page.goto("https://landrecords.co.jefferson.co.us/RealEstate/SearchEntry.aspx")
            await asyncio.sleep(2)

            # Search by instrument number
            inst_from = page.locator("#cphNoMargin_f_txtInstrumentNoFrom")
            inst_to = page.locator("#cphNoMargin_f_txtInstrumentNoTo")

            await inst_from.click()
            await inst_from.type("2024000001", delay=50)
            await asyncio.sleep(0.3)
            await inst_to.click()
            await inst_to.type("2024000003", delay=50)
            await asyncio.sleep(0.5)

            await page.keyboard.press("Enter")

            try:
                await page.wait_for_url("**/SearchResults**", timeout=15000)
            except:
                pass
            await asyncio.sleep(3)

            print(f"   Found results page: {'SearchResults' in page.url}")

            # Click first result
            print("\n2. Clicking on first document...")
            faux_cells = await page.query_selector_all("td.fauxDetailLink")
            if len(faux_cells) == 0:
                print("   No results found!")
                return

            # Get the instrument number
            row = await faux_cells[0].evaluate_handle("cell => cell.closest('tr')")
            cells = await row.query_selector_all("td")
            instrument = await cells[3].inner_text()
            instrument = instrument.strip()
            print(f"   Instrument: {instrument}")

            await faux_cells[0].click()
            await asyncio.sleep(3)

            if "SearchDetail" not in page.url:
                print("   Failed to navigate to detail")
                return

            print("   On detail page!")

            # Get page count
            body = await page.locator("body").inner_text()
            pages_match = re.search(r"# Pages in Image:\s*(\d+)", body)
            num_pages = int(pages_match.group(1)) if pages_match else 1
            print(f"   Number of pages: {num_pages}")

            # Find the image viewer frame
            print("\n3. Accessing image viewer frame...")
            viewer_frame = page.frame("cphNoMargin_ImageViewer1_ifrLTViewer")
            if not viewer_frame:
                print("   Frame not found!")
                return

            print(f"   Frame URL: {viewer_frame.url[:80]}...")

            # Get frame content
            frame_html = await viewer_frame.content()

            # Find GetImage.aspx URL
            get_image_pattern = r'GetImage\.aspx\?[^"\'>\s]+'
            matches = re.findall(get_image_pattern, frame_html)

            if not matches:
                print("   GetImage.aspx URL not found!")
                return

            print(f"   Found {len(matches)} image URL(s)")
            base_url = matches[0]
            print(f"   Base URL: {base_url[:80]}...")

            # Get cookies
            cookies = await page.context.cookies()
            cookie_str = "; ".join([f'{c["name"]}={c["value"]}' for c in cookies])
            print(f"   Cookies: {len(cookies)} total")

            # Create download directory
            download_dir = "jefferson_downloads"
            os.makedirs(download_dir, exist_ok=True)

            # Download each page
            print(f"\n4. Downloading {num_pages} page(s)...")

            base_url_full = f"https://landrecords.co.jefferson.co.us/Controls/{base_url}"

            async with httpx.AsyncClient() as client:
                for pg in range(num_pages):
                    # Modify Fpg parameter for each page
                    if "Fpg=" in base_url:
                        page_url = re.sub(r'Fpg=\d+', f'Fpg={pg}', base_url_full)
                    else:
                        page_url = base_url_full

                    print(f"\n   Downloading page {pg + 1}...")
                    print(f"   URL: {page_url[:100]}...")

                    response = await client.get(
                        page_url,
                        headers={
                            "Cookie": cookie_str,
                            "Referer": page.url,
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                        },
                        follow_redirects=True,
                        timeout=30
                    )

                    print(f"   Status: {response.status_code}")
                    print(f"   Content-Type: {response.headers.get('content-type', 'unknown')}")
                    print(f"   Size: {len(response.content):,} bytes")

                    if response.status_code == 200 and len(response.content) > 1000:
                        # Determine extension
                        content_type = response.headers.get("content-type", "")
                        if "png" in content_type:
                            ext = ".png"
                        elif "gif" in content_type:
                            ext = ".gif"
                        elif "tif" in content_type:
                            ext = ".tif"
                        else:
                            ext = ".jpg"

                        if num_pages == 1:
                            filename = f"{instrument}{ext}"
                        else:
                            filename = f"{instrument}_p{pg+1}{ext}"

                        filepath = os.path.join(download_dir, filename)
                        with open(filepath, "wb") as f:
                            f.write(response.content)

                        print(f"   SAVED: {filepath}")
                    else:
                        print(f"   FAILED: Response too small or error status")

            print("\n" + "=" * 60)
            print("Download Test Complete!")
            print("=" * 60)

            # List downloaded files
            files = os.listdir(download_dir)
            print(f"\nFiles in {download_dir}:")
            for f in files:
                size = os.path.getsize(os.path.join(download_dir, f))
                print(f"  {f}: {size:,} bytes")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="jefferson_image_error.png")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_image_download())
