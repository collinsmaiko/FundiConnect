import sqlite3
import os

# Path to your database
db_path = 'instance/fundiconnect.db'

if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get existing columns in reports table
    cursor.execute("PRAGMA table_info(reports)")
    existing_cols = [col[1] for col in cursor.fetchall()]

    # Add missing columns
    new_columns = {
        'reporter_ip': "ALTER TABLE reports ADD COLUMN reporter_ip VARCHAR(45)",
        'reporter_user_agent': "ALTER TABLE reports ADD COLUMN reporter_user_agent VARCHAR(500)",
        'is_urgent': "ALTER TABLE reports ADD COLUMN is_urgent BOOLEAN DEFAULT 0",
        'escalation_level': "ALTER TABLE reports ADD COLUMN escalation_level INTEGER DEFAULT 1",
        'status_history': "ALTER TABLE reports ADD COLUMN status_history TEXT",
        'resolution_type': "ALTER TABLE reports ADD COLUMN resolution_type VARCHAR(50)",
        'action_taken': "ALTER TABLE reports ADD COLUMN action_taken TEXT",
        'action_taken_by': "ALTER TABLE reports ADD COLUMN action_taken_by INTEGER",
        'action_taken_at': "ALTER TABLE reports ADD COLUMN action_taken_at DATETIME",
        'follow_up_required': "ALTER TABLE reports ADD COLUMN follow_up_required BOOLEAN DEFAULT 0",
        'follow_up_at': "ALTER TABLE reports ADD COLUMN follow_up_at DATETIME",
        'follow_up_notes': "ALTER TABLE reports ADD COLUMN follow_up_notes TEXT",
        'viewed_at': "ALTER TABLE reports ADD COLUMN viewed_at DATETIME",
        'acknowledged_at': "ALTER TABLE reports ADD COLUMN acknowledged_at DATETIME"
    }

    print("Checking reports table columns...")
    for col, sql in new_columns.items():
        if col not in existing_cols:
            try:
                cursor.execute(sql)
                print(f"✓ Added column: {col}")
            except Exception as e:
                print(f"✗ Error adding {col}: {e}")
        else:
            print(f"  Column already exists: {col}")

    conn.commit()
    conn.close()
    print("\nDatabase update complete!")
else:
    print(f"Database not found at {db_path}")
