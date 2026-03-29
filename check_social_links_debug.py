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
print("VERIFYING SOCIAL LINKS IN DATABASE")
print("=" * 70)

# Get all workers with their social links
cursor.execute("""
    SELECT u.id, u.name, u.user_type, u.email,
           wp.whatsapp, wp.facebook, wp.instagram, wp.twitter, wp.linkedin, wp.website,
           wp.certifications, wp.portfolio_images
    FROM users u
    LEFT JOIN worker_profiles wp ON u.id = wp.user_id
    WHERE u.user_type = 'worker'
""")

results = cursor.fetchall()

if results:
    print(f"\n📊 Found {len(results)} workers:\n")
    for row in results:
        user_id, name, user_type, email, whatsapp, facebook, instagram, twitter, linkedin, website, certs, portfolio = row

        print(f"👤 Worker: {name} (ID: {user_id})")
        print(f"   Email: {email or 'Not set'}")
        print(f"   WhatsApp: {repr(whatsapp)}")
        print(f"   Facebook: {repr(facebook)}")
        print(f"   Instagram: {repr(instagram)}")
        print(f"   Twitter: {repr(twitter)}")
        print(f"   LinkedIn: {repr(linkedin)}")
        print(f"   Website: {repr(website)}")
        print(f"   Certifications: {repr(certs)}")
        print(f"   Portfolio: {repr(portfolio)}")
        print("-" * 50)
else:
    print("No workers found in database")

# Also check if the worker has premium subscription
print("\n" + "=" * 70)
print("CHECKING PREMIUM SUBSCRIPTIONS")
print("=" * 70)

cursor.execute("""
    SELECT u.id, u.name, s.plan_type, s.is_active, s.payment_status, s.expires_at
    FROM users u
    JOIN subscriptions s ON u.id = s.user_id
    WHERE u.user_type = 'worker' AND s.plan_type != 'free'
""")

premium_results = cursor.fetchall()

if premium_results:
    print(f"\n📊 Workers with premium subscriptions:\n")
    for row in premium_results:
        user_id, name, plan_type, is_active, payment_status, expires_at = row
        print(f"   {name} (ID: {user_id}) - Plan: {plan_type}, Active: {is_active}, Status: {payment_status}, Expires: {expires_at}")
else:
    print("\n⚠️ No workers have premium subscriptions!")

conn.close()

print("\n" + "=" * 70)
print("If you see social links with values like 'None' or empty strings,")
print("the data is not saved properly. If you see actual values,")
print("check if the worker has an active premium subscription.")
print("=" * 70)
