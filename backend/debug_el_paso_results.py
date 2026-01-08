"""Debug the El Paso results table structure."""
import asyncio
from playwright.async_api import async_playwright


async def debug_results():
    """Debug the results table structure."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        try:
            # Navigate and accept disclaimer
            await page.goto("https://publicrecordsearch.elpasoco.com")
            await asyncio.sleep(2)

            disclaimer = page.locator("a:has-text('acknowledge')")
            if await disclaimer.count() > 0:
                await disclaimer.click()
                await asyncio.sleep(1)

            # Go to search
            await page.goto(
                "https://publicrecordsearch.elpasoco.com/RealEstate/SearchEntry.aspx",
                wait_until="networkidle",
            )
            await asyncio.sleep(1)

            # Search for something
            await page.fill("#cphNoMargin_f_txtParty", "Smith")
            await page.click("#cphNoMargin_SearchButtons1_btnSearch")
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            print(f"URL: {page.url}")
            await page.screenshot(path="el_paso_results_debug.png")

            # Explore the grid structure
            print("\n=== Looking for table/grid structure ===")

            # Check for Infragistics grid
            grids = await page.query_selector_all("[id*='WebDataGrid'], [id*='Grid']")
            print(f"Found {len(grids)} grids")

            # Look at the actual data rows
            # Try different selectors
            selectors_to_try = [
                "tr[id*='_r']",  # Infragistics row pattern
                ".igg_Item, .igg_AlternatingItem",  # Infragistics item classes
                "tr.igdRow, tr.igdAltRow",  # Another Infragistics pattern
                "tbody tr",
                "table tr:not(:first-child)",
            ]

            for selector in selectors_to_try:
                rows = await page.query_selector_all(selector)
                if len(rows) > 0 and len(rows) < 100:
                    print(f"\n=== Selector: {selector} ({len(rows)} rows) ===")
                    # Get the first row details
                    for i, row in enumerate(rows[:3]):
                        row_id = await row.get_attribute("id") or "no-id"
                        row_class = await row.get_attribute("class") or ""
                        row_text = await row.inner_text()
                        print(f"Row {i}: id={row_id[:40]}, class={row_class[:40]}")
                        # Show first 200 chars of text
                        text_clean = " ".join(row_text.split())[:200]
                        print(f"  Text: {text_clean}...")

            # Look for the specific data cells
            print("\n=== Looking for OPRID cells ===")
            oprid_cells = await page.query_selector_all("td:has-text('OPRID:')")
            print(f"Found {len(oprid_cells)} OPRID cells")

            if len(oprid_cells) > 0:
                for i, cell in enumerate(oprid_cells[:5]):
                    cell_text = await cell.inner_text()
                    parent_row = await cell.evaluate("el => el.closest('tr').outerHTML.substring(0, 500)")
                    print(f"\nOPRID Cell {i}:")
                    print(f"  Text: {cell_text}")
                    print(f"  Parent row (first 500 chars): {parent_row}")

            # Get the actual row structure
            print("\n=== Looking at fauxDetailLink cells ===")
            faux_cells = await page.query_selector_all("td.fauxDetailLink")
            print(f"Found {len(faux_cells)} fauxDetailLink cells")

            if len(faux_cells) > 0:
                for i, cell in enumerate(faux_cells[:3]):
                    cell_text = await cell.inner_text()
                    # Get the parent row
                    parent = await cell.evaluate("el => el.parentElement.tagName")
                    row_html = await cell.evaluate("""el => {
                        let row = el.closest('tr');
                        if (!row) return 'no row';
                        let cells = row.querySelectorAll('td');
                        return Array.from(cells).map((c, i) => `[${i}]: ${c.innerText.substring(0, 50)}`).join(' | ');
                    }""")
                    print(f"\nFaux Cell {i}:")
                    print(f"  Text: {cell_text[:100]}")
                    print(f"  Parent: {parent}")
                    print(f"  Row cells: {row_html}")

        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_results())
