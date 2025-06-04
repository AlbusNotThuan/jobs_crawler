from patchright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
import time

def crawl_itviec():
    BASE_URL = "https://itviec.com" # Base for constructing full URLs
    START_URL = f"{BASE_URL}/it-jobs"

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=r"C:\\playwright_user_data_itviec_vanilla", # Using a specific path
            channel="chrome",
            headless=False, # Set to True for non-UI runs later
            no_viewport=True,
        )
        
        main_page = browser.new_page()
        try:
            print(f"Navigating to initial page: {START_URL}")
            main_page.goto(START_URL, timeout=60000)
            # Wait for the job card container, which implies job cards are likely present
            main_page.wait_for_selector(".card-jobs-list .job-card", timeout=30000, state="visible") 
        except Exception as e:
            print(f"Error loading main page or finding initial job items: {e}")
            main_page.screenshot(path="error_initial_load.png")
            browser.close()
            return pd.DataFrame()

        job_data = []
        current_page_num = 1
        max_pages_to_crawl = 5 # Safety limit for pages, adjust as needed (e.g., 2 or 3 for quick tests)

        while current_page_num <= max_pages_to_crawl:
            print(f"Crawling search results page {current_page_num}...")
            try:
                main_page.wait_for_selector(".card-jobs-list .job-card", timeout=30000, state="visible")
                main_page.wait_for_load_state("domcontentloaded", timeout=30000)
                # A short sleep can help ensure all dynamic elements on the list page render
                time.sleep(2) 
            except Exception as e:
                print(f"Error waiting for content on page {current_page_num}: {e}")
                main_page.screenshot(path=f"error_page_{current_page_num}_load.png")
                break 

            job_elements_locators = main_page.locator(".card-jobs-list .job-card")
            count_on_page = job_elements_locators.count()
            print(f"Found {count_on_page} job cards on page {current_page_num}.")

            if count_on_page == 0:
                print(f"No job cards found on page {current_page_num}. This might be the end or an issue.")
                break

            for i in range(count_on_page):
                job_element = job_elements_locators.nth(i)
                try:
                    title_element = job_element.locator("h3[data-search--job-selection-target='jobTitle']")
                    title = title_element.inner_text().strip() if title_element.count() > 0 else "Not specified"
                    
                    job_page_url_raw = title_element.get_attribute("data-url") if title_element.count() > 0 else None
                    job_page_url = "Not specified"
                    if job_page_url_raw:
                        job_page_url = job_page_url_raw.split("?")[0] # Clean tracking params

                    company_element = job_element.locator("span.ims-2 a.text-rich-grey")
                    company = company_element.inner_text().strip() if company_element.count() > 0 else "Not specified"

                    location_element = job_element.locator("div.text-rich-grey.text-truncate[title]")
                    location = location_element.get_attribute("title").strip() if location_element.count() > 0 and location_element.get_attribute("title") else "Not specified"
                    
                    print(f"  Collected: {title} | {company} | {location} | {job_page_url}")

                    job_data.append({
                        "Title": title,
                        "Company": company,
                        "Location": location,
                        "Description": "Not specified (detail page not visited)", # Placeholder
                        "Skills": "Not specified (detail page not visited)",      # Placeholder
                        "Link": job_page_url
                    })
                    
                except Exception as e_job_item:
                    print(f"  Error processing one job card on page {current_page_num}, index {i+1}: {e_job_item}")
                    # Continue to the next job card on the current page

            # --- Pagination ---
            print(f"Checking for next page link from page {current_page_num}...")
            next_page_locator = main_page.locator("div.page.next > a[rel='next']")
            
            if next_page_locator.count() > 0 and next_page_locator.is_visible():
                next_page_href = next_page_locator.get_attribute("href")
                if next_page_href:
                    next_page_url_full = f"{BASE_URL}{next_page_href}" if next_page_href.startswith("/") else next_page_href
                    
                    print(f"Navigating to next page: {next_page_url_full}")
                    main_page.goto(next_page_url_full, timeout=60000)
                    current_page_num += 1
                else:
                    print("Next page link found but 'href' attribute is missing. Ending crawl.")
                    break
            else:
                print("No 'Next page' link found or it's not visible. Ending crawl.")
                break
        
        browser.close()

    df = pd.DataFrame(job_data)
    if df.empty:
        print("No job data was successfully crawled.")
    else:
        # Adjust page count display logic slightly for accuracy if loop breaks early
        actual_pages_crawled = current_page_num -1 if count_on_page > 0 or current_page_num > 1 else 0
        if count_on_page == 0 and current_page_num == 1 and not job_data : actual_pages_crawled = 0 # No jobs on first page
        elif count_on_page == 0 and current_page_num >1 : actual_pages_crawled = current_page_num -1
        elif job_data: actual_pages_crawled = current_page_num # If loop completed max_pages or broke after processing last page

        print(f"\nSuccessfully crawled {len(df)} job summaries from {actual_pages_crawled} page(s).")
    return df

if __name__ == '__main__':
    print("Starting ITviec crawler script (Vanilla - Search Pages Only)...")
    crawled_data_df = crawl_itviec()
    
    if not crawled_data_df.empty:
        print("\n--- Sample of Crawled Job Summaries (First 5 Rows) ---")
        print(crawled_data_df.head())
        
        try:
            csv_file_path = "itviec_jobs_summary.csv"
            crawled_data_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
            print(f"\nSummary data saved to {csv_file_path}")
        except Exception as e:
            print(f"Error occurred while saving data to CSV: {e}")
    else:
        print("No data was crawled to display or save.")