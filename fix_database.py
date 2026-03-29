"""
Fix database schema to allow NULL emails and add missing columns
Run this script once to fix the database
"""

import sqlite3
import os

def fix_database():
    """Fix the database schema to allow NULL emails and add missing columns"""
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'fundiconnect.db')

    # Create instance directory if it doesn't exist
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    # Delete existing database to recreate with correct schema
    if os.path.exists(db_path):
        print("Deleting existing database...")
        os.remove(db_path)
        print("Database deleted. It will be recreated with correct schema when you run the app.")
    else:
        print("No existing database found.")

    print("Run 'python app.py' to create the database with the correct schema.")

if __name__ == '__main__':
    fix_database()
