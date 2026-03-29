"""
Reset database with admin user
Run this to completely reset your database
"""

import os
from app import app, db
from models import User, Subscription
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta

def reset_database():
    """Delete existing database and create new one with admin"""

    # Delete existing database
    db_path = os.path.join(os.path.dirname(__file__), 'instance', 'fundiconnect.db')
    if os.path.exists(db_path):
        print(f"Removing existing database...")
        os.remove(db_path)

    # Create fresh database
    with app.app_context():
        print("Creating fresh database...")
        db.create_all()

        # Create admin user
        admin = User(
            phone="254713324672",
            password_hash=generate_password_hash("123456"),
            user_type="admin",
            name="Admin User",
            email="admin@fundiconnect.co.ke",
            is_admin=True,
            admin_phone_verified=True
        )
        db.session.add(admin)
        db.session.flush()

        # Create free subscription for admin
        free_sub = Subscription(
            user_id=admin.id,
            plan_type='free',
            amount_paid=0,
            payment_status='completed',
            is_active=True,
            expires_at=datetime.utcnow() + timedelta(days=36500)
        )
        db.session.add(free_sub)

        db.session.commit()

        print("✓ Database created successfully!")
        print("\nAdmin credentials:")
        print("  Phone: 254713324672")
        print("  Password: 123456")
        print("\nYou can now login to the admin dashboard!")

if __name__ == '__main__':
    reset_database()
