from patchright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
import time
import re
import random
from datetime import datetime, timedelta
import hashlib
from bs4 import BeautifulSoup

# Helper functions for job detail page crawling
def parse_posted_time(posted_text, current_date=None):
    """
    Parse the posted time text from LinkedIn and convert to a date.
    
    Args:
        posted_text (str): Text from the posted date element, e.g. "2 days ago"
        current_date (datetime, optional): Base date to calculate from. Defaults to today.
        
    Returns:
        str: Formatted date string in YYYY-MM-DD format
    """
    if current_date is None:
        current_date = datetime.now()
        
    # If text is empty or None, return today's date
    if not posted_text:
        return current_date.strftime("%Y-%m-%d")
    
    # Clean up the text
    text = posted_text.lower().strip()
    
    # Check for "today" or "just now"
    if "today" in text or "just now" in text or "hours ago" in text or "minutes ago" in text or text == "":
        return current_date.strftime("%Y-%m-%d")
    
    # Check for "yesterday"
    if "yesterday" in text:
        date = current_date - timedelta(days=1)
        return date.strftime("%Y-%m-%d")
    
    # Patterns for different time formats
    days_pattern = re.compile(r"(\d+)\s*day[s]?\s*ago")
    weeks_pattern = re.compile(r"(\d+)\s*week[s]?\s*ago")
    months_pattern = re.compile(r"(\d+)\s*month[s]?\s*ago")
    years_pattern = re.compile(r"(\d+)\s*year[s]?\s*ago")
    
    # Check for days
    match = days_pattern.search(text)
    if match:
        days = int(match.group(1))
        date = current_date - timedelta(days=days)
        return date.strftime("%Y-%m-%d")
    
    # Check for weeks
    match = weeks_pattern.search(text)
    if match:
        weeks = int(match.group(1))
        date = current_date - timedelta(weeks=weeks)
        return date.strftime("%Y-%m-%d")
    
    # Check for months
    match = months_pattern.search(text)
    if match:
        months = int(match.group(1))
        # Approximate month calculation
        year = current_date.year
        month = current_date.month - months
        
        # Handle year rollover
        while month <= 0:
            month += 12
            year -= 1
            
        # Get the same day of the resulting month, or the last day if the original day doesn't exist
        try:
            date = datetime(year, month, current_date.day)
        except ValueError:
            # Handle cases like Feb 30 -> Feb 28/29
            if month == 2:  # February
                # Check for leap year
                if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0:
                    date = datetime(year, month, 29)  # Leap year
                else:
                    date = datetime(year, month, 28)  # Non-leap year
            else:
                # Get the last day of the month
                if month in [4, 6, 9, 11]:  # 30 days
                    date = datetime(year, month, 30)
                else:  # 31 days
                    date = datetime(year, month, 31)
                    
        return date.strftime("%Y-%m-%d")
    
    # Check for years
    match = years_pattern.search(text)
    if match:
        years = int(match.group(1))
        # Simply subtract years
        try:
            date = datetime(current_date.year - years, current_date.month, current_date.day)
        except ValueError:
            # Handle Feb 29 in leap years
            date = datetime(current_date.year - years, current_date.month, 28)
        return date.strftime("%Y-%m-%d")
    
    # If no pattern matches, return today's date
    return current_date.strftime("%Y-%m-%d")

def generate_job_hash(title, company, posted_date=None):
    """Generate a unique hash for a job based on title, company, and posted date."""
    if posted_date:
        job_string = f"{title.lower().strip()}|{company.lower().strip()}|{posted_date}"
    else:
        job_string = f"{title.lower().strip()}|{company.lower().strip()}"
    
    job_hash = hashlib.sha256(job_string.encode('utf-8')).hexdigest()
    return job_hash

def clean_html(html_content):
    """
    Remove HTML tags and clean up description text.
    
    Args:
        html_content (str): HTML content to clean
        
    Returns:
        str: Plain text content with HTML removed
    """
    if not html_content or html_content == "Not available":
        return "Not available"
        
    try:
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Extract text
        text = soup.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    except Exception as e:
        print(f"Error cleaning HTML: {e}")
        return html_content  # Return original if parsing fails

