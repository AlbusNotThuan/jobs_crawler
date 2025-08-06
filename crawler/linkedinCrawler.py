from patchright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
import time
import re
import os
import random
import threading
from datetime import datetime, timedelta
import hashlib
from bs4 import BeautifulSoup
import sys

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))



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

def clean_html(html_content, logger=None):
    """
    Remove HTML tags and clean up description text.
    
    Args:
        html_content (str): HTML content to clean
        logger (logging.Logger, optional): Logger instance
        
    Returns:
        str: Cleaned text content
    """
    if not html_content or html_content == "Not available":
        return ""
        
    try:
        # Use BeautifulSoup to extract text from HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        
        # Normalize whitespace
        return re.sub(r'\s+', ' ', text).strip()
    except Exception as e:
        if logger:
            logger.error(f"Error cleaning HTML: {e}")
        else:
            print(f"Error cleaning HTML: {e}")
        return html_content  # Return original if parsing fails

def extract_job_details(page, job_id, config, logger=None):
    """
    Extract detailed job information from a LinkedIn job detail page.
    
    Args:
        page: Playwright page object
        job_id: LinkedIn job ID
        config: Configuration dictionary
        logger (logging.Logger, optional): Logger instance
        
    Returns:
        dict: Job details including title, company, location, posted date, and description
    """
    
    # Initialize job details with standard fields
    job_details = {
        "job_id": job_id,
        "job_title": None,
        "company": None,
        "salary": None,
        "location": None,
        "posted_date": datetime.now().strftime("%Y-%m-%d"),
        "job_expertise": None,
        "skills": None,
        "benefits": None,
        "job_description": None,
        "experience": None,
        "yoe": None,
        "work_type": None,
        "link": f"https://www.linkedin.com/jobs/view/{job_id}/",
        "raw_job_description": None,
    }
    
    try:
        # Wait for job details to load
        page.wait_for_selector(".job-details-jobs-unified-top-card__job-title", 
                              timeout=config.get("SELECTOR_TIMEOUT", 30000))
        
        # Extract job title
        title_element = page.locator(".job-details-jobs-unified-top-card__job-title h1")
        if title_element.count() > 0:
            job_details["job_title"] = title_element.inner_text().strip()
            if logger:
                logger.info(f"  Title: {job_details['job_title']}")
            else:
                print(f"  Title: {job_details['job_title']}")

        # Extract company name
        company_element = page.locator(".job-details-jobs-unified-top-card__company-name a")
        if company_element.count() > 0:
            job_details["company"] = company_element.inner_text().strip()
            if logger:
                logger.info(f"  Company: {job_details['company']}")
            else:
                print(f"  Company: {job_details['company']}")

        # Extract location and posted time
        tertiary_desc = page.locator(".job-details-jobs-unified-top-card__tertiary-description-container span.tvm__text")
        if tertiary_desc.count() > 0:
            # First element is typically location
            if tertiary_desc.first.count() > 0:
                job_details["location"] = tertiary_desc.first.inner_text().strip()

            # Look for posted date and apply count
            for element in tertiary_desc.all():
                text = element.inner_text().strip()
                if any(time_indicator in text.lower() for time_indicator in ["ago", "hour", "day", "week", "month"]):
                    job_details["posted_date"] = parse_posted_time(text)
                    if logger:
                        logger.info(f"  Posted Date: {text} → {job_details['posted_date']}")
                    else:
                        print(f"  Posted Date: {text} → {job_details['posted_date']}")
                elif "people clicked apply" in text.lower():
                    if logger:
                        logger.info(f"  Apply Count: {text}")
                    else:
                        print(f"  Apply Count: {text}")
        
        # Extract raw job description
        description_element = page.locator(".jobs-description__content .jobs-box__html-content")
        if description_element.count() > 0:
            html_description = description_element.inner_html().strip()
            job_details["raw_job_description"] = clean_html(html_description)

            # Show preview
            desc_preview = job_details["raw_job_description"][:100].replace("\n", " ") + "..."
            if logger:
                logger.info(f"  RAW Job Description: {desc_preview}")
            else:
                print(f"  RAW Job Description: {desc_preview}")

        # Generate unique job ID hash
        if job_details["job_title"] != None and job_details["company"] != None:
            unique_job_id = generate_job_hash(job_details["job_title"], job_details["company"], job_details["posted_date"])
            job_details["job_id"] = unique_job_id
            if logger:
                logger.info(f"  Generated Job ID: {unique_job_id[:8]}...")
            else:
                print(f"  Generated Job ID: {unique_job_id[:8]}...")

        # Store original LinkedIn ID for reference
        job_details['linkedin_id'] = job_id  
        return job_details
    
    except Exception as e:
        if logger:
            logger.error(f"  Error extracting job details for job ID {job_id}: {e}")
        else:
            print(f"  Error extracting job details for job ID {job_id}: {e}")
        try:
            page.screenshot(path=f"error_job_details_{job_id}.png")
        except:
            pass
        return job_details

