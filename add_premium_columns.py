"""
FundiConnect - Database Migration Script
Adds premium feature columns to worker_profiles table
Run this script once to update your database
"""

import sqlite3
import os

# Path to your database
DB_PATH = 'instance/fundiconnect.db'

def add_premium_columns():
    """Add all premium feature columns to worker_profiles table"""

    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found at {DB_PATH}")
        print("Please run your Flask app first to create the database.")
        return False

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Get existing columns
        cursor.execute("PRAGMA table_info(worker_profiles)")
        existing_columns = [col[1] for col in cursor.fetchall()]

        print("=" * 60)
        print("FundiConnect - Premium Features Database Update")
        print("=" * 60)
        print(f"\n📁 Database: {DB_PATH}")
        print(f"📊 Existing columns: {len(existing_columns)}")

        # Define columns to add
        columns_to_add = {
            'portfolio_images': 'TEXT',
            'certifications': 'TEXT',
            'whatsapp': 'VARCHAR(20)',
            'facebook': 'VARCHAR(200)',
            'instagram': 'VARCHAR(100)',
            'twitter': 'VARCHAR(100)',
            'linkedin': 'VARCHAR(200)',
            'website': 'VARCHAR(200)'
        }

        print("\n📝 Adding missing columns...")
        print("-" * 40)

        added_count = 0
        for col_name, col_type in columns_to_add.items():
            if col_name not in existing_columns:
                try:
                    sql = f"ALTER TABLE worker_profiles ADD COLUMN {col_name} {col_type}"
                    cursor.execute(sql)
                    added_count += 1
                    print(f"✅ Added: {col_name}")
                except Exception as e:
                    print(f"❌ Failed to add {col_name}: {e}")
            else:
                print(f"✓ Already exists: {col_name}")

        # Commit changes
        conn.commit()

        # Verify final columns
        cursor.execute("PRAGMA table_info(worker_profiles)")
        final_columns = [col[1] for col in cursor.fetchall()]

        print("-" * 40)
        print(f"\n📊 Summary:")
        print(f"   • Columns added: {added_count}")
        print(f"   • Total columns now: {len(final_columns)}")

        conn.close()

        print("\n✅ Database update completed!")
        print("=" * 60)
        return True

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    add_premium_columns()
