import os
import psycopg
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def create_tables_and_populate_skills():
    """Create database tables and populate the skill table only."""
    try:
        # Connect to database
        conn_string = os.getenv('DB_CONNECTION')
        if not conn_string:
            raise ValueError("DB_CONNECTION environment variable not found")
        
        conn = psycopg.connect(conn_string)
        cur = conn.cursor()
        print("✓ Connected to database successfully!")
        
        # Create tables
        print("\n📋 Creating database tables...")
        
        # Create job table
        print("   Creating job table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job (
                job_id SERIAL PRIMARY KEY,
                job_title VARCHAR(255) NOT NULL,
                job_expertise VARCHAR(255) NOT NULL,
                description TEXT,
                requirements TEXT,
                salary VARCHAR(255),
                location VARCHAR(255),
                posted_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                yoe VARCHAR(255),
                work_type VARCHAR(50)
            );
        """)
        
        # Create skill table
        print("   Creating skill table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS skill (
                skill_id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                description TEXT
            );
        """)
        
        # Create job_skill table
        print("   Creating job_skill table...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS job_skill (
                job_id INT NOT NULL,
                skill_id INT NOT NULL,
                relevance FLOAT,
                PRIMARY KEY (job_id, skill_id),
                CONSTRAINT fk_job
                    FOREIGN KEY(job_id)
                    REFERENCES job(job_id)
                    ON DELETE CASCADE,
                CONSTRAINT fk_skill
                    FOREIGN KEY(skill_id)
                    REFERENCES skill(skill_id)
                    ON DELETE CASCADE
            );
        """)
        
        print("✓ Database tables created successfully!")
        
        # Load and populate skills
        print("\n🏷️  Populating skills table...")
        
        # Load skills from file
        skills_file = os.path.join(os.path.dirname(__file__), 'it_skill_tags.txt')
        if not os.path.exists(skills_file):
            print(f"✗ Skills file not found: {skills_file}")
            return
        
        skills = []
        with open(skills_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line:
                    # Parse skills from the format: 'SkillName',
                    if line.startswith("'") and line.endswith("',"):
                        skill = line[1:-2]  # Remove quotes and comma
                        skills.append(skill)
                    elif line.startswith("'") and line.endswith("'"):
                        skill = line[1:-1]  # Remove quotes only
                        skills.append(skill)
        
        print(f"   Found {len(skills)} skills to insert")
        
        # Insert skills into database
        skills_inserted = 0
        for skill_name in skills:
            try:
                cur.execute(
                    "INSERT INTO skill (name, description) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                    (skill_name, f"IT skill: {skill_name}")
                )
                if cur.rowcount > 0:
                    skills_inserted += 1
            except Exception as e:
                print(f"   ⚠ Error inserting skill '{skill_name}': {e}")
                continue
        
        # Commit all changes
        conn.commit()
        
        print(f"✓ Successfully inserted {skills_inserted} skills")
        
        # Verify the setup
        print("\n🔍 Verifying database setup...")
        
        # Check tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name IN ('job', 'skill', 'job_skill')
            ORDER BY table_name;
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        for table in ['job', 'job_skill', 'skill']:
            if table in tables:
                print(f"   ✓ Table '{table}' exists")
            else:
                print(f"   ✗ Table '{table}' missing")
        
        # Check skill count
        cur.execute("SELECT COUNT(*) FROM skill")
        skill_count = cur.fetchone()[0]
        print(f"   Skills in database: {skill_count}")
        
        # Show sample skills
        cur.execute("SELECT name FROM skill ORDER BY name LIMIT 10")
        sample_skills = [row[0] for row in cur.fetchall()]
        print(f"   Sample skills: {', '.join(sample_skills)}")
        
        print("\n🎉 Database setup completed successfully!")
        print("Tables created and skill table populated.")
        print("Ready for job data when needed.")
        
        # Close connections
        cur.close()
        conn.close()
        print("✓ Database connection closed")
        
    except Exception as e:
        print(f"❌ Error setting up database: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

if __name__ == "__main__":
    print("🚀 Database Setup - Tables and Skills Only")
    print("=" * 50)
    create_tables_and_populate_skills()