# We're removing the crawl_linkedin_job_details function since we're directly using
# extract_job_details from within crawl_linkedin with immediate detail crawling

def analyze_job_async(job_details, job_data_lock, logger=None):
    """
    Phân tích job description bằng AI và cập nhật job_details.
    Hàm này sẽ được chạy trong một thread riêng.
    
    Args:
        job_details (dict): Job details dictionary to update
        job_data_lock (threading.Lock): Lock for thread-safe updates
        logger (logging.Logger, optional): Logger instance
    """
    try:
        import asyncio
        import sys
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from utils.analyze_job import analyze_job_content
        # Tạo event loop mới cho thread này
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run LLM extraction
        analysis_result = loop.run_until_complete(analyze_job_content(job_details["raw_job_description"], job_details["job_title"]))

        # Cập nhật thông tin từ phân tích
        if analysis_result and isinstance(analysis_result, dict):
            # Khóa để đảm bảo thread safety khi cập nhật
            with job_data_lock:
                # Update job_description
                if "job_description" in analysis_result and analysis_result["job_description"] != "Not Specified":
                    job_details["job_description"] = analysis_result["job_description"]
                    if logger:
                        logger.info(f"  Job Description: {job_details['job_description'][:100]}...")
                    else:
                        print(f"  Job Description: {job_details['job_description'][:100]}...")

                # Update job requirements
                if "job_requirements" in analysis_result and analysis_result["job_requirements"] != "Not Specified":
                    job_details["Job_Requirements"] = analysis_result["job_requirements"]
                    if logger:
                        logger.info(f"  Job Requirements: {job_details['Job_Requirements'][:100]}...")
                    else:
                        print(f"  Job Requirements: {job_details['Job_Requirements'][:100]}...")

                # Update years of experience
                if "yoe" in analysis_result and analysis_result["yoe"] != None:
                    job_details["yoe"] = analysis_result["yoe"]
                    if logger:
                        logger.info(f"  Experience for {job_details['job_id'][:8]}: {job_details['yoe']}")
                    else:
                        print(f"  Experience for {job_details['job_id'][:8]}: {job_details['yoe']}")

                # Cập nhật salary
                if "salary" in analysis_result and analysis_result["salary"] != None:
                    job_details["salary"] = analysis_result["salary"]
                    if logger:
                        logger.info(f"  Salary for {job_details['job_id'][:8]}: {job_details['salary']}")
                    else:
                        print(f"  Salary for {job_details['job_id'][:8]}: {job_details['salary']}")

                # Job expertise
                if "job_expertise" in analysis_result and analysis_result["job_expertise"] != None:
                    job_details["job_expertise"] = analysis_result["job_expertise"]
                    if logger:
                        logger.info(f"  Job Expertise for {job_details['job_id'][:8]}: {job_details['job_expertise']}")
                    else:
                        print(f"  Job Expertise for {job_details['job_id'][:8]}: {job_details['job_expertise']}")
                # Update company information
                if "company_information" in analysis_result and analysis_result["company_information"] != None:
                    job_details["company_information"] = analysis_result["company_information"]
                    if logger:
                        logger.info(f"  Company Description for {job_details['job_id'][:8]}: {job_details['company_information'][:100]}...")
                    else:
                        print(f"  Company Description for {job_details['job_id'][:8]}: {job_details['company_information'][:100]}...")

                # store temporary embedding
                if "job_requirements_embedding" in analysis_result:
                    job_details["job_requirements_embedding"] = analysis_result["job_requirements_embedding"]
                if "requirements_embedding" in analysis_result:
                    job_details["requirements_embedding"] = analysis_result["requirements_embedding"]

        loop.close()
    except Exception as ai_error:
        if logger:
            logger.error(f"  Error analyzing job with AI: {ai_error}")
        else:
            print(f"  Error analyzing job with AI: {ai_error}")