def extract_job_details(page, job_id, config):
    """
    Extract detailed job information from a LinkedIn job detail page.
    
    Args:
        page: Playwright page object
        job_id: LinkedIn job ID
        config: Configuration dictionary
        
    Returns:
        dict: Job details including title, company, location, posted date, and description
    """
    # Initialize with exactly the same columns as itviecCrawler output for consistency
    job_details = {
        "JobID": job_id,  # This will be replaced with the generated hash later
        "Title": "Not specified",
        "Company": "Not specified",
        "Salary": "Not specified",
        "Location": "Not specified",
        "Posted_Date": datetime.now().strftime("%Y-%m-%d"),  # Default to today
        "Skills": "Not specified",
        "Benefits": "Not specified",
        "Description": "Not specified",
        "Experience_Requirements": "Not specified",
        "Link": f"https://www.linkedin.com/jobs/view/{job_id}/"
    }
    
    try:
        # Wait for the job details to load
        print(f"  Waiting for job details to load for job ID: {job_id}")
        page.wait_for_selector(".job-details-jobs-unified-top-card__job-title", 
                              timeout=config.get("SELECTOR_TIMEOUT", 30000))
        
        # Extract job title
        title_element = page.locator(".job-details-jobs-unified-top-card__job-title h1")
        if title_element.count() > 0:
            job_details["Title"] = title_element.inner_text().strip()
            print(f"  Title: {job_details['Title']}")
        
        # Extract company name
        company_element = page.locator(".job-details-jobs-unified-top-card__company-name a")
        if company_element.count() > 0:
            job_details["Company"] = company_element.inner_text().strip()
            print(f"  Company: {job_details['Company']}")
        
        # Extract location and posted time
        tertiary_desc = page.locator(".job-details-jobs-unified-top-card__tertiary-description-container span.tvm__text")
        if tertiary_desc.count() > 0:
            # First element is typically location
            if tertiary_desc.first.count() > 0:
                job_details["Location"] = tertiary_desc.first.inner_text().strip()
            
            # Try to find posted date (typically has text like "1 week ago")
            all_tertiary_texts = tertiary_desc.all()
            posted_date_text = None
            for element in all_tertiary_texts:
                text = element.inner_text().strip()
                if any(time_indicator in text.lower() for time_indicator in ["ago", "hour", "day", "week", "month"]):
                    posted_date_text = text
                    # Parse the LinkedIn posting date format to YYYY-MM-DD
                    job_details["Posted_Date"] = parse_posted_time(text)
                    print(f"  Posted Date: {text} → {job_details['Posted_Date']}")
                elif "people clicked apply" in text.lower():
                    # Just print the apply count but don't store it in the job details to match itviec format
                    print(f"  Apply Count: {text}")
        
        # Extract job description
        description_element = page.locator(".jobs-description__content .jobs-box__html-content")
        if description_element.count() > 0:
            # Get the HTML content
            html_description = description_element.inner_html().strip()
            
            # Clean HTML and store only the plain text version (no HTML stored)
            job_details["Description"] = clean_html(html_description)
            
            # Show preview of cleaned text
            desc_preview = job_details["Description"][:100].replace("\n", " ") + "..."
            print(f"  Description: {desc_preview}")
        
        # Generate a unique job ID hash using title, company and posted date
        if job_details["Title"] != "Not specified" and job_details["Company"] != "Not specified":
            unique_job_id = generate_job_hash(job_details["Title"], job_details["Company"], job_details["Posted_Date"])
            job_details["JobID"] = unique_job_id
            print(f"  Generated Job ID: {unique_job_id[:8]}...")  # Print first 8 chars of the hash
        
        print(f"  Successfully extracted details for job ID: {job_id}")
        return job_details
    
    except Exception as e:
        print(f"  Error extracting job details for job ID {job_id}: {e}")
        # Take a screenshot of the failed page for debugging
        try:
            page.screenshot(path=f"error_job_details_{job_id}.png")
        except:
            pass
        return job_details

