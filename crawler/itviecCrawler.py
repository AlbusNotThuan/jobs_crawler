from patchright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd
import time
import re
from datetime import datetime, timedelta
import hashlib
import os
import sys

# Add parent directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

def parse_posted_time(posted_text, current_date=None):
    """
    Parse the posted time text from ITviec and convert to a date.
    
    Args:
        posted_text (str): Text from the posted date element, e.g. "Posted 25 minutes ago"
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
    if text.startswith("posted"):
        text = text[6:].strip()  # Remove "posted" prefix
    
    # Check for "today" or "just now"
    if "today" in text or "just now" in text or text == "":
        return current_date.strftime("%Y-%m-%d")
    
    # Check for "yesterday"
    if "yesterday" in text:
        date = current_date - timedelta(days=1)
        return date.strftime("%Y-%m-%d")
        
    # Patterns for different time formats
    minutes_pattern = re.compile(r"(\d+)\s*minute[s]?\s*ago")
    hours_pattern = re.compile(r"(\d+)\s*hour[s]?\s*ago")
    days_pattern = re.compile(r"(\d+)\s*day[s]?\s*ago")
    weeks_pattern = re.compile(r"(\d+)\s*week[s]?\s*ago")
    months_pattern = re.compile(r"(\d+)\s*month[s]?\s*ago")
    years_pattern = re.compile(r"(\d+)\s*year[s]?\s*ago")
    
    # Specific date pattern (like "Jan 15, 2023" or "15 Jan 2023")
    date_pattern = re.compile(r'(\d{1,2})[\/\-\s](\d{1,2})[\/\-\s](\d{2,4})')
    
    # Check for specific date matches first
    date_match = date_pattern.search(text)
    if date_match:
        try:
            day, month, year = date_match.groups()
            if len(year) == 2:  # Convert 2-digit year to 4-digit
                year = "20" + year if int(year) < 50 else "19" + year
            parsed_date = datetime(int(year), int(month), int(day))
            return parsed_date.strftime("%Y-%m-%d")
        except ValueError:
            # If date parsing fails, continue with other patterns
            pass
    
    # Check for minutes
    match = minutes_pattern.search(text)
    if match:
        minutes = int(match.group(1))
        date = current_date - timedelta(minutes=minutes)
        return date.strftime("%Y-%m-%d")
    
    # Check for hours
    match = hours_pattern.search(text)
    if match:
        hours = int(match.group(1))
        date = current_date - timedelta(hours=hours)
        return date.strftime("%Y-%m-%d")
    
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
        # Approximate month calculation (more accurate than fixed 30 days)
        # Handle month rollover and different days in months
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
    
    # If no pattern matches or it's something else, return today's date
    return current_date.strftime("%Y-%m-%d")

def generate_job_hash(title, company, posted_date=None):
    """Generate a unique hash for a job based on title, company, and posted date."""
    if posted_date:
        job_string = f"{title.lower().strip()}|{company.lower().strip()}|{posted_date}"
    else:
        job_string = f"{title.lower().strip()}|{company.lower().strip()}"
    
    job_hash = hashlib.sha256(job_string.encode('utf-8')).hexdigest()
    return job_hash

def crawl_itviec(config, logger=None):
    """
    Crawls job listings from ITviec, including detail pages for each job,
    and handles pagination.
    
    Args:
        config (dict): Configuration dictionary
        logger (logging.Logger, optional): Logger instance. If None, uses default print statements
    """
    # Initialize logger if not provided
    from utils.logger import CrawlerLogger
    if logger is None:
        crawler_logger = CrawlerLogger()
        logger = crawler_logger.get_itviec_logger()
    
    # Selectors are defined here for clarity
    JOB_CARD_SELECTOR = ".card-jobs-list .job-card"
    NEXT_PAGE_SELECTOR = "div.page.next > a[rel='next']"
    
    START_URL = f"{config['BASE_URL']}/it-jobs"

    logger.info(f"Starting ITviec crawler with {config['PAGE_LIMIT']} page limit")
    logger.info(f"Base URL: {config['BASE_URL']}")

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=config["USER_DATA_DIR"],
            channel="chrome",
            headless=config["HEADLESS"],
            no_viewport=True,
        )

        main_page = browser.new_page()
        try:
            logger.info(f"Navigating to initial page: {START_URL}")
            main_page.goto(START_URL, timeout=config["PAGE_LOAD_TIMEOUT"])
            main_page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible") 
        except Exception as e:
            logger.error(f"Error loading main page or finding initial job items: {e}")
            main_page.screenshot(path="error_initial_load.png")
            browser.close()
            return pd.DataFrame()

        job_data = []
        current_page_num = 1

        while True:
            if config['PAGE_LIMIT'] != 0 and current_page_num > config['PAGE_LIMIT']:
                logger.info(f"Reached page limit ({config['PAGE_LIMIT']}). Ending crawl.")
                break

            logger.info(f"Crawling search results page {current_page_num}...")
            try:
                main_page.wait_for_selector(JOB_CARD_SELECTOR, timeout=config["SELECTOR_TIMEOUT"], state="visible")
                time.sleep(config["PAGE_SLEEP_DURATION"]) 
            except Exception as e:
                logger.error(f"Error waiting for content on page {current_page_num}: {e}")
                main_page.screenshot(path=f"error_page_{current_page_num}_load.png")
                break 

            job_elements_locators = main_page.locator(JOB_CARD_SELECTOR)
            count_on_page = job_elements_locators.count()
            logger.info(f"Found {count_on_page} job cards on page {current_page_num}.")

            if count_on_page == 0:
                logger.info("No more job cards found. Ending crawl.")
                break

            for i in range(count_on_page):
                job_element = job_elements_locators.nth(i)
                try:
                    title_element = job_element.locator("h3[data-search--job-selection-target='jobTitle']")
                    title = title_element.inner_text().strip() if title_element.count() > 0 else "Not specified"
                    
                    company_element = job_element.locator("span.ims-2 a.text-rich-grey")
                    company = company_element.inner_text().strip() if company_element.count() > 0 else "Not specified"

                    # Get the URL to the job detail page
                    job_page_url_raw = title_element.get_attribute("data-url") if title_element.count() > 0 else None
                    if not job_page_url_raw:
                        logger.warning(f"  Skipping job '{title}' due to missing link.")
                        continue
                    job_page_url = job_page_url_raw.split("?")[0]
                    
                    logger.info(f"  Processing job {i+1}/{count_on_page}: {title}")

                    # --- Scrape Job Detail Page ---
                    job_detail_page = browser.new_page()
                    description, experience, benefits, skills, salary, location, job_expertise = ("Not specified",) * 7
                    posted_date = datetime.now().strftime("%Y-%m-%d")  # Default to today
                    job_id = generate_job_hash(title, company, posted_date)  # Default ID
                    
                    try:
                        job_detail_page.goto(job_page_url, timeout=config["NAVIGATION_TIMEOUT"])
                        job_detail_page.wait_for_load_state('domcontentloaded')
                        time.sleep(config["PAGE_SLEEP_DURATION"])

                        salary_locator = job_detail_page.locator(".salary .fw-500")
                        salary = salary_locator.inner_text().strip() # if salary_locator.count() > 0 else "Not specified"
                        # salary_locator = job_detail_page.locator(".salary .fw-500").first()
                        # salary = salary_locator.inner_text().strip() if salary_locator.count() > 0 else "Not specified"
                        logger.info(f"    - Salary: {salary}")
                        
                        location_locator = job_detail_page.locator("div.d-inline-block:has(svg.feather-icon.icon-sm.align-middle) > span.normal-text.text-rich-grey")
                        location = location_locator.inner_text().strip() if location_locator.count() > 0 else "Not specified"
                        
                        # Extract Job Expertise
                        job_expertise_locator = job_detail_page.locator("div.imb-4.imb-xl-3.d-flex:has(div:has-text('Job Expertise:')) a.itag")
                        job_expertise = job_expertise_locator.inner_text().strip() if job_expertise_locator.count() > 0 else "Not specified"
                        logger.info(f"    - Job Expertise: {job_expertise}")
                        
                        # Extract posted date using the specific selector for the clock icon element
                        posted_date_locator = job_detail_page.locator("div.d-inline-block:has(svg.feather-icon[href$='#clock']) > span.text-rich-grey")
                        posted_date_text = posted_date_locator.inner_text().strip() if posted_date_locator.count() > 0 else "Posted today"
                        
                        # Parse the posted date text into a standardized date format
                        posted_date = parse_posted_time(posted_date_text)
                        logger.info(f"    - Posted Date: {posted_date_text} → {posted_date}")
                        
                        # Generate unique job ID using title, company and posted date
                        job_id = generate_job_hash(title, company, posted_date)
                        logger.info(f"    - Job ID: {job_id[:8]}...")  # Print first 8 chars of the hash
                        
                        # Find the div containing "Skills:" and get the tags from the next sibling div
                        skills_container = job_detail_page.locator("div.d-flex.flex-wrap.igap-2:near(div:has-text('Skills:'))")
                        skills_tags = skills_container.locator("a.itag")
                        if skills_container.count() > 0:
                            # Extract and clean each skill tag
                            skills = []
                            for tag in skills_tags.all():
                                skill_text = tag.inner_text().strip()
                                if skill_text:  # Only add non-empty skills
                                    # Remove any newlines or excessive spaces
                                    clean_skill = re.sub(r'\s+', ' ', skill_text).strip()
                                    skills.append(clean_skill)
                        else:
                            skills = []

                        # Scrape and clean the main text content sections
                        
                        # Process job description
                        description_locator = job_detail_page.locator("div.paragraph:has(h2:has-text('Job description'))")
                        if description_locator.count() > 0:
                            raw_description = description_locator.inner_text().strip()
                            # Remove the heading from the content
                            if "Job description" in raw_description:
                                description_parts = raw_description.split("Job description", 1)
                                if len(description_parts) > 1:
                                    raw_description = description_parts[1].strip()
                            # Clean up the text - replace multiple newlines with a single space
                            description = re.sub(r'\s*\n\s*', ' ', raw_description)
                            # Replace multiple spaces with a single space
                            description = re.sub(r'\s+', ' ', description).strip()
                        else:
                            description = "Not specified"
                            
                        # Process experience requirements
                        experience_locator = job_detail_page.locator("div.paragraph:has(h2:has-text('Your skills and experience'))")
                        if experience_locator.count() > 0:
                            raw_experience = experience_locator.inner_text().strip()
                            # Remove the heading from the content
                            if "Your skills and experience" in raw_experience:
                                experience_parts = raw_experience.split("Your skills and experience", 1)
                                if len(experience_parts) > 1:
                                    raw_experience = experience_parts[1].strip()
                            # Clean up the text - replace multiple newlines with a single space
                            experience = re.sub(r'\s*\n\s*', ' ', raw_experience)
                            # Replace multiple spaces with a single space
                            experience = re.sub(r'\s+', ' ', experience).strip()
                        else:
                            experience = "Not specified"
                            
                        # Process benefits
                        benefits_locator = job_detail_page.locator("div.paragraph:has(h2:has-text('Why you`ll love working here'))")
                        if benefits_locator.count() > 0:
                            raw_benefits = benefits_locator.inner_text().strip()
                            # Remove the heading from the content
                            if "Why you`ll love working here" in raw_benefits:
                                benefits_parts = raw_benefits.split("Why you`ll love working here", 1)
                                if len(benefits_parts) > 1:
                                    raw_benefits = benefits_parts[1].strip()
                            # Clean up the text - replace multiple newlines with a single space
                            benefits = re.sub(r'\s*\n\s*', ' ', raw_benefits)
                            # Replace multiple spaces with a single space
                            benefits = re.sub(r'\s+', ' ', benefits).strip()
                        else:
                            benefits = "Not specified"

                    except Exception as e_detail:
                        logger.error(f"    - Error processing detail page {job_page_url}: {e_detail}")
                        job_detail_page.screenshot(path=f"error_detail_page_{current_page_num}_{i+1}.png")
                    finally:
                        job_detail_page.close()

                    job_data.append({
                        "JobID": job_id,
                        "Title": title,
                        "Company": company,
                        "Salary": salary,
                        "Location": location,
                        "Posted_Date": posted_date,
                        "Job_Expertise": job_expertise,
                        "Skills": ", ".join(skills) if skills else "Not specified",
                        "Benefits": benefits,
                        "Description": description,
                        "Experience_Requirements": experience,
                        "Link": job_page_url
                    })
                    
                except Exception as e_job_item:
                    logger.error(f"  - Error processing a job card on page {current_page_num}, index {i+1}: {e_job_item}")

            # --- Pagination ---
            logger.info(f"Checking for next page link...")
            next_page_locator = main_page.locator(NEXT_PAGE_SELECTOR)
            
            if next_page_locator.count() > 0 and next_page_locator.is_visible():
                next_page_href = next_page_locator.get_attribute("href")
                if next_page_href:
                    next_page_url_full = f"{config['BASE_URL']}{next_page_href}"
                    logger.info(f"Navigating to next page: {next_page_url_full}")
                    main_page.goto(next_page_url_full, timeout=config["NAVIGATION_TIMEOUT"])
                    current_page_num += 1
                else:
                    logger.info("Next page link found but 'href' is missing. Ending crawl.")
                    break
            else:
                logger.info("No 'Next page' link found. Ending crawl.")
                break
        
        browser.close()

    df = pd.DataFrame(job_data)
    if df.empty:
        logger.warning("No job data was successfully crawled.")
    else:
        logger.info(f"Successfully crawled {len(df)} unique jobs from {current_page_num -1} page(s).")
    return df

if __name__ == '__main__':
    import argparse
    import os
    import sys
    from utils.logger import CrawlerLogger
    from utils.job_database_inserter import JobDatabaseInserter

    # Setup argument parser
    parser = argparse.ArgumentParser(description='Crawl ITviec job listings')
    parser.add_argument('--pages', type=int, default=3, help='Number of pages to crawl (0 for all)')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--save-to-db', action='store_true', help='Save crawled data to database')
    parser.add_argument('--output-dir', type=str, default='output', help='Directory to save CSV files')
    args = parser.parse_args()
    
    # Setup logger
    crawler_logger = CrawlerLogger()
    logger = crawler_logger.get_itviec_logger()
    
    # Ensure output directory exists
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        logger.info(f"Created output directory: {args.output_dir}")

    # Configuration dictionary
    config = {
        "BASE_URL": "https://itviec.com",
        "USER_DATA_DIR": "./playwright_user_data",
        "HEADLESS": args.headless,
        "PAGE_LOAD_TIMEOUT": 60000, # 60 seconds
        "SELECTOR_TIMEOUT": 30000, # 30 seconds
        "NAVIGATION_TIMEOUT": 60000, # 60 seconds
        "PAGE_SLEEP_DURATION": 3, # 3 seconds to wait on list pages
        "DETAIL_PAGE_SLEEP_DURATION": 1.5, # 1.5 seconds to wait on detail pages
        "PAGE_LIMIT": args.pages # Set to 0 to crawl all pages
    }

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    logger.info("Starting ITviec crawler with the following configuration:")
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
    
    # Initialize database connection if needed
    db_inserter = None
    if args.save_to_db:
        try:
            logger.info("Initializing database connection...")
            db_inserter = JobDatabaseInserter()
            logger.info("Database connection established successfully")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            logger.info("Continuing without database support")
            args.save_to_db = False
    
    # Run the crawler
    crawled_data_df = crawl_itviec(config, logger)
    
    if not crawled_data_df.empty:
        logger.info(f"Successfully crawled {len(crawled_data_df)} jobs")
        logger.info("--- Sample of Crawled Data (First 5 Rows) ---")
        
        # Save to CSV
        try:
            csv_file_path = os.path.join(args.output_dir, f"{timestamp}_itviec_jobs.csv")
            crawled_data_df.to_csv(csv_file_path, index=False, encoding='utf-8-sig')
            logger.info(f"Data successfully saved to {csv_file_path}")
        except Exception as e:
            logger.error(f"Error saving data to CSV: {e}")
        
        # Save to database if requested
        if args.save_to_db and db_inserter:
            logger.info("Saving data to database...")
            job_count = 0
            total_skills = 0
            
            try:
                for _, job in crawled_data_df.iterrows():
                    job_dict = job.to_dict()
                    db_job_id = db_inserter.insert_job(job_dict)
                    
                    if db_job_id:
                        job_count += 1
                        skills_count = db_inserter.insert_job_skills(db_job_id, job_dict.get("Skills", ""))
                        total_skills += skills_count
                
                # Commit all changes
                db_inserter.conn.commit()
                logger.info(f"Successfully saved {job_count} jobs with {total_skills} skills to database")
                
                # Get database stats
                stats = db_inserter.get_database_stats()
                logger.info(f"Database now contains {stats.get('total_jobs', 0)} jobs and {stats.get('total_skills', 0)} skills")
                
            except Exception as e:
                logger.error(f"Error saving to database: {e}")
                if db_inserter and db_inserter.conn:
                    db_inserter.conn.rollback()
                    
            finally:
                if db_inserter:
                    db_inserter.close_connection()
    else:
        logger.warning("No data was crawled to display or save.")