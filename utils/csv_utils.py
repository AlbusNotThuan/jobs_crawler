#!/usr/bin/env python
"""
CSV Utilities for Job Crawler

This module provides utilities for handling CSV operations, particularly for
saving analyzed job data to CSV files with proper formatting and error handling.
"""

import os
import csv
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
import hashlib

class CSVUtils:
    """
    Utility class for handling CSV operations for job data.
    """
    
    @staticmethod
    def generate_job_id(title: str, company: str) -> str:
        """
        Generate a unique job ID based on title and company.
        
        Args:
            title (str): Job title
            company (str): Company name
            
        Returns:
            str: Generated job ID
        """
        if not title:
            title = "unknown_title"
        if not company:
            company = "unknown_company"
            
        # Normalize strings
        title = title.lower().strip()
        company = company.lower().strip()
        
        # Create hash
        hash_input = f"{title}_{company}"
        job_id = hashlib.md5(hash_input.encode()).hexdigest()[:16]
        return f"job_{job_id}"