def crawl_linkedin_job_details(job_ids_df, config):
    """
    Crawls detailed information for LinkedIn job listings from individual job detail pages.
    
    Args:
        job_ids_df: DataFrame containing JobID and Link columns
        config: Configuration dictionary
        
    Returns:
        DataFrame: Detailed job information
    """
    if job_ids_df.empty:
        print("No job IDs provided to crawl details.")
        return pd.DataFrame()
    
    # Ensure required columns exist
    if "JobID" not in job_ids_df.columns or "Link" not in job_ids_df.columns:
        print("Input DataFrame must contain 'JobID' and 'Link' columns.")
        return pd.DataFrame()
    
    LOGIN_INDICATORS = ["form#login", "input[name='session_key']", "button[aria-label='Sign in']"]
    is_logged_in = config.get('IS_LOGGED_IN', False)
    
    job_details_list = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=config["USER_DATA_DIR"],
            channel=config["CHANNEL"],
            headless=config["HEADLESS"],
            no_viewport=config["NO_VIEWPORT"],
            slow_mo=500  # Reduce bot detection
        )
        
        page = browser.new_page()
        
        # Check if login is required first by navigating to LinkedIn
        try:
            print("Checking LinkedIn login status...")
            page.goto("https://www.linkedin.com/", timeout=config["PAGE_LOAD_TIMEOUT"])
            
            # Check if login is required
            login_required = False
            for login_selector in LOGIN_INDICATORS:
                if page.locator(login_selector).count() > 0:
                    login_required = True
                    break
            
            if login_required and not is_logged_in:
                print("Login required! Please log in manually. You have 60 seconds...")
                time.sleep(60)
                # Check again after login attempt
                for login_selector in LOGIN_INDICATORS:
                    if page.locator(login_selector).count() > 0:
                        print("Still showing login page. Please ensure you're logged in.")
                        page.screenshot(path="linkedin_login_required.png")
                        browser.close()
                        return pd.DataFrame()
            
            # If we get here, we're either logged in or no login required
            print("Login check complete. Proceeding with job detail crawling...")
            
        except Exception as e:
            print(f"Error during login check: {e}")
            page.screenshot(path="error_linkedin_initial_load.png")
            browser.close()
            return pd.DataFrame()
        
        # Process each job ID and extract details
        total_jobs = len(job_ids_df)
        for i, (_, row) in enumerate(job_ids_df.iterrows()):
            job_id = row["JobID"]
            job_url = row["Link"]
            
            print(f"\nProcessing job {i+1}/{total_jobs}: ID={job_id}")
            
            try:
                # Navigate to the job detail page
                print(f"  Navigating to: {job_url}")
                page.goto(job_url, timeout=config["PAGE_LOAD_TIMEOUT"])
                
                # Wait for the page to load properly
                time.sleep(config.get("PAGE_SLEEP_DURATION", 3))
                
                # Extract job details
                job_details = extract_job_details(page, job_id, config)
                job_details_list.append(job_details)
                
                # Use efficient random delays to prevent rate limiting
                min_delay = config.get("DETAIL_SLEEP_MIN", 0.5)
                max_delay = config.get("DETAIL_SLEEP_MAX", 1.5)
                
                # Use random delay between min and max values
                delay = round(random.uniform(min_delay, max_delay), 2)
                print(f"  Waiting {delay} seconds before next job...")
                time.sleep(delay)
                
            except Exception as e:
                print(f"  Error processing job ID {job_id}: {e}")
                # Try to take a screenshot for debugging
                try:
                    page.screenshot(path=f"error_job_{job_id}.png")
                except:
                    pass
        
        browser.close()
    
    # Convert the results to DataFrame
    results_df = pd.DataFrame(job_details_list)
    
    if results_df.empty:
        print("\nNo job details were successfully crawled.")
    else:
        print(f"\nSuccessfully crawled details for {len(results_df)} out of {total_jobs} jobs.")
    
    return results_df

