"""
Async Job Analyzer for Legacy Import

Handles asynchronous job analysis for legacy data import,
integrating with the existing analyze_job module.
"""

import asyncio
import hashlib
from typing import Dict, Any, Set, Optional
from utils.analyze_job import analyze_job_content


class AsyncJobAnalyzer:
    def __init__(self, logger=None):
        """
        Initialize the async job analyzer.
        
        Args:
            logger: Optional logger instance
        """
        self.logger = logger
        self.processed_hashes: Set[str] = set()
        self.last_call_time = 0
        self.min_delay = 4.2  # 4.2 seconds between calls to stay under 15 RPM (60/15 = 4 seconds + buffer)
    
    def _log(self, message: str, level: str = "info"):
        """Helper method for logging."""
        if self.logger:
            if level == "error":
                self.logger.error(message)
            elif level == "warning":
                self.logger.warning(message)
            else:
                self.logger.info(message)
        else:
            print(message)
    
    def generate_internal_hash(self, job_title: str, company: str) -> str:
        """
        Generate an internal hash for deduplication tracking.
        This hash is only used internally and not saved to the database.
        
        Args:
            job_title (str): Job title
            company (str): Company name
            
        Returns:
            str: Internal hash for deduplication
        """
        # Normalize the inputs
        title_clean = (job_title or "").strip().lower()
        company_clean = (company or "").strip().lower()
        
        # Create hash input
        hash_input = f"{title_clean}|{company_clean}"
        
        # Generate MD5 hash
        internal_hash = hashlib.md5(hash_input.encode('utf-8')).hexdigest()[:16]
        return f"internal_{internal_hash}"
    
    def is_duplicate(self, job_title: str, company: str) -> bool:
        """
        Check if a job is a duplicate based on internal hash.
        
        Args:
            job_title (str): Job title
            company (str): Company name
            
        Returns:
            bool: True if duplicate, False otherwise
        """
        internal_hash = self.generate_internal_hash(job_title, company)
        return internal_hash in self.processed_hashes
    
    def mark_as_processed(self, job_title: str, company: str):
        """
        Mark a job as processed to prevent duplicates.
        
        Args:
            job_title (str): Job title
            company (str): Company name
        """
        internal_hash = self.generate_internal_hash(job_title, company)
        self.processed_hashes.add(internal_hash)
    
    async def _enforce_rate_limit(self):
        """Ensure we don't exceed the 15 RPM rate limit."""
        import time
        current_time = time.time()
        time_since_last_call = current_time - self.last_call_time
        
        if time_since_last_call < self.min_delay:
            delay = self.min_delay - time_since_last_call
            self._log(f"  Rate limiting: waiting {delay:.1f} seconds...")
            await asyncio.sleep(delay)
        
        self.last_call_time = time.time()

    async def analyze_single_job(self, job_data: Dict[str, Any], job_index: int) -> Optional[Dict[str, Any]]:
        """
        Analyze a single job asynchronously.
        
        Args:
            job_data (Dict): Raw job data from CSV
            job_index (int): Index of the job for logging
            
        Returns:
            Optional[Dict]: Analyzed job data or None if duplicate/error
        """
        # Enforce rate limiting (sequential processing)
        await self._enforce_rate_limit()
        
        try:
                # Extract basic info
                job_title = job_data.get('job_title', '')
                company = job_data.get('company_name', '')
                
                # Check for duplicates
                if self.is_duplicate(job_title, company):
                    self._log(f"  Job {job_index}: Skipping duplicate - {job_title[:50]}...")
                    return None
                
                # Mark as processed
                self.mark_as_processed(job_title, company)
                
                self._log(f"  Job {job_index}: Analyzing - {job_title[:50]}...")
                
                # Prepare content for analysis
                description = job_data.get('raw_job_description', '')
                if not description.strip():
                    self._log(f"  Job {job_index}: Warning - No description available", level="warning")
                    description = f"Job title: {job_title}"
                
                # Call the existing analyze_job_content function
                analysis_result = await analyze_job_content(description, job_title)
                
                # Merge original data with analysis results
                enhanced_job_data = {
                    # Original CSV data
                    'JobID': job_data.get('JobID', ''),
                    'Title': job_title,
                    'Company': company,
                    'Salary': job_data.get('Salary', ''),
                    'Location': job_data.get('Location', ''),
                    'Posted_Date': job_data.get('Posted_Date', ''),
                    'Link': job_data.get('Link', ''),
                    'Benefits': job_data.get('Benefits', ''),
                    'Experience': job_data.get('Experience', ''),
                    'Skills': job_data.get('Skills', ''),  # Legacy field, will be ignored in inserter
                    
                    # Analysis results
                    'job_title': job_title,
                    'company_name': company,
                    'job_expertise': analysis_result.get('job_expertise', ''),
                    'yoe': analysis_result.get('yoe', ''),
                    'salary': analysis_result.get('salary', job_data.get('Salary', '')),
                    'job_requirements': analysis_result.get('job_requirements', ''),
                    'job_description': analysis_result.get('job_description', description),
                    'company_infomation': analysis_result.get('company_infomation', ''),
                    'work_type': 'Full-time',  # Default value
                    
                    # Embeddings (will be handled by inserter)
                    'job_description_embedding': analysis_result.get('job_description_embedding'),
                    'job_requirements_embedding': analysis_result.get('job_requirements_embedding'),
                    
                    # Metadata
                    'location': job_data.get('Location', ''),
                    'posted_date': job_data.get('Posted_Date', ''),
                    'job_id': job_data.get('JobID', ''),  # Use original JobID as hash
                }
                
                self._log(f"  Job {job_index}: ✓ Analysis completed - {job_title[:30]}...")
                return enhanced_job_data
                
        except Exception as e:
            self._log(f"  Job {job_index}: ✗ Analysis failed - {str(e)}", level="error")
            return None
    
    async def analyze_jobs_sequentially(self, jobs_data: list) -> list:
        """
        Analyze jobs sequentially one by one with rate limiting.
        Use this method for API with strict rate limits (15 RPM).
        
        Args:
            jobs_data (list): List of job data dictionaries
            
        Returns:
            list: List of analyzed job data dictionaries
        """
        analyzed_jobs = []
        total_jobs = len(jobs_data)
        
        self._log(f"Starting sequential analysis of {total_jobs} jobs...")
        
        # Process jobs one by one
        for i, job_data in enumerate(jobs_data):
            job_index = i + 1
            self._log(f"Processing job {job_index} of {total_jobs}...")
            
            # Analyze the single job (rate limiting handled internally)
            result = await self.analyze_single_job(job_data, job_index)
            
            # Add to results if successful
            if result is not None:
                analyzed_jobs.append(result)
            
        self._log(f"Analysis completed. Processed {len(analyzed_jobs)} out of {total_jobs} jobs.")
        return analyzed_jobs
        
    def get_stats(self) -> Dict[str, int]:
        """
        Get processing statistics.
        
        Returns:
            Dict: Processing statistics
        """
        return {
            "total_processed": len(self.processed_hashes),
            "duplicates_skipped": len(self.processed_hashes)  # This will be tracked separately in actual implementation
        }


