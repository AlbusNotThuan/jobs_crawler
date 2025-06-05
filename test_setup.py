#!/usr/bin/env python3
"""
Test script for the job crawler main.py
"""

import sys
import os

# Add the current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all modules can be imported successfully."""
    try:
        from utils.load_config import load_config, validate_required_keys
        print("✓ utils.load_config imported successfully")
        
        from utils.arg_parser import create_parser
        print("✓ utils.arg_parser imported successfully")
        
        from utils.colors import Colors
        print("✓ utils.colors imported successfully")
        
        from itviecCrawler import crawl_itviec
        print("✓ itviecCrawler imported successfully")
        
        import main
        print("✓ main module imported successfully")
        
        return True
    except Exception as e:
        print(f"✗ Import error: {e}")
        return False

def test_config_loading():
    """Test configuration loading."""
    try:
        from utils.load_config import load_config
        config = load_config('configs/itviec_config.yaml')
        print("✓ Configuration loaded successfully")
        print(f"  - Base URL: {config.get('BASE_URL', 'Not found')}")
        print(f"  - Headless: {config.get('HEADLESS', 'Not found')}")
        return True
    except Exception as e:
        print(f"✗ Config loading error: {e}")
        return False

def test_crawler_manager():
    """Test the JobCrawlerManager."""
    try:
        from main import JobCrawlerManager
        manager = JobCrawlerManager()
        print("✓ JobCrawlerManager created successfully")
        print(f"  - Supported sites: {list(manager.supported_sites.keys())}")
        return True
    except Exception as e:
        print(f"✗ JobCrawlerManager error: {e}")
        return False

if __name__ == '__main__':
    print("Job Crawler Test Script")
    print("=" * 40)
    
    all_tests_passed = True
    
    print("\n1. Testing imports...")
    all_tests_passed &= test_imports()
    
    print("\n2. Testing configuration loading...")
    all_tests_passed &= test_config_loading()
    
    print("\n3. Testing JobCrawlerManager...")
    all_tests_passed &= test_crawler_manager()
    
    print("\n" + "=" * 40)
    if all_tests_passed:
        print("✓ All tests passed! The crawler is ready to use.")
        print("\nUsage examples:")
        print("  python main.py --list-sites")
        print("  python main.py --site itviec --show-summary")
        print("  python main.py --site itviec --headless --output my_jobs.csv")
    else:
        print("✗ Some tests failed. Please check the errors above.")
        sys.exit(1)
