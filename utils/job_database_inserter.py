import os
import psycopg
from datetime import datetime, timezone
from typing import List, Dict, Optional, Set
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class JobDatabaseInserter:
    """
    Utility class to insert analyzed job data into the database.
    Handles deduplication and company management.
    """
    
    def __init__(self, logger=None):
        self.conn = None
        self.cur = None
        self.existing_job_ids: Set[str] = set()
        self.companies_cache: Dict[str, str] = {}  # company_name -> company_id
        self.existing_web_ids: Set[str] = set()  # For LinkedIn jobs
        self.logger = logger  # Logger instance (if provided)
        self.connect_to_database()
        self.load_existing_job_ids()
        self.load_companies_cache()
        self.load_existing_web_ids()

    def connect_to_database(self):
        """Connect to the PostgreSQL database."""
        try:
            conn_string = os.getenv('DB_CONNECTION')
            if not conn_string:
                raise ValueError("DB_CONNECTION environment variable not found")
            
            self.conn = psycopg.connect(conn_string)
            self.cur = self.conn.cursor()
            self._log("✓ JobDatabaseInserter connected to database successfully!")
            
        except Exception as e:
            self._log(f"✗ Error connecting to database: {e}", level="error")
            raise
    
    def _log(self, message, level="info"):
        """Helper method for logging messages with logger or print."""
        if self.logger:
            if level == "error":
                self.logger.error(message)
            elif level == "warning":
                self.logger.warning(message)
            else:
                self.logger.info(message)
        else:
            print(message)
            
    def load_existing_job_ids(self):
        """Load all existing job IDs from the database to check for duplicates."""
        try:
            self.cur.execute("SELECT job_id FROM job")
            rows = self.cur.fetchall()
            self.existing_job_ids = {str(row[0]) for row in rows}
            self._log(f"Loaded {len(self.existing_job_ids)} existing job IDs for duplicate checking")
        except Exception as e:
            self._log(f"Error loading existing job IDs: {e}", level="error")
            self.existing_job_ids = set()

    def load_existing_web_ids(self):
        """Load all existing web IDs from the database to check for LinkedIn job duplicates."""
        try:
            self.cur.execute("SELECT web_id FROM job")
            rows = self.cur.fetchall()
            self.existing_web_ids = {str(row[0]) for row in rows}
            self._log(f"Loaded {len(self.existing_web_ids)} existing web IDs")
        except Exception as e:
            self._log(f"Error loading existing web IDs: {e}", level="error")
            self.existing_web_ids = set()
    
    def load_companies_cache(self):
        """Load existing companies from the database."""
        try:
            self.cur.execute("SELECT company_name, company_id FROM company")
            rows = self.cur.fetchall()
            self.companies_cache = {row[0]: row[1] for row in rows}
            self._log(f"Loaded {len(self.companies_cache)} companies into cache")
        except Exception as e:
            self._log(f"Error loading companies cache: {e}", level="error")
            self.companies_cache = {}

    def is_duplicate_job(self, job_id: str, web_id: str) -> bool:
        """Check if a job ID already exists in the database."""
        return (str(job_id) in self.existing_job_ids or
                str(web_id) in self.existing_web_ids)

    def _generate_company_id(self, company_name: str) -> str:
        """Generate a unique company ID based on company name."""
        import hashlib
        import time
        
        # Create a hash from company name + current timestamp for uniqueness
        hash_input = f"{company_name.lower().strip()}_{int(time.time())}"
        company_id = hashlib.md5(hash_input.encode()).hexdigest()[:12]
        return f"comp_{company_id}"
    
    def get_or_create_company(self, company_name: str, company_description: str = None) -> str:
        """
        Get company_id for a company name, creating it if it doesn't exist.
        
        Args:
            company_name (str): Name of the company
            company_description (str): Description of the company (optional)
            
        Returns:
            str: company_id
        """
        if not company_name or company_name.strip() == "":
            company_name = "Unknown Company"
            
        company_name = company_name.strip()
        
        # Check cache first
        if company_name in self.companies_cache:
            return self.companies_cache[company_name]
        
        try:
            # Check if company already exists
            self.cur.execute("SELECT company_id FROM company WHERE company_name = %s", (company_name,))
            existing = self.cur.fetchone()
            
            if existing:
                company_id = existing[0]
            else:
                # Generate new company ID and insert
                company_id = self._generate_company_id(company_name)
                insert_query = """
                    INSERT INTO company (company_id, company_name, company_description)
                    VALUES (%s, %s, %s)
                """
                self.cur.execute(insert_query, (company_id, company_name, company_description))
            
            # Update cache
            self.companies_cache[company_name] = company_id
            
            return company_id
        except Exception as e:
            self._log(f"Error creating/getting company {company_name}: {e}", level="error")
            # Return a default company_id
            return "comp_default"
    
    def insert_job(self, job_data: Dict) -> Optional[str]:
        """
        Insert a single job into the database.
        
        Args:
            job_data (Dict): Job data dictionary with all the fields
            
        Returns:
            Optional[str]: The inserted job_id if successful, None otherwise
        """
        try:
            import random, time
            job_id_hash = str(job_data.get("job_id", ""))
            web_id = str(job_data.get("web_id", ""))
            if self.is_duplicate_job(job_id_hash, web_id):
                self._log(f"  [Job ID hash check] Skipping duplicate job: {job_id_hash[:8]}...")
                return "duplication"

            # Get or create company
            company_name = job_data.get("company_name", "Unknown Company")
            company_description = job_data.get("company_description", None)
            company_id = self.get_or_create_company(company_name, company_description)
            
            # Insert job record
            insert_query = """
                INSERT INTO job (
                    job_id, job_title, job_expertise, yoe, salary, location, 
                    posted_date, requirements, requirements_embedding, 
                    description, description_embedding, web_id, company_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            
            # Convert embeddings to proper format if they exist
            requirements_embedding = job_data.get("job_requirements_embedding")
            description_embedding = job_data.get("job_description_embedding")
            
            # Handle None or empty embeddings - convert to None for pgvector
            if not requirements_embedding or requirements_embedding == "[]":
                requirements_embedding = None
            if not description_embedding or description_embedding == "[]":
                description_embedding = None
            
            values = (
                job_id_hash,  # Use hash as job_id
                job_data.get("job_title", None),
                job_data.get("job_expertise", None),
                job_data.get("yoe", None),
                job_data.get("salary", None),
                job_data.get("location", None),
                job_data.get("posted_date", datetime.now(timezone.utc)),
                job_data.get("job_requirements", None),
                requirements_embedding,  # pgvector will handle the list
                job_data.get("job_description", None),
                description_embedding,  # pgvector will handle the list
                job_data.get("web_id", None),
                company_id,
            )
            
            self.cur.execute(insert_query, values)
            self.conn.commit()  # Ensure changes are saved
            self.existing_job_ids.add(job_id_hash)
            self._log(f"  ✓ Inserted job: {job_id_hash[:8]} - {job_data.get('job_title', 'Unknown')[:50]}")
            
            # Add random sleep between 0.2 and 1.2 seconds
            time.sleep(random.uniform(0.2, 1.2))
            return job_id_hash
        except Exception as e:
            self._log(f"  ✗ Error inserting job: {e}", level="error")
            self.conn.rollback()
            return None
    
    def insert_job_batch(self, job_data_list: List[Dict]) -> Dict[str, int]:
        """
        Insert a batch of analyzed jobs into the database.
        
        Args:
            job_data_list (List[Dict]): List of job data dictionaries
            
        Returns:
            Dict[str, int]: Statistics about the insertion
        """
        stats = {
            "total": len(job_data_list),
            "inserted": 0,
            "duplicates": 0,
            "errors": 0
        }
        
        self._log(f"\n📊 Inserting {stats['total']} jobs into database...")
        
        for i, job_data in enumerate(job_data_list, 1):
            try:
                job_id = job_data.get("job_id", f"unknown_{i}")
                web_id = job_data.get("web_id", "")
                self._log(f"  Processing {i}/{stats['total']}: {job_id[:8]}...")
                
                # Check for duplicate
                if self.is_duplicate_job(str(job_id), str(web_id)):
                    stats["duplicates"] += 1
                    self._log(f"    ⚠ Duplicate job skipped")
                    continue
                
                # Insert job
                success = self.insert_job(job_data)
                
                if success:
                    stats["inserted"] += 1
                else:
                    stats["errors"] += 1
                    
            except Exception as e:
                self._log(f"    ✗ Error processing job {i}: {e}", level="error")
                stats["errors"] += 1
                continue
        
        # Print summary
        self._log(f"\n📈 Batch insertion summary:")
        self._log(f"  Total jobs processed: {stats['total']}")
        self._log(f"  Successfully inserted: {stats['inserted']}")
        self._log(f"  Duplicates skipped: {stats['duplicates']}")
        self._log(f"  Errors encountered: {stats['errors']}")
        
        return stats
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get current database statistics."""
        try:
            stats = {}
            
            # Count jobs
            self.cur.execute("SELECT COUNT(*) FROM job")
            stats["total_jobs"] = self.cur.fetchone()[0]
            
            # Count companies
            self.cur.execute("SELECT COUNT(*) FROM company")
            stats["total_companies"] = self.cur.fetchone()[0]
            
            return stats
        except Exception as e:
            self._log(f"Error getting database stats: {e}", level="error")
            return {}
            
        except Exception as e:
            print(f"Error getting database stats: {e}")
            return {}
            
    def close_connection(self):
        """Close database connection."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        self._log("✓ JobDatabaseInserter connection closed")

# Example usage:
if __name__ == "__main__":
    inserter = JobDatabaseInserter()
    job_data = {
        "JobID": "12345",
        "Title": "Software Engineer",
        "Company": "Tech Corp",
        "Location": "Remote",
        "Posted_Date": datetime.now(timezone.utc),
        "work_type": "Full-time",
        "yoe": "3 years",
        "Salary": "$100,000 - $120,000",
        "job_requirements": "Python, Django, REST APIs",
        "job_description": "Develop and maintain web applications.",
        "job_requirements_embedding": None,
        "job_description_embedding": None
    }
    inserter.insert_job(job_data)
    inserter.close_connection()