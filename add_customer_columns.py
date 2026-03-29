import sqlite3
import os

# Path to your database
db_path = 'instance/fundiconnect.db'

def add_customer_columns():
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        print("Make sure you're in the correct directory")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get existing columns
        cursor.execute("PRAGMA table_info(users)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        print(f"📁 Database found at: {db_path}")
        print(f"📊 Existing columns: {len(existing_columns)}")
        print("-" * 50)

        # Define columns to add
        columns = {
            'company_name': 'VARCHAR(200)',
            'business_location': 'VARCHAR(200)',
            'company_description': 'TEXT',
            'preferred_categories': 'VARCHAR(500)',
            'budget_range': 'VARCHAR(100)',
            'verified_only': 'BOOLEAN DEFAULT 0',
            'priority_listing': 'BOOLEAN DEFAULT 0'
        }

        added = []
        skipped = []
        failed = []

        for col_name, col_type in columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
                    conn.commit()
                    added.append(col_name)
                    print(f"✅ Added column: {col_name}")
                except Exception as e:
                    failed.append(col_name)
                    print(f"❌ Failed to add {col_name}: {e}")
            else:
                skipped.append(col_name)
                print(f"⏭️  Column already exists: {col_name}")

        conn.close()

        print("-" * 50)
        print(f"✅ Successfully added: {len(added)} columns")
        print(f"⏭️  Already existed: {len(skipped)} columns")
        if failed:
            print(f"❌ Failed: {len(failed)} columns")

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == '__main__':
    add_customer_columns()
