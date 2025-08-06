"""
CSV Exporter Utility for Job Data

This utility handles saving job data to CSV files with proper formatting,
excluding vector columns, and supporting both row-wise and batch operations.
"""

import os
import csv
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path


class JobCSVExporter:
    """
    Utility class for exporting job data to CSV files.
    Supports both row-wise appending and batch operations.
    """
    
    def __init__(self, output_dir: str = None):
        """
        Initialize the CSV exporter.
        
        Args:
            output_dir (str): Directory to save CSV files. Defaults to 'output' in project root.
        """
        if output_dir is None:
            # Default to 'output' directory in project root
            project_root = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.output_dir = project_root / "output"
        else:
            self.output_dir = Path(output_dir)
        
        # Ensure output directory exists
        self.output_dir.mkdir(exist_ok=True)
        
        # Define columns to exclude from CSV export (vector columns)
        self.exclude_columns = {
            'job_description_embedding',
            'job_requirements_embedding',
            'requirements_embedding',
            'description_embedding'
        }
        
        # Standard column order for LinkedIn jobs
        self.standard_columns = [
            'job_id', 'job_title', 'company_name', 'salary', 'location', 
            'posted_date', 'job_expertise', 'yoe', 'work_type',
            'job_requirements', 'job_description', 'company_id', 'company_description'
        ]
    
    def _filter_job_data(self, job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Filter out vector columns and standardize field names.
        
        Args:
            job_data (Dict): Raw job data dictionary
            
        Returns:
            Dict: Filtered job data suitable for CSV export
        """
        filtered_data = {}
        
        # Map and filter the data
        field_mapping = {
            'job_id': job_data.get('job_id', ''),
            'job_title': job_data.get('job_title', job_data.get('Title', '')),
            'company_name': job_data.get('company_name', job_data.get('Company', '')),
            'salary': job_data.get('salary', job_data.get('Salary', '')),
            'location': job_data.get('location', job_data.get('Location', '')),
            'posted_date': job_data.get('posted_date', job_data.get('Posted_Date', '')),
            'job_expertise': job_data.get('job_expertise', job_data.get('Job_Expertise', '')),
            'yoe': job_data.get('yoe', job_data.get('Experience', '')),
            'work_type': job_data.get('work_type', ''),
            'job_requirements': job_data.get('job_requirements', job_data.get('requirements', '')),
            'job_description': job_data.get('job_description', job_data.get('Description', '')),
            'company_id': job_data.get('company_id', ''),
            'company_description': job_data.get('company_description', job_data.get('company_infomation', ''))
        }
        
        # Only include non-vector columns
        for key, value in field_mapping.items():
            if key not in self.exclude_columns:
                filtered_data[key] = value
        
        return filtered_data
    
    def generate_filename(self, prefix: str = "linkedin_jobs") -> str:
        """
        Generate a timestamped filename for CSV export.
        
        Args:
            prefix (str): Prefix for the filename
            
        Returns:
            str: Generated filename
        """
        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        return f"{timestamp}_{prefix}.csv"
    
    def create_csv_file(self, filename: str) -> str:
        """
        Create a new CSV file with headers.
        
        Args:
            filename (str): Name of the CSV file
            
        Returns:
            str: Full path to the created CSV file
        """
        filepath = self.output_dir / filename
        
        # Write header row
        with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=self.standard_columns)
            writer.writeheader()
        
        return str(filepath)
    
    def append_single_job(self, filepath: str, job_data: Dict[str, Any]) -> bool:
        """
        Append a single job to an existing CSV file.
        
        Args:
            filepath (str): Path to the CSV file
            job_data (Dict): Job data to append
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            filtered_data = self._filter_job_data(job_data)
            
            # Ensure file exists
            if not os.path.exists(filepath):
                # Create file with headers if it doesn't exist
                with open(filepath, 'w', newline='', encoding='utf-8') as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=self.standard_columns)
                    writer.writeheader()
            
            # Append the job data
            with open(filepath, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=self.standard_columns)
                writer.writerow(filtered_data)
            
            return True
            
        except Exception as e:
            print(f"Error appending job to CSV: {e}")
            return False
    
    def append_jobs_batch(self, jobs_data: List[Dict[str, Any]], filepath: str = None) -> str:
        """
        Save a batch of jobs to a CSV file.
        
        Args:
            jobs_data (List[Dict]): List of job data dictionaries
            filepath (str): Path to the current CSV file.
            
        Returns:
            
        """
        
        # Filter all job data
        filtered_jobs = [self._filter_job_data(job) for job in jobs_data]
        
        # Loop to add jobs to CSV
        for job in filtered_jobs:
            self.append_single_job(filepath, job)
    
        return str(filepath)
    
    def get_csv_path(self, filename: str) -> str:
        """
        Get the full path for a CSV file in the output directory.
        
        Args:
            filename (str): Name of the CSV file
            
        Returns:
            str: Full path to the CSV file
        """
        return str(self.output_dir / filename)

# Example usage
if __name__ == "__main__":
    # Test the CSV exporter
    exporter = JobCSVExporter()
    
    # Sample job data
    sample_job = {
        'job_id': 'test_123',
        'job_title': 'Software Engineer',
        'company_name': 'Tech Corp',
        'salary': '$80,000 - $120,000',
        'location': 'San Francisco, CA',
        'posted_date': '2025-08-05',
        'job_expertise': 'Software Development',
        'yoe': '3-5 years',
        'work_type': 'Full-time',
        'job_requirements': 'Python, Django, React',
        'job_description': 'We are looking for a talented software engineer...',
        'company_id': 'comp_tech123',
        'company_description': 'Leading technology company',
        'job_description_embedding': [0.1, 0.2, 0.3],  # This will be excluded
        'job_requirements_embedding': [0.4, 0.5, 0.6]   # This will be excluded
    }
    
    # Create a new CSV file
    filename = exporter.generate_filename()
    filepath = exporter.create_csv_file(filename)
    print(f"Created CSV file: {filepath}")
    
    # Append a job
    success = exporter.append_jobs_batch([sample_job], filepath)
    print(f"Job appended successfully: {success}")