def crawl_linkedin(config, logger=None, db_inserter=None):
    """
    Crawls job listings from LinkedIn search results page.
    Extracts job IDs from the search page and immediately navigates to each job detail page
    to collect detailed information.
    
    Args:
        config (dict): Configuration dictionary
        logger (logging.Logger, optional): Logger instance. If None, uses default print statements
        db_inserter (JobDatabaseInserter, optional): Database inserter instance for saving data to database
    """
    # Initialize logger if not provided
    from utils.logger import CrawlerLogger
    if logger is None:
        crawler_logger = CrawlerLogger()
        logger = crawler_logger.get_linkedin_logger()
        
    # Selectors for LinkedIn job search page
    JOB_CARD_SELECTOR = "li[data-occludable-job-id]"
    NEXT_PAGE_SELECTOR = "button[aria-label='View next page']"
    LOGIN_INDICATORS = ["form#login", "input[name='session_key']", "button[aria-label='Sign in']"]
    
    # Import threading để chạy phân tích AI bất đồng bộ
    import threading
    
    # Tạo lock để đảm bảo thread safety khi cập nhật job_data
    job_data_lock = threading.Lock()
    
    # Danh sách các thread đang chạy
    analysis_threads = []
    
    START_URL = config['BASE_URL']
    is_logged_in = config.get('IS_LOGGED_IN', False)
    
    logger.info(f"Starting LinkedIn crawler with {config.get('PAGE_LIMIT', 'unlimited')} page limit")
    logger.info(f"Base URL: {START_URL}")

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
            logger.info(f"Navigating to LinkedIn jobs: {START_URL}")
            page.goto(START_URL, timeout=config["PAGE_LOAD_TIMEOUT"])
            
            # Check if login is required
            login_required = False
            for login_selector in LOGIN_INDICATORS:
                if page.locator(login_selector).count() > 0:
                    login_required = True
                    break
            
            if login_required and not is_logged_in:
                logger.warning("Login required! Please log in manually. You have 60 seconds...")
                time.sleep(60)
                # Check again after login attempt
                for login_selector in LOGIN_INDICATORS:
                    if page.locator(login_selector).count() > 0:
                        logger.error("Still showing login page. Please ensure you're logged in.")
                        page.screenshot(path="linkedin_login_required.png")
                        browser.close()
                        return pd.DataFrame()
            elif is_logged_in:
                logger.info("Using existing login session...")
                time.sleep(3)  # Short wait for page to load
            else:
                logger.info("No login required, proceeding...")
                time.sleep(3)

            # Wait for job cards to load
            logger.info("Waiting for job cards to load...")
            page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible")
        except Exception as e:
            logger.error(f"Error loading the initial page or job cards: {e}")
            page.screenshot(path="error_linkedin_initial_load.png")
            browser.close()
            return pd.DataFrame()

        job_data = []
        seen_job_ids = set()
        current_page_num = 1
        max_pages = config.get('PAGE_LIMIT', 5)

        while True:
            if max_pages != 0 and current_page_num > max_pages:
                logger.info(f"Reached page limit ({max_pages}). Ending crawl.")
                break

            logger.info(f"Crawling search results page {current_page_num}...")
            
            try:
                # Get all job cards on current page
                job_cards = page.locator(JOB_CARD_SELECTOR).all()
                logger.info(f"Found {len(job_cards)} job cards on page {current_page_num}.")

                if not job_cards:
                    logger.warning("No job cards found on this page. Ending crawl.")
                    break

                for i, job_card in enumerate(job_cards):
                    try:
                        # Extract LinkedIn job ID
                        linkedin_job_id = job_card.get_attribute("data-occludable-job-id")
                        
                        # Skip if no ID or duplicate
                        if not linkedin_job_id or linkedin_job_id in seen_job_ids:
                            logger.info(f"  Skipping job card {i+1} with ID {linkedin_job_id} (duplicate or missing ID)")
                            continue
                        
                        seen_job_ids.add(linkedin_job_id)
                        
                        # Create job view URL and navigate to detail page
                        job_view_url = f"https://www.linkedin.com/jobs/view/{linkedin_job_id}/"
                        logger.info(f"  Processing job {i+1}/{len(job_cards)}: ID={linkedin_job_id}")
                        
                        # Open detail page in new tab
                        detail_page = browser.new_page()
                        
                        try:
                            # Navigate to job detail page
                            detail_page.goto(job_view_url, timeout=config["PAGE_LOAD_TIMEOUT"])
                            time.sleep(config.get("PAGE_SLEEP_DURATION", 3))
                            
                            # Extract job details
                            job_details = extract_job_details(detail_page, linkedin_job_id, config, logger)
                            
                            # Thêm job vào job_data
                            with job_data_lock:
                                job_data.append(job_details)
                            
                            # Khởi chạy thread phân tích AI nếu có mô tả
                            if job_details["raw_job_description"] != None:
                                analysis_thread = threading.Thread(
                                    target=analyze_job_async,
                                    args=(job_details, job_data_lock, logger)
                                )
                                analysis_thread.start()
                                analysis_threads.append(analysis_thread)
                            
                        except Exception as detail_error:
                            logger.error(f"  Error processing job detail: {detail_error}")
                            # Add basic placeholder information
                            job_data.append({
                                "job_id": linkedin_job_id,
                                "job_title": None,
                                "company": None,
                                "salary": None,
                                "location": None,
                                "posted_date": datetime.now().strftime("%Y-%m-%d"),
                                "job_expertise": None,
                                "skills": None,
                                "benefits": None,
                                "job_description": None,
                                "link": job_view_url,
                                "raw_job_description": None,
                                "linkedin_id": linkedin_job_id,
                                "yoe": None,
                                "job_requirements": None,
                                "work_type": None,
                                "company_information": None,
                                "job_requirements_embedding": None,
                                "requirements_embedding": None
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
                            logger.info(f"  Waiting {delay} seconds before next job...")
                            time.sleep(delay)
                    except Exception as e:
                        logger.error(f"  Error extracting job ID {i+1}: {e}")

                # --- Pagination ---
                next_button = page.locator(NEXT_PAGE_SELECTOR)
                logger.debug(f"Next page button: {next_button}")
                logger.info(f"Next page button count: {next_button.count()}")
                logger.debug(f"Next page button enabled: {next_button.is_enabled()}")
                if next_button.count() > 0 and next_button.is_enabled():
                    logger.info("Clicking next page button...")
                    next_button.click()
                    time.sleep(config['PAGE_SLEEP_DURATION'])
                    current_page_num += 1
                else:
                    logger.info("No 'Next page' button found or it's disabled. Ending crawl.")
                    break
                    
            except Exception as e:
                logger.error(f"Error on page {current_page_num}: {e}")
                page.screenshot(path=f"error_linkedin_page_{current_page_num}.png")
                break
        
        browser.close()
        
    # Đợi tất cả các thread phân tích AI hoàn thành
    if analysis_threads:
        logger.info(f"\nWaiting for {len(analysis_threads)} AI analysis tasks to complete...")
        for thread in analysis_threads:
            thread.join()
        logger.info("All AI analysis tasks completed.")
    
    # Insert analyzed jobs into database
    if job_data:
        try:
            logger.info(f"\n💾 Inserting {len(job_data)} analyzed jobs into database...")
            # Import the database inserter
            import sys
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from utils.job_database_inserter import JobDatabaseInserter
            
            # Create inserter and insert jobs
            inserter = JobDatabaseInserter()
            stats = inserter.insert_job_batch(job_data)
            
            # Show database statistics
            db_stats = inserter.get_database_stats()
            logger.info(f"\n📊 Final database statistics:")
            logger.info(f"   Total jobs in database: {db_stats.get('total_jobs', 0)}")
            logger.info(f"   Total skills: {db_stats.get('total_skills', 0)}")
            logger.info(f"   Job-skill relationships: {db_stats.get('total_relationships', 0)}")
            
            if 'by_expertise' in db_stats:
                logger.info(f"   Jobs by expertise: {db_stats['by_expertise']}")
            
            inserter.close_connection()
            
        except Exception as db_error:
            logger.error(f"Error inserting jobs into database: {db_error}")

    # Create DataFrame from collected data
    df = pd.DataFrame(job_data)
    df.drop(columns=['job_description_embedding', 'job_requirements_embedding'], inplace=True, errors='ignore')
    if df.empty:
        logger.warning("\nNo job data was successfully crawled.")
    else:
        logger.info(f"\nSuccessfully crawled {len(df)} unique jobs from {current_page_num - 1} page(s).")
    return df

if __name__ == '__main__':
    from utils.load_config import load_config
    import os
    import sys
    sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
    from utils.logger import CrawlerLogger
    
    # Setup paths
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    output_dir = os.path.join(project_root, "output")
    
    # Initialize logger
    crawler_logger = CrawlerLogger()
    logger = crawler_logger.get_linkedin_logger()
    
    # Load configuration from YAML file
    current_dir = os.path.dirname(os.path.realpath(__file__))
    config_path = os.path.join(os.path.dirname(current_dir), "config", "linkedin_config.yaml")
    
    try:
        # Load configuration and set defaults
        config = load_config(config_path)
        logger.info("Loaded LinkedIn crawler configuration")
        
        # Default configuration values
        defaults = {
            "IS_LOGGED_IN": False,
            "USER_DATA_DIR": "./playwright_user_data",
            "CHANNEL": "chrome",
            "HEADLESS": False,  # Set default to False (not headless)
            "NO_VIEWPORT": True,
            "PAGE_LOAD_TIMEOUT": 60000,
            "SELECTOR_TIMEOUT": 30000,
            "NAVIGATION_TIMEOUT": 30000,
            "PAGE_SLEEP_DURATION": 3,
            "PAGE_LIMIT": 2,    # Default to 2 pages
            "DETAIL_SLEEP_MIN": 0.5,
            "DETAIL_SLEEP_MAX": 1.5
        }
        
        # Apply defaults for any missing keys
        for key, value in defaults.items():
            if key not in config:
                config[key] = value
                
        # Ensure output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            logger.info(f"Created output directory: {output_dir}")
        
        # Log configuration
        logger.info(f"Configuration: PAGE_LIMIT={config['PAGE_LIMIT']}, HEADLESS={config['HEADLESS']}")
                
        # Run the crawler
        logger.info("Crawling LinkedIn job listings with details...")
        crawled_data_df = crawl_linkedin(config, logger)
        
        if not crawled_data_df.empty:
            # Display sample of crawled data
            logger.info("\n--- Sample of Crawled Data (First 5 Rows) ---")
            sample_columns = ['JobID', 'Title', 'Company', 'Location', 'Posted_Date']
            sample_df = crawled_data_df[sample_columns].head(5) if all(col in crawled_data_df.columns for col in sample_columns) else crawled_data_df.head(5)
            for _, row in sample_df.iterrows():
                if 'JobID' in row and 'Title' in row and 'Company' in row:
                    logger.info(f"  {row['JobID'][:8]}... | {row['Title']} | {row['Company']}")
                else:
                    logger.info(f"  {row}")
            
            # Save data to CSV
            timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output")
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            csv_file_path = os.path.join(output_dir, f"{timestamp}_linkedin_jobs.csv")
            crawled_data_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
            logger.info(f"\nData successfully saved to {csv_file_path}")
            
        else:
            logger.warning("No data was crawled to display")
    
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.error("Crawler execution failed.")
