import psycopg
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

conn_string = os.getenv('DB_CONNECTION')

try:
    # Connect to your postgres DB
    conn = psycopg.connect(conn_string)
    print("Connected to the database successfully!")

    # Open a cursor to perform database operations
    cur = conn.cursor()

    # Example: Execute a query
    cur.execute("SELECT * FROM job")
    jobs = cur.fetchall()
    print("Jobs in the database:")
    for job in jobs:
        print(" -", job)

    # Close the cursor and connection
    cur.close()
    conn.close()

except (Exception, psycopg.Error) as error:
    print("Error while connecting to PostgreSQL", error)