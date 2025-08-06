#!/usr/bin/env python
"""
Import Legacy LinkedIn Jobs CSV to Database

This script takes a LinkedIn jobs CSV file, analyzes each job asynchronously,
and imports the analyzed data into the database with proper deduplication.
"""

import os
import sys
import argparse
import asyncio
import pandas as pd
from datetime import datetime
from typing import Dict
from utils.job_database_inserter import JobDatabaseInserter
from utils.logger import CrawlerLogger
from utils.async_job_analyzer import AsyncJobAnalyzer
from utils.csv_exporter import JobCSVExporter
from utils.csv_utils import CSVUtils
from utils.api_key_manager import get_api_key_manager, APIKeyManager


def load_backup():
    """Load backup data, append only unique jobs to today's backup CSV, and save for safety."""
    import pandas as pd
    from glob import glob
    from datetime import datetime

    backup_dir = os.path.join(os.path.dirname(__file__), 'backup')
    os.makedirs(backup_dir, exist_ok=True)

    # Find all backup CSVs
    backup_csvs = sorted(glob(os.path.join(backup_dir, '*.csv')))
    if not backup_csvs:
        print("No backup CSV files found.")
        return

    # Load all backup data into one DataFrame
    dfs = [pd.read_csv(f, encoding='utf-8-sig') for f in backup_csvs]
    all_jobs_df = pd.concat(dfs, ignore_index=True)

    # Today's backup file
    today_str = datetime.now().strftime('%Y-%m-%d')
    today_backup_path = os.path.join(backup_dir, f'backup_{today_str}.csv')

    # If today's backup exists, load it; else, create with all columns
    if os.path.exists(today_backup_path):
        today_df = pd.read_csv(today_backup_path, encoding='utf-8-sig')
    else:
        # Use columns from the first backup file
        today_df = pd.DataFrame(columns=all_jobs_df.columns)
        today_df.to_csv(today_backup_path, index=False, encoding='utf-8-sig')

    # Find unique jobs not already in today's backup
    existing_jobids = set(today_df['JobID']) if not today_df.empty else set()
    new_jobs_df = all_jobs_df[~all_jobs_df['JobID'].isin(existing_jobids)]

    # Append only unique jobs
    if not new_jobs_df.empty:
        updated_df = pd.concat([today_df, new_jobs_df], ignore_index=True)
        updated_df.to_csv(today_backup_path, index=False, encoding='utf-8-sig')
        print(f"Appended {len(new_jobs_df)} new unique jobs to {today_backup_path}")
    else:
        print("No new unique jobs to append.")

