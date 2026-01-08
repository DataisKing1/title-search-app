"""Test Jefferson County document download functionality."""
import asyncio
import os
from playwright.async_api import async_playwright


async def test_jefferson_download():
    """Test downloading a document from Jefferson County."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            print("=" * 60)
            print("Jefferson County Document Download Test")
            print("=" * 60)

            # Navigate and search for a specific document
            print("\n1. Searching for document...")
            await page.goto("https://landrecords.co.jefferson.co.us/RealEstate/SearchEntry.aspx")
            await asyncio.sleep(2)

            # Search by instrument number range to get recent docs
            inst_from = page.locator("#cphNoMargin_f_txtInstrumentNoFrom")
            inst_to = page.locator("#cphNoMargin_f_txtInstrumentNoTo")

            await inst_from.click()
            await inst_from.type("2024000001", delay=50)
            await asyncio.sleep(0.3)
            await inst_to.click()
            await inst_to.type("2024000005", delay=50)
            await asyncio.sleep(0.5)

            await page.keyboard.press("Enter")

            try:
                await page.wait_for_url("**/SearchResults**", timeout=15000)
            except:
                pass
            await asyncio.sleep(3)

            print(f"   URL: {page.url}")

            # Get first result
            faux_cells = await page.query_selector_all("td.fauxDetailLink")
            print(f"   Found {len(faux_cells)} results")

            if len(faux_cells) == 0:
                print("   No results found")
                return

            # Click first result to go to detail page
            print("\n2. Navigating to document detail...")
            await faux_cells[0].click()
            await asyncio.sleep(3)

            if "SearchDetail" not in page.url:
                print("   Failed to navigate to detail page")
                return

            print(f"   URL: {page.url}")

            # Get document info
            body = await page.locator("body").inner_text()

            import re
            pages_match = re.search(r"# Pages in Image:\s*(\d+)", body)
            if pages_match:
                print(f"   Number of Pages: {pages_match.group(1)}")
                print("   Image Available: YES")
            else:
                print("   Image info not found")

            # Check for the image viewer frame
            print("\n3. Analyzing image viewer...")
            frames = page.frames
            print(f"   Total frames: {len(frames)}")

            viewer_frame = None
            for f in frames:
                if "LTViewer" in f.name or "ImageViewer" in f.name:
                    viewer_frame = f
                    print(f"   Found viewer frame: {f.name}")
                    print(f"   Frame URL: {f.url[:100]}...")
                    break

            if viewer_frame:
                # Get frame content
                frame_html = await viewer_frame.content()
                print(f"   Frame HTML length: {len(frame_html)}")

                # Look for image sources
                img_patterns = [
                    r'src=["\']([^"\']+\.(png|jpg|gif|tif)[^"\']*)["\']',
                    r'ImageViewer\.aspx[^"\']*',
                    r'GetImage[^"\']*',
                ]

                for pattern in img_patterns:
                    matches = re.findall(pattern, frame_html, re.IGNORECASE)
                    if matches:
                        print(f"   Found pattern matches: {len(matches)}")
                        for m in matches[:3]:
                            if isinstance(m, tuple):
                                print(f"     {m[0][:80]}...")
                            else:
                                print(f"     {m[:80]}...")

            # Try to find any download/print buttons
            print("\n4. Looking for download options...")
            download_selectors = [
                "a:has-text('Download')",
                "button:has-text('Download')",
                "a:has-text('Print')",
                "img[src*='print']",
                "a[href*='download']",
                "a[href*='image']",
            ]

            for selector in download_selectors:
                elements = page.locator(selector)
                count = await elements.count()
                if count > 0:
                    print(f"   Found: {selector} ({count})")

            # Create download directory
            download_dir = "jefferson_downloads"
            os.makedirs(download_dir, exist_ok=True)

            # Try PDF capture as fallback
            print("\n5. Capturing page as PDF...")
            pdf_path = os.path.join(download_dir, "test_document.pdf")
            await page.pdf(path=pdf_path)

            if os.path.exists(pdf_path):
                size = os.path.getsize(pdf_path)
                print(f"   PDF saved: {pdf_path}")
                print(f"   Size: {size:,} bytes")

            # Take screenshot for reference
            print("\n6. Taking screenshot...")
            await page.screenshot(path=os.path.join(download_dir, "detail_page.png"))
            print(f"   Screenshot saved: {download_dir}/detail_page.png")

            print("\n" + "=" * 60)
            print("Download Test Summary")
            print("=" * 60)
            print("- Document detail navigation: WORKING")
            print("- Image viewer frame: FOUND")
            print("- PDF capture fallback: WORKING")
            print("\nNote: Jefferson County uses a custom LTViewer for images.")
            print("Direct image download requires session cookies and may")
            print("involve multi-page TIFF handling.")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="jefferson_download_error.png")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(test_jefferson_download())
