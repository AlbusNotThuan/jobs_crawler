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
    cur.execute("SELECT * FROM skill")
    skills = cur.fetchall()
    print("Skills in the database:")
    for skill in skills:
        print(" -", skill)

    # Close the cursor and connection
    cur.close()
    conn.close()

except (Exception, psycopg.Error) as error:
    print("Error while connecting to PostgreSQL", error)