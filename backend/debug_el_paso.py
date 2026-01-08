"""Debug script to explore El Paso County portal structure."""
import asyncio
from playwright.async_api import async_playwright


async def debug_el_paso():
    """Debug the El Paso County portal."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            print("Navigating to El Paso County portal...")
            await page.goto("https://publicrecordsearch.elpasoco.com")
            await asyncio.sleep(3)

            print(f"URL: {page.url}")
            await page.screenshot(path="el_paso_step1.png")
            print("Screenshot: el_paso_step1.png")

            # Check page content
            body_text = await page.locator("body").inner_text()
            print(f"\nPage text (first 500 chars):\n{body_text[:500]}")

            # Check for links
            links = await page.query_selector_all("a")
            print(f"\nFound {len(links)} links")
            for link in links[:10]:
                text = await link.inner_text()
                href = await link.get_attribute("href")
                print(f"  Link: {text[:50]} -> {href}")

            # Look for disclaimer link
            disclaimer = page.locator("a:has-text('acknowledge')")
            print(f"\nDisclaimer links found: {await disclaimer.count()}")

            if await disclaimer.count() > 0:
                print("Clicking disclaimer...")
                await disclaimer.first.click()
                await asyncio.sleep(3)

                print(f"After disclaimer URL: {page.url}")
                await page.screenshot(path="el_paso_step2.png")
                print("Screenshot: el_paso_step2.png")

            # Now try to navigate to search page
            print("\nNavigating to Real Estate search...")
            await page.goto(
                "https://publicrecordsearch.elpasoco.com/RealEstate/SearchEntry.aspx",
                wait_until="networkidle",
            )
            await asyncio.sleep(2)

            print(f"Search page URL: {page.url}")
            await page.screenshot(path="el_paso_step3.png")
            print("Screenshot: el_paso_step3.png")

            # Check what inputs are on the page
            inputs = await page.query_selector_all("input")
            print(f"\nFound {len(inputs)} input fields")
            for inp in inputs[:15]:
                inp_id = await inp.get_attribute("id") or "no-id"
                inp_name = await inp.get_attribute("name") or "no-name"
                inp_type = await inp.get_attribute("type") or "text"
                print(f"  Input: id={inp_id[:50]}, name={inp_name[:30]}, type={inp_type}")

            # Check for buttons
            buttons = await page.query_selector_all("input[type='submit'], button")
            print(f"\nFound {len(buttons)} buttons")
            for btn in buttons:
                btn_id = await btn.get_attribute("id") or "no-id"
                btn_value = await btn.get_attribute("value") or ""
                btn_text = await btn.inner_text() if await btn.get_attribute("type") != "submit" else btn_value
                print(f"  Button: id={btn_id[:50]}, value={btn_text[:30]}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            await page.screenshot(path="el_paso_debug_error.png")

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_el_paso())