async def import_legacy_jobs(csv_file_path: str, logger, batch_size: int = 5, start_idx: int = 0) -> Dict[str, int]:
    """
    Import legacy LinkedIn jobs with async analysis and database insertion.
    
    Args:
        csv_file_path (str): Path to the CSV file
        logger: Logger instance
        batch_size (int): Number of jobs to analyze concurrently
        
    Returns:
        Dict[str, int]: Import statistics
    """
    stats = {
        "total_jobs": 0,
        "analyzed": 0,
        "inserted": 0,
        "duplicates": 0,
        "errors": 0
    }
    
    try:
        # Read the CSV file
        logger.info(f"Reading CSV file: {csv_file_path}")
        df = pd.read_csv(csv_file_path, encoding='utf-8-sig')
        
        if df.empty:
            logger.warning("CSV file is empty")
            return stats
        
        stats["total_jobs"] = len(df)
        logger.info(f"Found {stats['total_jobs']} jobs in CSV file")
        
        # Convert DataFrame to list of dictionaries
        jobs_data = df.to_dict('records')
        
        # Initialize components
        analyzer = AsyncJobAnalyzer(logger)
        db_inserter = JobDatabaseInserter(logger)
        csv_exporter = JobCSVExporter()
        
        # Create CSV file for saving analyzed data (excluding vectors)
        csv_filename = csv_exporter.generate_filename("analyzed_linkedin_jobs")
        csv_filepath = csv_exporter.create_csv_file(csv_filename)
        logger.info(f"Created CSV file for analyzed data: {csv_filepath}")
        
        # Analyze jobs in batches
        logger.info(f"Batch Size Setting: {batch_size}")
        total_jobs = len(jobs_data)
        total_batches = (total_jobs + batch_size - 1) // batch_size

        logger.info(f"Total batches to process: {total_batches}")
        if start_idx != 0:
            logger.info(f"Starting from index: {start_idx}")

        for i in range(0 + start_idx, total_jobs, batch_size):
            batch = jobs_data[i:i + batch_size]
            logger.info(f"Analyzing batch {i // batch_size + 1}/{total_batches} with {len(batch)} jobs")
            
            # Analyze jobs asynchronously
            analyzed_jobs = await analyzer.analyze_jobs_sequentially(batch)
            stats["analyzed"] += len(analyzed_jobs)
            
            # Insert analyzed jobs into the database
            for job in analyzed_jobs:
                if db_inserter.insert_job(job):
                    stats["inserted"] += 1
                else:
                    stats["errors"] += 1
            
            # Save analyzed jobs to CSV
            csv_exporter.append_jobs_batch(analyzed_jobs, csv_filepath)
        
        logger.info(f"Import completed: {stats['inserted']} jobs inserted, {stats['duplicates']} duplicates skipped, {stats['errors']} errors")
        return stats
        
    except Exception as e:
        logger.error(f"Error during legacy import: {e}")
        stats["errors"] += 1
        return stats


def main():
    """Main function to import LinkedIn jobs from CSV to database with async analysis."""
    parser = argparse.ArgumentParser(description='Import legacy LinkedIn jobs CSV to database with AI analysis')
    parser.add_argument('csv_file', help='Path to LinkedIn jobs CSV file')
    parser.add_argument('--batch-size', type=int, default=10, help='Number of jobs to analyze concurrently (default: 5)')
    parser.add_argument('--load-backup', action='store_true', help='Load and consolidate backup files first')
    parser.add_argument('--start-idx', type=int, default=0, help='Start index for batch processing (default: 0)')
    args = parser.parse_args()
    
    # Load backup if requested
    if args.load_backup:
        print("Loading backup data...")
        load_backup()
    
    # Set up logger
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = f'import_linkedin_{timestamp}.log'
    
    # Initialize the logger
    crawler_logger = CrawlerLogger(log_dir)
    logger = crawler_logger.get_logger('linkedin_legacy_importer', log_file)
    logger.info(f"Starting LinkedIn legacy CSV import: {args.csv_file}")
    logger.info(f"Batch size for analysis: {args.batch_size}")
    
    # Validate the CSV file exists
    if not os.path.exists(args.csv_file):
        logger.error(f"CSV file not found: {args.csv_file}")
        return 1
    
    try:
        # Run the async import process
        stats = asyncio.run(import_legacy_jobs(args.csv_file, logger, args.batch_size, args.start_idx))
        
        # Print final statistics
        logger.info("=" * 60)
        logger.info("IMPORT SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total jobs in CSV: {stats['total_jobs']}")
        logger.info(f"Successfully analyzed: {stats['analyzed']}")
        logger.info(f"Successfully inserted: {stats['inserted']}")
        logger.info(f"Duplicates skipped: {stats['duplicates']}")
        logger.info(f"Errors encountered: {stats['errors']}")
        logger.info("=" * 60)
        
        if stats['errors'] > 0:
            logger.warning(f"Import completed with {stats['errors']} errors")
            return 1
        else:
            logger.info("Import completed successfully!")
            return 0
    
    except KeyboardInterrupt:
        logger.info("Import interrupted by user")
        return 1
    except Exception as e:
        logger.error(f"Unexpected error during import: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
