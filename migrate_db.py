import os
import mysql.connector
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'notes_db'),
    'port': int(os.getenv('DB_PORT', 3306))
}

def migrate():
    print(f"🔌 Connecting to database {DB_CONFIG['database']}...")
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Columns to add to 'users' table
        new_columns = [
            ("first_name", "VARCHAR(50)"),
            ("last_name", "VARCHAR(50)"),
            ("bio", "TEXT"),
            ("avatar_url", "VARCHAR(512)"),
            ("timezone", "VARCHAR(50) DEFAULT 'UTC'"),
            ("profile_complete", "BOOLEAN DEFAULT FALSE")
        ]
        
        print("🔍 Checking 'users' table for missing columns...")
        
        for col_name, col_def in new_columns:
            try:
                # Try to add the column
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                print(f"✅ Added column: {col_name}")
            except mysql.connector.Error as err:
                # Error 1060: Duplicate column name
                if err.errno == 1060:
                    print(f"⚠️  Column '{col_name}' already exists (skipping)")
                else:
                    print(f"❌ Error adding '{col_name}': {err}")
        
        conn.commit()
        print("\n✨ Migration completed successfully!")
        
    except mysql.connector.Error as err:
        print(f"❌ Database connection error: {err}")
        print("Check your .env file credentials.")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    migrate()
