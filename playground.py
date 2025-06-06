from patchright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

url = "https://itviec.com/it-jobs/vts-ky-su-giai-phap-nghiep-vu-business-analyst-viettel-group-4456"
with sync_playwright() as p:
    browser = p.chromium.launch_persistent_context(
        user_data_dir="./playwright_user_data",
        channel="chrome",
        headless=False,
        no_viewport=True,
    )

    page = browser.new_page()
    try:
        page.goto(url, timeout=30000)
        page.wait_for_load_state('domcontentloaded')
        print("Page loaded successfully. The browser will remain open.")
        print("--- Press Enter in this console window to close the browser and end the script. ---")

        locator = page.locator("div.d-flex.flex-wrap.igap-2:near(div:has-text('Skills:'))")
        locator.highlight()  # Highlight the element for visibility
        salary = locator.inner_text().strip() if locator.count() > 0 else "Not specified"
        print(f"{locator.inner_text().strip()}")
        print(salary)
        # This line will pause the script and wait for your input
        input()

    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        # The browser will only close after the input() is received or an error occurs
        print("Closing browser...")
        browser.close()

    
    
