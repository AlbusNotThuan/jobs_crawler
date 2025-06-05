from patchright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
import time
from datetime import datetime
import hashlib

def generate_job_hash(title, company):
    """Generate a hash for a job based on title and company for deduplication."""
    # Create a consistent string from title and company
    job_string = f"{title.lower().strip()}|{company.lower().strip()}"
    # Create a hash of the string
    job_hash = hashlib.sha256(job_string.encode('utf-8')).hexdigest()
    return job_hash

def crawl_itviec(config):
    # Hardcoded selectors for ITviec
    JOB_CARD_SELECTOR = ".card-jobs-list .job-card"
    NEXT_PAGE_SELECTOR = "div.page.next > a[rel='next']"
    
    START_URL = f"{config['BASE_URL']}/it-jobs"

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=config["USER_DATA_DIR"],
            channel="chrome",
            headless=False,
            no_viewport=True,
        )

        main_page = browser.new_page()
        try:
            print(f"Navigating to initial page: {START_URL}")
            main_page.goto(START_URL, timeout=config["PAGE_LOAD_TIMEOUT"])
            # Wait for the job card container, which implies job cards are likely present
            main_page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible") 
        except Exception as e:
            print(f"Error loading main page or finding initial job items: {e}")
            main_page.screenshot(path="error_initial_load.png")
            browser.close()
            return pd.DataFrame()

        if config['SIGN_IN_FLAG'] == False:
            print("Please sign in to your ITviec account manually before proceeding.")
            print("You have 30 seconds to sign in...")
            time.sleep(30000)


        job_data = []
        seen_hashes = set()  # Track job hashes for deduplication
        current_page_num = 1

        while True:  # Changed to crawl until no more pagination is found
            print(f"Crawling search results page {current_page_num}...")
            try:
                main_page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible")
                main_page.wait_for_load_state("domcontentloaded", timeout=config["SELECTOR_TIMEOUT"])
                # A short sleep can help ensure all dynamic elements on the list page render
                time.sleep(config["PAGE_SLEEP_DURATION"]) 
            except Exception as e:
                print(f"Error waiting for content on page {current_page_num}: {e}")
                main_page.screenshot(path=f"error_page_{current_page_num}_load.png")
                break 

            job_elements_locators = main_page.locator(JOB_CARD_SELECTOR)
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
                    
                    # # Generate hash for this job for deduplication
                    # job_hash = generate_job_hash(title, company)
                    
                    # # Skip if we've already seen this job (deduplication)
                    # if job_hash in seen_hashes:
                    #     print(f"  Skipping duplicate: {title} | {company}")
                    #     continue
                    
                    # seen_hashes.add(job_hash)

                    # Visit the job detail page to collect more data
               


                    
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
            next_page_locator = main_page.locator(NEXT_PAGE_SELECTOR)
            
            # Check if we've reached the page limit (if one is set)
            if config['PAGE_LIMIT'] != 'none' and current_page_num == config['PAGE_LIMIT']:
                print(f"Reached page limit ({config['PAGE_LIMIT']}). Ending crawl.")
                break
            
            # Continue to next page if available
            if next_page_locator.count() > 0 and next_page_locator.is_visible():
                next_page_href = next_page_locator.get_attribute("href")
                if next_page_href:
                    next_page_url_full = f"{config['BASE_URL']}{next_page_href}" if next_page_href.startswith("/") else next_page_href
                    
                    print(f"Navigating to next page: {next_page_url_full}")
                    main_page.goto(next_page_url_full, timeout=config["NAVIGATION_TIMEOUT"])
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
    time_now = datetime.now().strftime("%Y-%m-%d")
    print(f"Current time: {time_now}")
    print("This script will crawl ITviec job listings and save the summaries to a CSV file.")
    print("Starting ITviec crawler script (Vanilla - Search Pages Only)...")
    crawled_data_df = crawl_itviec()
   
    
    if not crawled_data_df.empty:
        print("\n--- Sample of Crawled Job Summaries (First 5 Rows) ---")
        print(crawled_data_df.head())
        
        try:
            csv_file_path = f"{time_now}itviec_jobs_summary.csv"
            crawled_data_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
            print(f"\nSummary data saved to {csv_file_path}")
        except Exception as e:
            print(f"Error occurred while saving data to CSV: {e}")
    else:
        print("No data was crawled to display or save.")