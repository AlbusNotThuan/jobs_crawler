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
    Handles deduplication and skill tokenization/matching.
    """
    
    def __init__(self):
        self.conn = None
        self.cur = None
        self.existing_job_ids: Set[str] = set()
        self.skills_cache: Dict[str, int] = {}  # skill_name -> skill_id
        self.connect_to_database()
        self.load_existing_job_ids()
        self.load_skills_cache()
    
    def connect_to_database(self):
        """Connect to the PostgreSQL database."""
        try:
            conn_string = os.getenv('DB_CONNECTION')
            if not conn_string:
                raise ValueError("DB_CONNECTION environment variable not found")
            
            self.conn = psycopg.connect(conn_string)
            self.cur = self.conn.cursor()
            print("✓ JobDatabaseInserter connected to database successfully!")
            
        except Exception as e:
            print(f"✗ Error connecting to database: {e}")
            raise
    
    def load_existing_job_ids(self):
        """Load all existing job IDs from the database to check for duplicates."""
        try:
            # Get all job IDs that are currently in the database
            self.cur.execute("SELECT job_id FROM job")
            results = self.cur.fetchall()
            
            # Convert to set of strings for faster lookup
            self.existing_job_ids = {str(row[0]) for row in results}
            print(f"✓ Loaded {len(self.existing_job_ids)} existing job IDs from database")
            
        except Exception as e:
            print(f"✗ Error loading existing job IDs: {e}")
            self.existing_job_ids = set()
    
    def load_skills_cache(self):
        """Load all skills from database into cache for fast lookup."""
        try:
            self.cur.execute("SELECT skill_id, name FROM skill")
            results = self.cur.fetchall()
            
            # Create cache: skill_name (lowercase) -> skill_id
            self.skills_cache = {name.lower(): skill_id for skill_id, name in results}
            print(f"✓ Loaded {len(self.skills_cache)} skills into cache")
            
        except Exception as e:
            print(f"✗ Error loading skills cache: {e}")
            self.skills_cache = {}
    
    def is_duplicate_job(self, job_id: str) -> bool:
        """Check if a job ID already exists in the database."""
        return str(job_id) in self.existing_job_ids
    
    def tokenize_skills(self, skills_text: str) -> List[str]:
        """
        Tokenize skills from comma-separated text and clean them.
        
        Args:
            skills_text (str): Comma-separated skills string
            
        Returns:
            List[str]: List of cleaned skill names
        """
        if not skills_text or skills_text.strip() in ["Not specified", "Not available", ""]:
            return []
        
        # Split by comma and clean up each skill
        skills = []
        for skill in skills_text.split(','):
            skill = skill.strip()
            if skill and len(skill) > 1:  # Skip empty or single character skills
                skills.append(skill)
        
        return skills
    
    def find_skill_id(self, skill_name: str) -> Optional[int]:
        """
        Find skill ID for a given skill name.
        Uses exact match first, then partial matching.
        
        Args:
            skill_name (str): Name of the skill to find
            
        Returns:
            Optional[int]: skill_id if found, None otherwise
        """
        skill_lower = skill_name.lower().strip()
        
        # Exact match first
        if skill_lower in self.skills_cache:
            return self.skills_cache[skill_lower]
        
        # Partial matching - find skills that contain the search term
        for cached_skill, skill_id in self.skills_cache.items():
            if (skill_lower in cached_skill) or (cached_skill in skill_lower):
                print(f"  Partial match: '{skill_name}' -> '{cached_skill}'")
                return skill_id
        
        print(f"  Skill not found: '{skill_name}'")
        return None
    
    def parse_years_of_experience(self, yoe_text: str) -> Optional[str]:
        """Return years of experience as-is (no parsing)."""
        return yoe_text
    
    def determine_job_expertise(self, title: str, yoe: Optional[str]) -> str:
        """Return job expertise as-is (no parsing)."""
        return title
    
    def insert_job(self, job_data: Dict) -> Optional[int]:
        """
        Insert a single job into the database.
        
        Args:
            job_data (Dict): Job data dictionary with all the fields
            
        Returns:
            Optional[int]: The inserted job_id if successful, None otherwise
        """
        try:
            import random, time
            job_id_hash = str(job_data.get("JobID", ""))
            if self.is_duplicate_job(job_id_hash):
                print(f"  Skipping duplicate job: {job_id_hash[:8]}...")
                return None
            # Insert job record as-is
            insert_query = """
                INSERT INTO job (job_title, job_expertise, description, requirements, salary, location, posted_date, yoe, work_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING job_id
            """
            values = (
                job_data.get("Title", ""),
                job_data.get("Job_Expertise", ""),
                job_data.get("Description", ""),
                job_data.get("Experience", ""),
                job_data.get("Salary", ""),
                job_data.get("Location", ""),
                job_data.get("Posted_Date", datetime.now(timezone.utc)),
                job_data.get("yoe", ""),
                job_data.get("work_type", "")
            )
            self.cur.execute(insert_query, values)
            db_job_id = self.cur.fetchone()[0]
            self.existing_job_ids.add(job_id_hash)
            print(f"  ✓ Inserted job: {db_job_id} - {job_data.get('Title', 'Unknown')[:50]}")
            # Add random sleep between 0.2 and 1.2 seconds
            time.sleep(random.uniform(0.2, 1.2))
            return db_job_id
        except Exception as e:
            print(f"  ✗ Error inserting job: {e}")
            self.conn.rollback()
            return None
    
    def insert_job_skills(self, db_job_id: int, skills_text: str) -> int:
        """
        Insert job-skill relationships for a job.
        
        Args:
            db_job_id (int): Database job ID
            skills_text (str): Comma-separated skills string
            
        Returns:
            int: Number of skills successfully linked
        """
        try:
            # Tokenize skills
            skills = self.tokenize_skills(skills_text)
            
            if not skills:
                return 0
            
            skills_linked = 0
            
            for skill_name in skills:
                skill_id = self.find_skill_id(skill_name)
                
                if skill_id:
                    try:
                        # Insert job-skill relationship
                        self.cur.execute(
                            "INSERT INTO job_skill (job_id, skill_id, relevance) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                            (db_job_id, skill_id, 1.0)  # Default relevance of 1.0
                        )
                        
                        if self.cur.rowcount > 0:
                            skills_linked += 1
                            
                    except Exception as e:
                        print(f"    ✗ Error linking skill '{skill_name}': {e}")
                        continue
            
            print(f"    ✓ Linked {skills_linked}/{len(skills)} skills")
            return skills_linked
            
        except Exception as e:
            print(f"  ✗ Error processing skills: {e}")
            return 0
    
    def insert_analyzed_job(self, job_data: Dict) -> bool:
        """
        Insert a complete analyzed job with skills into the database.
        
        Args:
            job_data (Dict): Complete job data dictionary
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Insert the job
            db_job_id = self.insert_job(job_data)
            
            if db_job_id is None:
                return False
            
            # Insert job skills
            skills_text = job_data.get("Skills", "")
            if skills_text and skills_text not in ["Not specified", "Not available"]:
                self.insert_job_skills(db_job_id, skills_text)
            
            # Commit the transaction
            self.conn.commit()
            return True
            
        except Exception as e:
            print(f"  ✗ Error inserting analyzed job: {e}")
            self.conn.rollback()
            return False
    
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
            "errors": 0,
            "skills_linked": 0
        }
        
        print(f"\n📊 Inserting {stats['total']} jobs into database...")
        
        for i, job_data in enumerate(job_data_list, 1):
            try:
                job_id = job_data.get("JobID", f"unknown_{i}")
                print(f"  Processing {i}/{stats['total']}: {job_id[:8]}...")
                
                # Check for duplicate
                if self.is_duplicate_job(str(job_id)):
                    stats["duplicates"] += 1
                    print(f"    ⚠ Duplicate job skipped")
                    continue
                
                # Insert job
                success = self.insert_analyzed_job(job_data)
                
                if success:
                    stats["inserted"] += 1
                else:
                    stats["errors"] += 1
                    
            except Exception as e:
                print(f"    ✗ Error processing job {i}: {e}")
                stats["errors"] += 1
                continue
        
        # Print summary
        print(f"\n📈 Batch insertion summary:")
        print(f"  Total jobs processed: {stats['total']}")
        print(f"  Successfully inserted: {stats['inserted']}")
        print(f"  Duplicates skipped: {stats['duplicates']}")
        print(f"  Errors encountered: {stats['errors']}")
        
        return stats
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get current database statistics."""
        try:
            stats = {}
            
            # Count jobs
            self.cur.execute("SELECT COUNT(*) FROM job")
            stats["total_jobs"] = self.cur.fetchone()[0]
            
            # Count skills
            self.cur.execute("SELECT COUNT(*) FROM skill")
            stats["total_skills"] = self.cur.fetchone()[0]
            
            # Count job-skill relationships
            self.cur.execute("SELECT COUNT(*) FROM job_skill")
            stats["total_relationships"] = self.cur.fetchone()[0]
            
            # Jobs by expertise
            self.cur.execute("SELECT job_expertise, COUNT(*) FROM job GROUP BY job_expertise")
            stats["by_expertise"] = dict(self.cur.fetchall())
            
            return stats
            
        except Exception as e:
            print(f"Error getting database stats: {e}")
            return {}
    
    def close_connection(self):
        """Close database connection."""
        if self.cur:
            self.cur.close()
        if self.conn:
            self.conn.close()
        print("✓ JobDatabaseInserter connection closed")


# Example usage
if __name__ == "__main__":
    # Example job data (as would come from the LinkedIn crawler)
    sample_job_data = [
        {
            "JobID": "sample123",
            "Title": "Senior Python Developer",
            "Company": "Tech Corp",
            "Salary": "$80,000 - $120,000",
            "Location": "San Francisco, CA",
            "Posted_Date": "2025-07-30",
            "Job_Expertise": "Senior",
            "Skills": "Python, Django, PostgreSQL, AWS, Docker",
            "Benefits": "Health insurance, 401k",
            "Description": "We are looking for a senior Python developer...",
            "Experience_Requirements": "5+ years",
            "Link": "https://linkedin.com/jobs/view/sample123"
        }
    ]
    
    # Initialize inserter
    inserter = JobDatabaseInserter()
    
    try:
        # Insert batch
        stats = inserter.insert_job_batch(sample_job_data)
        
        # Show database stats
        db_stats = inserter.get_database_stats()
        print(f"\n📊 Current database stats: {db_stats}")
        
    finally:
        inserter.close_connection()