def crawl_linkedin(config):
    """
    Crawls job listings from LinkedIn search results page.
    Extracts job IDs from the search page and immediately navigates to each job detail page
    to collect detailed information, similar to how itviecCrawler works.
    """
    # Selectors for LinkedIn job search page
    JOB_CARD_SELECTOR = "li[data-occludable-job-id]"
    NEXT_PAGE_SELECTOR = "button[aria-label='View next page']"
    LOGIN_INDICATORS = ["form#login", "input[name='session_key']", "button[aria-label='Sign in']"]
    
    START_URL = config['BASE_URL']
    is_logged_in = config.get('IS_LOGGED_IN', False)
    crawl_details_immediately = config.get('CRAWL_DETAILS_IMMEDIATELY', True)  # Default to immediate detail crawling

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=config["USER_DATA_DIR"],
            channel=config["CHANNEL"],
            headless=config["HEADLESS"],
            no_viewport=config["NO_VIEWPORT"],
            slow_mo=1000  # Slow down to avoid bot detection
        )

        page = browser.new_page()
        try:
            print(f"Navigating to LinkedIn jobs: {START_URL}")
            page.goto(START_URL, timeout=config["PAGE_LOAD_TIMEOUT"])
            
            # Check if login is required
            login_required = False
            for login_selector in LOGIN_INDICATORS:
                if page.locator(login_selector).count() > 0:
                    login_required = True
                    break
            
            if login_required and not is_logged_in:
                print("Login required! Please log in manually. You have 60 seconds...")
                time.sleep(60)
                # Check again after login attempt
                for login_selector in LOGIN_INDICATORS:
                    if page.locator(login_selector).count() > 0:
                        print("Still showing login page. Please ensure you're logged in.")
                        page.screenshot(path="linkedin_login_required.png")
                        browser.close()
                        return pd.DataFrame()
            elif is_logged_in:
                print("Using existing login session...")
                time.sleep(3)  # Short wait for page to load
            else:
                print("No login required, proceeding...")
                time.sleep(3)

            # No scrolling, we'll just grab visible job cards
            print("Waiting for initial job cards to load...")
            time.sleep(2)

            print("Waiting for job cards to load...")
            page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible")
        except Exception as e:
            print(f"Error loading the initial page or job cards. Error: {e}")
            page.screenshot(path="error_linkedin_initial_load.png")
            browser.close()
            return pd.DataFrame()

        job_data = []
        seen_job_ids = set()
        current_page_num = 1
        max_pages = config.get('PAGE_LIMIT', 5)

        while True:
            if max_pages != 0 and current_page_num > max_pages:
                print(f"Reached page limit ({max_pages}). Ending crawl.")
                break

            print(f"Crawling search results page {current_page_num}...")
            
            try:
                # Just wait for job cards to be visible, no scrolling
                print(f"  Waiting for job cards on page {current_page_num}...")
                page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible")
                time.sleep(1.5)  # Brief pause to ensure page is settled
                
            except Exception as e:
                print(f"Error waiting for content on page {current_page_num}: {e}")
                page.screenshot(path=f"error_linkedin_page_{current_page_num}_load.png")
                break
            
            job_cards = page.locator(JOB_CARD_SELECTOR).all()
            print(f"Found {len(job_cards)} job cards on page {current_page_num}.")

            if not job_cards:
                print("No job cards found on this page. Ending crawl.")
                page.screenshot(path=f"no_job_cards_page_{current_page_num}.png")
                break

            for i, job_card in enumerate(job_cards):
                try:
                    # Extract LinkedIn job ID from data attribute - this is the key piece of information
                    linkedin_job_id = job_card.get_attribute("data-occludable-job-id")
                    
                    # Skip if no ID or duplicate
                    if not linkedin_job_id:
                        continue
                    
                    if linkedin_job_id in seen_job_ids:
                        continue
                    
                    seen_job_ids.add(linkedin_job_id)
                    
                    # Create job view URL for immediate navigation
                    job_view_url = f"https://www.linkedin.com/jobs/view/{linkedin_job_id}/"
                    print(f"  Processing job {i+1}/{len(job_cards)}: ID={linkedin_job_id}")
                    
                    if crawl_details_immediately:
                        # Open a new page for this job detail
                        print(f"  Navigating to job detail page: {job_view_url}")
                        detail_page = browser.new_page()
                        
                        try:
                            # Navigate to the job detail page
                            detail_page.goto(job_view_url, timeout=config["PAGE_LOAD_TIMEOUT"])
                            time.sleep(config.get("PAGE_SLEEP_DURATION", 3))
                            
                            # Extract job details
                            job_details = extract_job_details(detail_page, linkedin_job_id, config)
                            job_data.append(job_details)
                            
                        except Exception as detail_error:
                            print(f"  Error processing job detail page for ID {linkedin_job_id}: {detail_error}")
                            # Add basic information at minimum with all expected columns (matching itviec)
                            job_data.append({
                                "JobID": linkedin_job_id,
                                "Title": "Error retrieving details",
                                "Company": "Not specified",
                                "Salary": "Not specified",
                                "Location": "Not specified",
                                "Posted_Date": datetime.now().strftime("%Y-%m-%d"),
                                "Skills": "Not specified",
                                "Benefits": "Not specified",
                                "Description": "Not specified",
                                "Experience_Requirements": "Not specified",
                                "Link": job_view_url
                            })
                            
                            # Try to capture error screenshot
                            try:
                                detail_page.screenshot(path=f"error_job_detail_{linkedin_job_id}.png")
                            except:
                                pass
                        finally:
                            # Close the detail page
                            detail_page.close()
                            
                            # Add a smart, efficient delay to avoid rate limiting
                            min_delay = config.get("DETAIL_SLEEP_MIN", 0.5)
                            max_delay = config.get("DETAIL_SLEEP_MAX", 1.5)
                            
                            # Use random delay between min and max values
                            delay = round(random.uniform(min_delay, max_delay), 2)
                            print(f"  Waiting {delay} seconds before next job...")
                            time.sleep(delay)
                    else:
                        # Just collect the job ID for later processing with all the expected columns (matching itviec)
                        job_data.append({
                            "JobID": linkedin_job_id,  # LinkedIn ID as placeholder
                            "Title": "Not specified",
                            "Company": "Not specified",
                            "Salary": "Not specified",
                            "Location": "Not specified",
                            "Posted_Date": datetime.now().strftime("%Y-%m-%d"),
                            "Skills": "Not specified",
                            "Benefits": "Not specified",
                            "Description": "Not specified",
                            "Experience_Requirements": "Not specified",
                            "Link": job_view_url
                        })
                        
                except Exception as e:
                    print(f"  Error extracting job ID {i+1}: {e}")

            # --- Pagination ---
            print("\nChecking for next page button...")
            next_button = page.locator(NEXT_PAGE_SELECTOR)
            
            if next_button.count() > 0 and next_button.is_enabled():
                print("Clicking next page button...")
                try:
                    next_button.click()
                    time.sleep(config['PAGE_SLEEP_DURATION'])
                    current_page_num += 1
                except Exception as e:
                    print(f"Error clicking next button: {e}")
                    break
            else:
                print("No 'Next page' button found or it's disabled. Ending crawl.")
                break
        
        browser.close()

    df = pd.DataFrame(job_data)
    if df.empty:
        print("\nNo job data was successfully crawled.")
    else:
        print(f"\nSuccessfully crawled {len(df)} unique jobs from {current_page_num - 1} page(s).")
    return df

