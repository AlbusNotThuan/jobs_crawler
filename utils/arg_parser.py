import argparse
from typing import List


def create_parser(supported_sites: List[str]) -> argparse.ArgumentParser:
    """Create command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Job Crawler - A unified tool for crawling job sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  %(prog)s --site itviec                          # Crawl ITviec
  %(prog)s --site itviec --config custom.yaml    # Use custom config file
  %(prog)s --site itviec --output my_jobs.csv    # Save to specific file
  %(prog)s --list-sites                          # Show supported sites
  %(prog)s --site itviec --headless              # Run in headless mode
  %(prog)s --site itviec --show-summary          # Display results summary

Supported sites: {', '.join(supported_sites)}
        """
    )
    
    parser.add_argument(
        '--site', '-s',
        type=str,
        choices=supported_sites,
        help='Job site to crawl'
    )
    
    parser.add_argument(
        '--config', '-c',
        type=str,
        help='Path to custom configuration file'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Output CSV filename'
    )
    
    parser.add_argument(
        '--list-sites', '-l',
        action='store_true',
        help='List all supported job sites'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode'
    )
    
    parser.add_argument(
        '--show-summary',
        action='store_true',
        help='Display results summary after crawling'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser
