import sqlite3
import json
import os

db_path = 'instance/fundiconnect.db'

if not os.path.exists(db_path):
    print(f"❌ Database not found at {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

print("=" * 70)
print("Checking Social Links in Database")
print("=" * 70)

# Check if columns exist
cursor.execute("PRAGMA table_info(worker_profiles)")
columns = [col[1] for col in cursor.fetchall()]

print("\n📊 Checking for premium columns in worker_profiles:")
premium_columns = ['whatsapp', 'facebook', 'instagram', 'twitter', 'linkedin', 'website', 'certifications', 'portfolio_images']
for col in premium_columns:
    if col in columns:
        print(f"  ✅ {col}: EXISTS")
    else:
        print(f"  ❌ {col}: MISSING")

# Get all workers with any social links
print("\n👥 Workers with social links:")
print("-" * 70)

cursor.execute("""
    SELECT wp.id, u.name, u.phone,
           wp.whatsapp, wp.facebook, wp.instagram, wp.twitter, wp.linkedin, wp.website
    FROM worker_profiles wp
    JOIN users u ON wp.user_id = u.id
    WHERE wp.whatsapp IS NOT NULL AND wp.whatsapp != ''
       OR wp.facebook IS NOT NULL AND wp.facebook != ''
       OR wp.instagram IS NOT NULL AND wp.instagram != ''
       OR wp.twitter IS NOT NULL AND wp.twitter != ''
       OR wp.linkedin IS NOT NULL AND wp.linkedin != ''
       OR wp.website IS NOT NULL AND wp.website != ''
""")

results = cursor.fetchall()

if results:
    for row in results:
        wp_id, name, phone, whatsapp, facebook, instagram, twitter, linkedin, website = row
        print(f"\n👤 {name} (Phone: {phone})")
        print(f"   WhatsApp: {whatsapp if whatsapp else '❌ Not set'}")
        print(f"   Facebook: {facebook if facebook else '❌ Not set'}")
        print(f"   Instagram: {instagram if instagram else '❌ Not set'}")
        print(f"   Twitter: {twitter if twitter else '❌ Not set'}")
        print(f"   LinkedIn: {linkedin if linkedin else '❌ Not set'}")
        print(f"   Website: {website if website else '❌ Not set'}")
else:
    print("   No workers have social links set")

# Also check for workers that might have social links set to empty strings
print("\n📊 Workers with social links as empty strings:")
cursor.execute("""
    SELECT u.name, wp.whatsapp, wp.facebook, wp.instagram
    FROM worker_profiles wp
    JOIN users u ON wp.user_id = u.id
    WHERE wp.whatsapp = '' OR wp.facebook = '' OR wp.instagram = '' OR wp.twitter = '' OR wp.linkedin = '' OR wp.website = ''
""")
empty_results = cursor.fetchall()
if empty_results:
    for row in empty_results:
        print(f"   {row[0]}: has some empty string fields")
else:
    print("   No workers have empty string social links")

# Check total worker count
cursor.execute("SELECT COUNT(*) FROM worker_profiles")
total_workers = cursor.fetchone()[0]
print(f"\n📊 Total workers in database: {total_workers}")

conn.close()

print("\n" + "=" * 70)
print("If you see social links in the database but not on the profile,")
print("check the Flask logs for errors in the worker_profile route.")
print("=" * 70)