if __name__ == '__main__':
    from utils.load_config import load_config
    import os
    
    # Load the LinkedIn configuration from YAML file
    current_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(os.path.dirname(current_dir), "config", "linkedin_config.yaml")
    
    try:
        config = load_config(config_path)
        print("Loaded LinkedIn crawler configuration")
        
        # Set default values for any missing parameters
        defaults = {
            "IS_LOGGED_IN": False,
            "USER_DATA_DIR": "./playwright_user_data",
            "CHANNEL": "chrome",
            "HEADLESS": False,
            "NO_VIEWPORT": True,
            "PAGE_LOAD_TIMEOUT": 60000,
            "SELECTOR_TIMEOUT": 30000,
            "NAVIGATION_TIMEOUT": 30000,
            "PAGE_SLEEP_DURATION": 3,
            "PAGE_LIMIT": 2,
            "DETAIL_SLEEP_MIN": 0.5,
            "DETAIL_SLEEP_MAX": 1.5,
            "CRAWL_DETAILS_IMMEDIATELY": True
        }
        
        # Apply defaults for any missing keys
        for key, value in defaults.items():
            if key not in config:
                config[key] = value
                
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        print("This script will crawl LinkedIn job listings with details and save them to a CSV file.")
        
        crawled_data_df = crawl_linkedin(config)
        
        if not crawled_data_df.empty:
            print("\n--- Sample of Crawled Data (First 5 Rows) ---")
            sample_columns = ['JobID', 'Title', 'Company', 'Location', 'Posted_Date']
            sample_df = crawled_data_df[sample_columns].head(5) if all(col in crawled_data_df.columns for col in sample_columns) else crawled_data_df.head(5)
            for _, row in sample_df.iterrows():
                if 'JobID' in row and 'Title' in row and 'Company' in row:
                    print(f"  {row['JobID'][:8]}... | {row['Title']} | {row['Company']}")
                else:
                    print(row)
            
            try:
                csv_file_path = f"output/{timestamp}_linkedin_jobs.csv"
                crawled_data_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
                print(f"\nData successfully saved to {csv_file_path}")
            except Exception as e:
                print(f"Error occurred while saving data to CSV: {e}")
        else:
            print("No data was crawled to display or save.")
    
    except Exception as e:
        print(f"Error loading configuration: {e}")
        print("Using default configuration instead.")
