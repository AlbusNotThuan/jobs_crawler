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
        
    # Return today's date for empty text or None
    if not posted_text:
        return current_date.strftime("%Y-%m-%d")
    
    # Clean up the text
    text = posted_text.lower().strip()
    
    # Today or recent posts (hours, minutes)
    if any(indicator in text for indicator in ["today", "just now", "hours ago", "minutes ago"]) or text == "":
        return current_date.strftime("%Y-%m-%d")
    
    # Yesterday
    if "yesterday" in text:
        return (current_date - timedelta(days=1)).strftime("%Y-%m-%d")
    
    # Time patterns
    patterns = {
        "days": re.compile(r"(\d+)\s*day[s]?\s*ago"),
        "weeks": re.compile(r"(\d+)\s*week[s]?\s*ago"),
        "months": re.compile(r"(\d+)\s*month[s]?\s*ago"),
        "years": re.compile(r"(\d+)\s*year[s]?\s*ago")
    }
    
    # Check for days
    match = patterns["days"].search(text)
    if match:
        days = int(match.group(1))
        return (current_date - timedelta(days=days)).strftime("%Y-%m-%d")
    
    # Check for weeks
    match = patterns["weeks"].search(text)
    if match:
        weeks = int(match.group(1))
        return (current_date - timedelta(weeks=weeks)).strftime("%Y-%m-%d")
    
    # Check for months
    match = patterns["months"].search(text)
    if match:
        months = int(match.group(1))
        # Calculate new month and year
        year = current_date.year
        month = current_date.month - months
        
        # Handle year rollover
        while month <= 0:
            month += 12
            year -= 1
            
        # Handle month day boundaries
        try:
            date = datetime(year, month, current_date.day)
        except ValueError:
            # Get last day of month if original day doesn't exist
            if month == 2:  # February
                last_day = 29 if (year % 4 == 0 and year % 100 != 0) or year % 400 == 0 else 28
            elif month in [4, 6, 9, 11]:  # 30-day months
                last_day = 30
            else:  # 31-day months
                last_day = 31
            date = datetime(year, month, last_day)
                    
        return date.strftime("%Y-%m-%d")
    
    # Check for years
    match = patterns["years"].search(text)
    if match:
        years = int(match.group(1))
        try:
            date = datetime(current_date.year - years, current_date.month, current_date.day)
        except ValueError:
            # Handle Feb 29 in leap years
            date = datetime(current_date.year - years, current_date.month, 28)
        return date.strftime("%Y-%m-%d")
    
    # Default to today's date if no pattern matches
    return current_date.strftime("%Y-%m-%d")

def generate_job_hash(title, company, posted_date=None):
    """Generate a unique hash for a job based on title, company, and posted date."""
    # Normalize and combine fields
    job_string = f"{title.lower().strip()}|{company.lower().strip()}"
    if posted_date:
        job_string += f"|{posted_date}"
    
    # Generate SHA-256 hash
    return hashlib.sha256(job_string.encode('utf-8')).hexdigest()

def clean_html(html_content):
    """Remove HTML tags and clean up description text."""
    if not html_content or html_content == "Not available":
        return "Not available"
        
    try:
        # Use BeautifulSoup to extract text from HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        
        # Normalize whitespace
        return re.sub(r'\s+', ' ', text).strip()
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
    # Initialize job details with standard fields
    job_details = {
        "JobID": job_id,
        "Title": "Not specified",
        "Company": "Not specified",
        "Salary": "Not specified",
        "Location": "Not specified",
        "Posted_Date": datetime.now().strftime("%Y-%m-%d"),
        "Skills": "Not specified",
        "Benefits": "Not specified",
        "Description": "Not specified",
        "Experience_Requirements": "Not specified",
        "Link": f"https://www.linkedin.com/jobs/view/{job_id}/"
    }
    
    try:
        # Wait for job details to load
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
            
            # Look for posted date and apply count
            for element in tertiary_desc.all():
                text = element.inner_text().strip()
                if any(time_indicator in text.lower() for time_indicator in ["ago", "hour", "day", "week", "month"]):
                    job_details["Posted_Date"] = parse_posted_time(text)
                    print(f"  Posted Date: {text} → {job_details['Posted_Date']}")
                elif "people clicked apply" in text.lower():
                    print(f"  Apply Count: {text}")
        
        # Extract job description
        description_element = page.locator(".jobs-description__content .jobs-box__html-content")
        if description_element.count() > 0:
            html_description = description_element.inner_html().strip()
            job_details["Description"] = clean_html(html_description)
            
            # Show preview
            desc_preview = job_details["Description"][:100].replace("\n", " ") + "..."
            print(f"  Description: {desc_preview}")
        
        # Generate unique job ID hash
        if job_details["Title"] != "Not specified" and job_details["Company"] != "Not specified":
            unique_job_id = generate_job_hash(job_details["Title"], job_details["Company"], job_details["Posted_Date"])
            job_details["JobID"] = unique_job_id
            print(f"  Generated Job ID: {unique_job_id[:8]}...")
        
        return job_details
    
    except Exception as e:
        print(f"  Error extracting job details for job ID {job_id}: {e}")
        try:
            page.screenshot(path=f"error_job_details_{job_id}.png")
        except:
            pass
        return job_details

# We're removing the crawl_linkedin_job_details function since we're directly using
# extract_job_details from within crawl_linkedin with immediate detail crawling

