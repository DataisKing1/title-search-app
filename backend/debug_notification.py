"""Debug script to find the notification dialog close button"""
import asyncio
from playwright.async_api import async_playwright


async def debug_notification():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(viewport={'width': 1920, 'height': 1080})
        page = await context.new_page()

        try:
            print('Navigating to Denver portal...')
            await page.goto('https://countyfusion3.kofiletech.us/countyweb/loginDisplay.action?countyname=Denver')
            await asyncio.sleep(2)

            guest_btn = page.locator("input[value*='Guest']")
            if await guest_btn.count() > 0:
                await guest_btn.first.click()
                await asyncio.sleep(2)

            body_frame = page.frame('bodyframe')
            if body_frame and 'disclaimer' in body_frame.url.lower():
                await body_frame.evaluate('() => executeCommand("Accept")')
                await asyncio.sleep(3)

            await page.wait_for_load_state('networkidle')
            await asyncio.sleep(2)

            # List all frames
            print('\n=== All frames ===')
            for f in page.frames:
                print(f'  Frame: {f.name} | URL: {f.url[:60]}...')

            # Check dialogframe for notification
            dialog_frame = page.frame('dialogframe')
            if dialog_frame:
                print('\n=== Checking dialogframe for notification ===')
                print(f'  URL: {dialog_frame.url}')

                # Get dialogframe content
                result = await dialog_frame.evaluate("""() => {
                    return {
                        body: document.body ? document.body.innerHTML.substring(0, 500) : 'no body',
                        hasClose: !!document.querySelector('.panel-tool-close, .window-close, [onclick*="close"]')
                    };
                }""")
                print(f'  Has close button: {result.get("hasClose")}')
                print(f'  Body: {result.get("body", "")[:200]}...')

            # The notification might be rendered as an overlay
            # Let's try to find the main page frame and hide the overlay
            main_frame = page.main_frame
            print('\n=== Trying to close notification from main frame ===')

            # The dialogframe shows the notification content but the window/panel
            # structure is in the parent frame. Let's look for it there.
            close_result = await main_frame.evaluate("""() => {
                // The notification might be a fixed position overlay
                // Find elements with "Notification" text
                let all = document.querySelectorAll('*');
                for (let el of all) {
                    if (el.innerText && el.innerText.includes('Notification')) {
                        // Found notification text, try to find close button
                        let parent = el.closest('.window, .panel, div[style*="position"]');
                        if (parent) {
                            let close = parent.querySelector('.panel-tool-close, [onclick*="close"]');
                            if (close) {
                                close.click();
                                return 'Clicked close in parent';
                            }
                            // Try hiding it
                            parent.style.display = 'none';
                            return 'Hid notification parent';
                        }
                    }
                }
                return 'Could not find notification';
            }""")
            print(f'  Result: {close_result}')

            # Try finding the notification dialog and close it via JavaScript
            # The KoFile system uses a specific function to show/hide dialogs
            body_frame = page.frame('bodyframe')
            if body_frame:
                print('\n=== Trying hideNotification function ===')
                hide_result = await body_frame.evaluate("""() => {
                    // Try various approaches
                    if (typeof hideNotification === 'function') {
                        hideNotification();
                        return 'Called hideNotification()';
                    }
                    if (typeof closeNotification === 'function') {
                        closeNotification();
                        return 'Called closeNotification()';
                    }
                    // Hide the dialogframe iframe
                    let dialogFrame = document.querySelector('iframe[name="dialogframe"]');
                    if (dialogFrame) {
                        dialogFrame.style.display = 'none';
                        dialogFrame.style.visibility = 'hidden';
                        return 'Hid dialogframe iframe';
                    }
                    // Try hideDialog function
                    if (typeof hideDialog === 'function') {
                        hideDialog();
                        return 'Called hideDialog()';
                    }
                    return 'No hide function found';
                }""")
                print(f'  Result: {hide_result}')

            await asyncio.sleep(1)
            await page.screenshot(path='debug_after_close3.png')
            print('\nSaved debug_after_close3.png')

        except Exception as e:
            print(f'Error: {e}')
            import traceback
            traceback.print_exc()

        finally:
            await browser.close()


if __name__ == '__main__':
    asyncio.run(debug_notification())
