from patchright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
import time
from datetime import datetime
import hashlib

def generate_job_hash(title, company):
    """Generate a unique hash for a job based on title and company."""
    job_string = f"{title.lower().strip()}|{company.lower().strip()}"
    job_hash = hashlib.sha256(job_string.encode('utf-8')).hexdigest()
    return job_hash

def crawl_itviec(config):
    """
    Crawls job listings from ITviec, including detail pages for each job,
    and handles pagination.
    """
    # Selectors are defined here for clarity
    JOB_CARD_SELECTOR = ".card-jobs-list .job-card"
    NEXT_PAGE_SELECTOR = "div.page.next > a[rel='next']"
    
    START_URL = f"{config['BASE_URL']}/it-jobs"

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=config["USER_DATA_DIR"],
            channel="chrome",
            headless=config["HEADLESS"],
            no_viewport=True,
        )

        main_page = browser.new_page()
        try:
            print(f"Navigating to initial page: {START_URL}")
            main_page.goto(START_URL, timeout=config["PAGE_LOAD_TIMEOUT"])
            main_page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible") 
        except Exception as e:
            print(f"Error loading main page or finding initial job items: {e}")
            main_page.screenshot(path="error_initial_load.png")
            browser.close()
            return pd.DataFrame()

        job_data = []
        seen_hashes = set()
        current_page_num = 1

        while True:
            if config['PAGE_LIMIT'] != 0 and current_page_num > config['PAGE_LIMIT']:
                print(f"Reached page limit ({config['PAGE_LIMIT']}). Ending crawl.")
                break

            print(f"Crawling search results page {current_page_num}...")
            try:
                main_page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible")
                time.sleep(config["PAGE_SLEEP_DURATION"]) 
            except Exception as e:
                print(f"Error waiting for content on page {current_page_num}: {e}")
                main_page.screenshot(path=f"error_page_{current_page_num}_load.png")
                break 

            job_elements_locators = main_page.locator(JOB_CARD_SELECTOR)
            count_on_page = job_elements_locators.count()
            print(f"Found {count_on_page} job cards on page {current_page_num}.")

            if count_on_page == 0:
                print("No more job cards found. Ending crawl.")
                break

            for i in range(count_on_page):
                job_element = job_elements_locators.nth(i)
                try:
                    title_element = job_element.locator("h3[data-search--job-selection-target='jobTitle']")
                    title = title_element.inner_text().strip() if title_element.count() > 0 else "Not specified"
                    
                    company_element = job_element.locator("span.ims-2 a.text-rich-grey")
                    company = company_element.inner_text().strip() if company_element.count() > 0 else "Not specified"

                    job_hash = generate_job_hash(title, company)
                    if job_hash in seen_hashes:
                        print(f"  Skipping duplicate: {title} | {company}")
                        continue
                    seen_hashes.add(job_hash)
                    
                    job_page_url_raw = title_element.get_attribute("data-url") if title_element.count() > 0 else None
                    if not job_page_url_raw:
                        print(f"  Skipping job '{title}' due to missing link.")
                        continue
                    job_page_url = job_page_url_raw.split("?")[0]
                    
                    print(f"  Processing job {i+1}/{count_on_page}: {title}")

                    # --- Scrape Job Detail Page ---
                    job_detail_page = browser.new_page()
                    description, experience, benefits, skills, salary, location = ("Not specified",) * 6
                    
                    try:
                        job_detail_page.goto(job_page_url, timeout=config["NAVIGATION_TIMEOUT"])
                        job_detail_page.wait_for_load_state('domcontentloaded')
                        time.sleep(config["PAGE_SLEEP_DURATION"])

                        salary_locator = job_detail_page.locator(".salary .fw-500")
                        salary = salary_locator.inner_text().strip() # if salary_locator.count() > 0 else "Not specified"
                        print(f"    - Salary: {salary}")
                        
                        location_locator = job_detail_page.locator("div.d-inline-block:has(svg.feather-icon.icon-sm.align-middle) > span.normal-text.text-rich-grey")
                        location = location_locator.inner_text().strip() if location_locator.count() > 0 else "Not specified"
                        
                        # Find the div containing "Skills:" and get the tags from the next sibling div
                        skills_container = job_detail_page.locator("div.d-flex.flex-wrap.igap-2:near(div:has-text('Skills:'))")
                        skills_tags = skills_container.locator("a.itag")
                        skills = [tag.inner_text().strip() for tag in skills_tags.all() if tag.inner_text().strip()] if skills_container.count() > 0 else []

                        # Scrape the main text content sections
                        description_locator = job_detail_page.locator("div.paragraph:has(h2:has-text('Job description'))")
                        description = description_locator.inner_text().strip() if description_locator.count() > 0 else "Not specified"

                        experience_locator = job_detail_page.locator("div.paragraph:has(h2:has-text('Your skills and experience'))")
                        experience = experience_locator.inner_text().strip() if experience_locator.count() > 0 else "Not specified"

                        benefits_locator = job_detail_page.locator("div.paragraph:has(h2:has-text('Why you`ll love working here'))")
                        benefits = benefits_locator.inner_text().strip() if benefits_locator.count() > 0 else "Not specified"

                    except Exception as e_detail:
                        print(f"    - Error processing detail page {job_page_url}: {e_detail}")
                        job_detail_page.screenshot(path=f"error_detail_page_{current_page_num}_{i+1}.png")
                    finally:
                        job_detail_page.close()

                    job_data.append({
                        "Title": title,
                        "Company": company,
                        "Salary": salary,
                        "Location": location,
                        "Skills": ", ".join(skills) if skills else "Not specified",
                        "Benefits": benefits,
                        "Description": description,
                        "Experience_Requirements": experience,
                        "Link": job_page_url
                    })
                    
                except Exception as e_job_item:
                    print(f"  - Error processing a job card on page {current_page_num}, index {i+1}: {e_job_item}")

            # --- Pagination ---
            print(f"\nChecking for next page link...")
            next_page_locator = main_page.locator(NEXT_PAGE_SELECTOR)
            
            if next_page_locator.count() > 0 and next_page_locator.is_visible():
                next_page_href = next_page_locator.get_attribute("href")
                if next_page_href:
                    next_page_url_full = f"{config['BASE_URL']}{next_page_href}"
                    print(f"Navigating to next page: {next_page_url_full}")
                    main_page.goto(next_page_url_full, timeout=config["NAVIGATION_TIMEOUT"])
                    current_page_num += 1
                else:
                    print("Next page link found but 'href' is missing. Ending crawl.")
                    break
            else:
                print("No 'Next page' link found. Ending crawl.")
                break
        
        browser.close()

    df = pd.DataFrame(job_data)
    if df.empty:
        print("\nNo job data was successfully crawled.")
    else:
        print(f"\nSuccessfully crawled {len(df)} unique jobs from {current_page_num -1} page(s).")
    return df

