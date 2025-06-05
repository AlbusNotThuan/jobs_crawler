import argparse
import sys
import os
from datetime import datetime
from typing import Dict, Any, Optional
import pandas as pd
import importlib

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.load_config import load_config, validate_required_keys
from utils.arg_parser import create_parser
from utils.colors import Colors


class JobCrawlerManager:
    """Central manager for all job crawler operations."""
    
    def __init__(self):
        self.supported_sites = {}
        self.load_global_config()
    
    def load_global_config(self) -> None:
        """Load global configuration to get supported sites."""
        try:
            global_config_path = os.path.join(os.path.dirname(__file__), 'config', 'global.yaml')
            global_config = load_config(global_config_path)
            
            for site_id, site_info in global_config.get('sites', {}).items():
                if site_info.get('enabled', True):
                    # Dynamically import the crawler function
                    try:
                        module = importlib.import_module(site_info['crawler_module'])
                        crawler_func = getattr(module, site_info['crawler_function'])
                        
                        self.supported_sites[site_id] = {
                            'name': site_info['name'],
                            'crawler_func': crawler_func,
                            'config_file': site_info['config_file'],
                            'description': site_info['description']
                        }
                    except (ImportError, AttributeError) as e:
                        print(Colors.yellow(f"Warning: Could not load crawler for {site_id}: {e}"))
                        
        except Exception as e:
            print(Colors.red(f"Error loading global config: {e}"))
            # Fallback to hardcoded config if global config fails
            # from itviecCrawler import crawl_itviec
            # self.supported_sites = {
            #     'itviec': {
            #         'name': 'ITviec',
            #         'crawler_func': crawl_itviec,
            #         'config_file': 'configs/itviec_config.yaml',
            #         'description': 'Vietnamese IT job platform'
            #     }
            # }
    
    def list_supported_sites(self) -> None:
        """Display all supported job sites."""
        print(f"\n{Colors.cyan('Supported Job Sites:')}")
        print("=" * 50)
        for site_id, site_info in self.supported_sites.items():
            print(f"  {site_id:10} - {site_info['name']} ({site_info['description']})")
        print()
    
    def load_site_config(self, site: str, custom_config: Optional[str] = None) -> Dict[str, Any]:
        """Load configuration for a specific site."""
        if site not in self.supported_sites:
            raise ValueError(f"Unsupported site: {site}")
        
        site_info = self.supported_sites[site]
        config_file = custom_config or site_info['config_file']
        
        try:
            # Load YAML config - no defaults, everything must be in config file
            config = load_config(config_file)
            print(Colors.green(f"Loaded config from: {config_file}"))
            return config
            
        except Exception as e:
            print(Colors.red(f"Error loading config for {site}: {e}"))
            raise
    
    def crawl_site(self, site: str, config: Dict[str, Any]) -> pd.DataFrame:
        """Execute crawling for a specific site."""
        if site not in self.supported_sites:
            raise ValueError(f"Unsupported site: {site}")
        
        site_info = self.supported_sites[site]
        crawler_func = site_info['crawler_func']
        
        print(f"{Colors.blue('Starting crawl for')} {Colors.bold(site_info['name'])}...")
        print(f"   Base URL: {config.get('BASE_URL', 'Not specified')}")
        print(f"   Headless: {config.get('HEADLESS', False)}")
        print(f"   Timeout: {config.get('PAGE_LOAD_TIMEOUT', 60000)}ms")
        print("-" * 50)
        
        start_time = datetime.now()
        
        try:
            df = crawler_func(config)
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            print(Colors.green(f"Crawl completed for {site_info['name']}"))
            print(f"   Duration: {duration}")
            print(f"   Jobs found: {len(df) if not df.empty else 0}")
            
            return df
            
        except Exception as e:
            print(Colors.red(f"Crawl failed for {site_info['name']}: {e}"))
            raise
    
    def save_results(self, df: pd.DataFrame, site: str, output_file: Optional[str] = None) -> str:
        """Save crawling results to CSV file."""
        if df.empty:
            print(Colors.yellow("No data to save (empty DataFrame)"))
            return ""
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        folder_prefix = os.path.join(os.path.dirname(__file__), 'output')
        if output_file:
            filename = f"{folder_prefix}/{output_file}"
        else:
            filename = f"{folder_prefix}/{timestamp}_{site}_jobs.csv"
        
        try:
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(Colors.green(f"Results saved to: {filename}"))
            return filename
        except Exception as e:
            print(Colors.red(f"Error saving results: {e}"))
            raise
    
    def show_results_summary(self, df: pd.DataFrame, site: str) -> None:
        """Display summary of crawling results."""
        if df.empty:
            print("No results to display")
            return
        
        print(f"\n{Colors.cyan('Crawling Results Summary for')} {Colors.bold(site.upper())}:")
        print("=" * 60)
        print(f"Total jobs found: {len(df)}")
        
        if 'Company' in df.columns:
            top_companies = df['Company'].value_counts().head(5)
            print(f"\nTop 5 companies by job count:")
            for company, count in top_companies.items():
                print(f"  {company}: {count} jobs")
        
        if 'Location' in df.columns:
            top_locations = df['Location'].value_counts().head(5)
            print(f"\nTop 5 locations:")
            for location, count in top_locations.items():
                print(f"  {location}: {count} jobs")
        
        print(f"\nSample of first 3 jobs:")
        print("-" * 60)
        display_cols = ['Title', 'Company', 'Location']
        available_cols = [col for col in display_cols if col in df.columns]
        
        for i, row in df.head(3).iterrows():
            print(f"Job {i+1}:")
            for col in available_cols:
                print(f"  {col}: {row[col]}")
            print()


def main():
    """Main application entry point."""
    print("Job Crawler")
    print("=" * 40)
    
    # Initialize crawler manager first to get supported sites
    manager = JobCrawlerManager()
    
    # Create parser with supported sites
    supported_sites = list(manager.supported_sites.keys())
    parser = create_parser(supported_sites)
    args = parser.parse_args()
    
    # Handle list sites request
    if args.list_sites:
        manager.list_supported_sites()
        return
    
    # Validate required arguments
    if not args.site:
        print(Colors.red("Error: --site argument is required"))
        print("Use --list-sites to see available options")
        parser.print_help()
        sys.exit(1)
    
    try:
        # Load configuration
        print(f"{Colors.blue('Loading configuration for')} {Colors.bold(args.site)}...")
        config = manager.load_site_config(args.site, args.config)
        
        # Override headless mode if specified
        if args.headless:
            config['HEADLESS'] = True
            print(Colors.yellow("Running in headless mode"))
        
        # Validate configuration
        if args.verbose:
            print(Colors.cyan("Configuration loaded:"))
            for key, value in config.items():
                print(f"   {key}: {value}")
        
        # Execute crawling
        df = manager.crawl_site(args.site, config)
        
        # Save results
        if not df.empty:
            output_file = manager.save_results(df, args.site, args.output)
            
            # Show summary if requested (default is off)
            if args.show_summary:
                manager.show_results_summary(df, args.site)
        else:
            print(Colors.yellow("No jobs were crawled"))
    
    except KeyboardInterrupt:
        print(Colors.yellow("\nCrawling interrupted by user"))
        sys.exit(1)
    except Exception as e:
        print(Colors.red(f"Error: {e}"))
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
    
    print(Colors.green("\nJob crawling completed successfully!"))


if __name__ == '__main__':
    main()