def crawl_linkedin(config):
    """
    Crawls job listings from LinkedIn search results page.
    Extracts job IDs from the search page and immediately navigates to each job detail page
    to collect detailed information.
    """
    # Selectors for LinkedIn job search page
    JOB_CARD_SELECTOR = "li[data-occludable-job-id]"
    NEXT_PAGE_SELECTOR = "button[aria-label='View next page']"
    LOGIN_INDICATORS = ["form#login", "input[name='session_key']", "button[aria-label='Sign in']"]
    
    START_URL = config['BASE_URL']
    is_logged_in = config.get('IS_LOGGED_IN', False)

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

            # Wait for job cards to load
            print("Waiting for job cards to load...")
            page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible")
        except Exception as e:
            print(f"Error loading the initial page or job cards: {e}")
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
                # Get all job cards on current page
                job_cards = page.locator(JOB_CARD_SELECTOR).all()
                print(f"Found {len(job_cards)} job cards on page {current_page_num}.")

                if not job_cards:
                    print("No job cards found on this page. Ending crawl.")
                    break

                for i, job_card in enumerate(job_cards):
                    try:
                        # Extract LinkedIn job ID
                        linkedin_job_id = job_card.get_attribute("data-occludable-job-id")
                        
                        # Skip if no ID or duplicate
                        if not linkedin_job_id or linkedin_job_id in seen_job_ids:
                            continue
                        
                        seen_job_ids.add(linkedin_job_id)
                        
                        # Create job view URL and navigate to detail page
                        job_view_url = f"https://www.linkedin.com/jobs/view/{linkedin_job_id}/"
                        print(f"  Processing job {i+1}/{len(job_cards)}: ID={linkedin_job_id}")
                        
                        # Open detail page in new tab
                        detail_page = browser.new_page()
                        
                        try:
                            # Navigate to job detail page
                            detail_page.goto(job_view_url, timeout=config["PAGE_LOAD_TIMEOUT"])
                            time.sleep(config.get("PAGE_SLEEP_DURATION", 3))
                            
                            # Extract job details
                            job_details = extract_job_details(detail_page, linkedin_job_id, config)
                            job_data.append(job_details)
                            
                        except Exception as detail_error:
                            print(f"  Error processing job detail: {detail_error}")
                            # Add basic placeholder information
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
                            
                            try:
                                detail_page.screenshot(path=f"error_job_detail_{linkedin_job_id}.png")
                            except:
                                pass
                        finally:
                            # Close detail page
                            detail_page.close()
                            
                            # Add random delay between requests
                            delay = round(random.uniform(
                                config.get("DETAIL_SLEEP_MIN", 0.5), 
                                config.get("DETAIL_SLEEP_MAX", 1.5)
                            ), 2)
                            print(f"  Waiting {delay} seconds before next job...")
                            time.sleep(delay)
                    except Exception as e:
                        print(f"  Error extracting job ID {i+1}: {e}")

                # --- Pagination ---
                next_button = page.locator(NEXT_PAGE_SELECTOR)
                
                if next_button.count() > 0 and next_button.is_enabled():
                    print("Clicking next page button...")
                    next_button.click()
                    time.sleep(config['PAGE_SLEEP_DURATION'])
                    current_page_num += 1
                else:
                    print("No 'Next page' button found or it's disabled. Ending crawl.")
                    break
                    
            except Exception as e:
                print(f"Error on page {current_page_num}: {e}")
                page.screenshot(path=f"error_linkedin_page_{current_page_num}.png")
                break
        
        browser.close()

    # Create DataFrame from collected data
    df = pd.DataFrame(job_data)
    if df.empty:
        print("\nNo job data was successfully crawled.")
    else:
        print(f"\nSuccessfully crawled {len(df)} unique jobs from {current_page_num - 1} page(s).")
    return df

if __name__ == '__main__':
    from utils.load_config import load_config
    import os
    
    # Load configuration from YAML file
    current_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(os.path.dirname(current_dir), "config", "linkedin_config.yaml")
    
    try:
        # Load configuration and set defaults
        config = load_config(config_path)
        print("Loaded LinkedIn crawler configuration")
        
        # Default configuration values
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
            "DETAIL_SLEEP_MAX": 1.5
        }
        
        # Apply defaults for any missing keys
        for key, value in defaults.items():
            if key not in config:
                config[key] = value
                
        # Run the crawler
        print("Crawling LinkedIn job listings with details...")
        crawled_data_df = crawl_linkedin(config)
        
        if not crawled_data_df.empty:
            # Display sample of crawled data
            print("\n--- Sample of Crawled Data (First 5 Rows) ---")
            sample_columns = ['JobID', 'Title', 'Company', 'Location', 'Posted_Date']
            sample_df = crawled_data_df[sample_columns].head(5) if all(col in crawled_data_df.columns for col in sample_columns) else crawled_data_df.head(5)
            for _, row in sample_df.iterrows():
                if 'JobID' in row and 'Title' in row and 'Company' in row:
                    print(f"  {row['JobID'][:8]}... | {row['Title']} | {row['Company']}")
                else:
                    print(row)
            
            # Save data to CSV
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            csv_file_path = f"output/{timestamp}_linkedin_jobs.csv"
            crawled_data_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
            print(f"\nData successfully saved to {csv_file_path}")
        else:
            print("No data was crawled to display or save.")
    
    except Exception as e:
        print(f"Error: {e}")
        print("Crawler execution failed.")