if __name__ == '__main__':
    # Configuration dictionary to make the script easy to manage
    config = {
        "BASE_URL": "https://itviec.com",
        "USER_DATA_DIR": "./playwright_user_data",
        "HEADLESS": False, # Set to True for production/unattended runs
        "PAGE_LOAD_TIMEOUT": 60000, # 60 seconds
        "SELECTOR_TIMEOUT": 30000, # 30 seconds
        "NAVIGATION_TIMEOUT": 60000, # 60 seconds
        "PAGE_SLEEP_DURATION": 3, # 3 seconds to wait on list pages
        "DETAIL_PAGE_SLEEP_DURATION": 1.5, # 1.5 seconds to wait on detail pages
        "PAGE_LIMIT": 3 # Set to 0 to crawl all pages, or any number to limit the crawl
    }

    timestamp = datetime.now().strftime("%Y-%m-%d")
    print("This script will crawl ITviec job listings with details and save them to a CSV file.")
    
    crawled_data_df = crawl_itviec(config)
    
    if not crawled_data_df.empty:
        print("\n--- Sample of Crawled Data (First 5 Rows) ---")
        print(crawled_data_df.head())
        
        try:
            csv_file_path = f"{timestamp}_itviec_jobs_detailed.csv"
            crawled_data_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
            print(f"\nData successfully saved to {csv_file_path}")
        except Exception as e:
            print(f"Error occurred while saving data to CSV: {e}")
    else:
        print("No data was crawled to display or save.")