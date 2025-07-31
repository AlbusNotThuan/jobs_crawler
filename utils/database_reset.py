import psycopg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def reset_database():
    """Reset the database by dropping all tables and recreating them."""
    try:
        conn_string = os.getenv('DB_CONNECTION')
        if not conn_string:
            raise ValueError("DB_CONNECTION environment variable not found")
        
        # Connect to database
        conn = psycopg.connect(conn_string)
        cur = conn.cursor()
        print("✓ Connected to database successfully!")
        
        print("\n🗑️  Dropping existing tables...")
        
        # Drop tables in correct order (due to foreign key constraints)
        tables_to_drop = ['job_skill', 'job', 'skill']
        
        for table in tables_to_drop:
            try:
                cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")
                print(f"   ✓ Dropped table: {table}")
            except Exception as e:
                print(f"   ⚠ Error dropping table {table}: {e}")
        
        # Drop indexes if they exist
        print("\n🗑️  Dropping existing indexes...")
        indexes_to_drop = [
            'idx_job_title',
            'idx_job_location',
            'idx_job_posted_date',
            'idx_job_yoe',
            'idx_skill_name',
            'idx_job_skill_job_id',
            'idx_job_skill_skill_id'
        ]
        
        for index in indexes_to_drop:
            try:
                cur.execute(f"DROP INDEX IF EXISTS {index};")
                print(f"   ✓ Dropped index: {index}")
            except Exception as e:
                print(f"   ⚠ Error dropping index {index}: {e}")
        
        # Commit the drops
        conn.commit()
        
        print("\n✅ Database reset completed successfully!")
        print("All tables and indexes have been dropped.")
        print("\nTo recreate the database structure, run:")
        print("   python populate_database.py --setup")
        
        # Close connections
        cur.close()
        conn.close()
        print("✓ Database connection closed")
        
    except Exception as e:
        print(f"❌ Error resetting database: {e}")
        if 'conn' in locals():
            conn.rollback()
            conn.close()

def confirm_reset():
    """Ask for user confirmation before resetting."""
    print("⚠️  DATABASE RESET WARNING ⚠️")
    print("=" * 50)
    print("This will permanently delete ALL data in the database:")
    print("- All job records")
    print("- All skill records") 
    print("- All job-skill relationships")
    print("- All tables and indexes")
    print("\nThis action CANNOT be undone!")
    print("=" * 50)
    
    confirmation = input("\nType 'RESET' to confirm deletion: ").strip()
    
    if confirmation == 'RESET':
        return True
    else:
        print("❌ Reset cancelled. Database unchanged.")
        return False

if __name__ == "__main__":
    print("🚀 Database Reset Utility")
    print("=" * 30)
    
    if confirm_reset():
        reset_database()
    else:
        print("Database reset aborted.")