# Convenience function for single job analysis
async def analyze_job_async(job_data: Dict[str, Any], logger=None) -> Optional[Dict[str, Any]]:
    """
    Convenience function to analyze a single job.
    
    Args:
        job_data (Dict): Job data dictionary
        logger: Optional logger
        
    Returns:
        Optional[Dict]: Analyzed job data or None
    """
    analyzer = AsyncJobAnalyzer(logger)
    return await analyzer.analyze_single_job(job_data, 1)


# Example usage
if __name__ == "__main__":
    import asyncio
    
    async def test_analyzer():
        # Sample job data
        sample_jobs = [
            {
                'JobID': '12345',
                'Title': 'Software Engineer',
                'Company': 'Tech Corp',
                'Description': 'We are looking for a software engineer with Python experience...',
                'Salary': '$80k-120k',
                'Location': 'San Francisco',
                'Posted_Date': '2025-08-05'
            },
            {
                'JobID': '12346',
                'Title': 'Data Scientist',
                'Company': 'Data Inc',
                'Description': 'Seeking a data scientist with machine learning expertise...',
                'Salary': '$90k-130k',
                'Location': 'New York',
                'Posted_Date': '2025-08-05'
            }
        ]
        
        # Test the analyzer
        analyzer = AsyncJobAnalyzer()
        results = await analyzer.analyze_jobs_sequentially(sample_jobs)
        
        print(f"Analyzed {len(results)} jobs:")
        for result in results:
            print(f"- {result['job_title']} at {result['company_name']}")
            print(f"- {result['job_expertise']}, {result['yoe']}, {result['salary']}")
    
    # Run the test
    asyncio.run(test_analyzer())
