from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import pandas as pd # Pandas is imported but not used for direct data storage in this script version

def main():
    BASE_URL = "https://itviec.com/it-jobs"
    # Selector for the main container that holds all the job card listings
    JOB_LIST_CONTAINER_SELECTOR = ".card-jobs-list"
    # Your confirmed selector for an individual job card, to be used within the container
    JOB_CARD_SELECTOR_WITHIN_LIST = ".job-card" 

    # Using a new user_data_dir for this specific test run
    debug_user_data_dir = r"C:\\playwright_user_data_debug_20_elements" 

    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=debug_user_data_dir,
            channel="chrome",
            headless=False, # Keep False to observe browser actions
            no_viewport=True,
        )
        
        main_page = browser.new_page()
        
        try:
            print(f"Navigating to {BASE_URL}...")
            # 'networkidle' waits for network activity to be idle, good for dynamic pages
            main_page.goto(BASE_URL, timeout=60000)
            
            print(f"Waiting for the job list container ('{JOB_LIST_CONTAINER_SELECTOR}') to become visible...")
            job_list_container_locator = main_page.locator(JOB_LIST_CONTAINER_SELECTOR)
            job_list_container_locator.wait_for(state="visible", timeout=30000)
            print("Job list container is visible.")

            print(f"Locating all job cards ('{JOB_CARD_SELECTOR_WITHIN_LIST}') within the list container...")
            # Create a locator for all job cards within the specific container
            job_cards_locator = job_list_container_locator.locator(JOB_CARD_SELECTOR_WITHIN_LIST)
            
            # Check if cards are found, wait a bit longer if none are immediately present
            if job_cards_locator.count() == 0:
                print("No job cards immediately found. Waiting a bit longer for the first card to appear...")
                try:
                    # Wait for the first potential card to ensure the list isn't processed while empty
                    job_cards_locator.first.wait_for(state="visible", timeout=15000) 
                except PlaywrightTimeoutError:
                    print("Timeout: Still no job cards became visible after an extended wait.")
                    main_page.screenshot(path="debug_no_cards_after_extended_wait.png")
                    # Re-raise to be caught by the outer try-except block
                    raise 

            num_cards_found = job_cards_locator.count()
            if num_cards_found > 0:
                print(f"Found {num_cards_found} job card(s). Fetching inner texts for up to the first 20...")
                
                # Efficiently get inner texts from all located job cards
                all_texts = job_cards_locator.all_inner_texts()
                
                # Slice to get texts from the first 20 cards (or fewer if less than 20 found)
                job_texts_to_print = all_texts[:20]

                if job_texts_to_print:
                    print(f"\n--- Inner Texts of the First {len(job_texts_to_print)} of {num_cards_found} Job Card(s) Found ---")
                    for i, text in enumerate(job_texts_to_print):
                        print(f"\n--- Job {i+1} ---")
                        print(text.strip()) # Clean up whitespace
                        print("--------------------")
                else:
                    # This case should be rare if num_cards_found > 0 and all_inner_texts() works
                    print("Could not extract text from any job cards, even though locators may have matched elements.")
            else:
                print("No job cards were found matching the selectors within the job list container.")
                main_page.screenshot(path="debug_no_job_cards_found_in_container.png")
                print("Screenshot saved as 'debug_no_job_cards_found_in_container.png'.")

        except PlaywrightTimeoutError as e:
            print(f"A timeout error occurred: {e}")
            main_page.screenshot(path="debug_timeout_error_multi_elements.png")
            print("Screenshot captured due to timeout.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            main_page.screenshot(path="debug_unexpected_error_multi_elements.png")
            print("Screenshot captured due to an unexpected error.")
        finally:
            print("\nScript execution finished.")
            print("The browser window will remain open until you press Enter in this console.")
            input("Press Enter here to close the browser and end the script...")
            browser.close()
            
    # This script primarily prints the output. 
    # If you wanted to return the data (e.g., job_texts_to_print) for further processing,
    # you could modify the function to do so.
    return pd.DataFrame() # Returning an empty DataFrame as per the original script's structure

if __name__ == "__main__":
    print("--- Running Playwright Script: Fetching Texts of First 20 Job Cards ---")
    main()