"""
FundiConnect - Enterprise Platform for Skilled Workers
Version: 3.2.0 - COMPLETE SUBSCRIPTION SYSTEM WITH WORKER AND CUSTOMER PLANS
Copyright: FundiConnect Inc.
"""

import os
import uuid
import json
import logging
import sqlite3
import traceback
import smtplib
import re
import threading
import time
import secrets
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from werkzeug.middleware.proxy_fix import ProxyFix
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Path to your database
db_path = 'instance/fundiconnect.db'

# ==================== CONFIGURATION ====================

class Config:
    """Application configuration with environment variable support"""
    SECRET_KEY = os.environ.get('SECRET_KEY', secrets.token_hex(32))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///fundiconnect.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 10,
        'pool_recycle': 3600,
        'pool_pre_ping': True
    }
    UPLOAD_FOLDER = 'static/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    SESSION_COOKIE_SECURE = os.environ.get('SESSION_COOKIE_SECURE', 'true').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'support.fundiconnect@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'support.fundiconnect@gmail.com')

    # Email sending toggle
    SEND_EMAILS = os.environ.get('SEND_EMAILS', 'true').lower() == 'true'

    # Welcome email grace period (24 hours in seconds)
    WELCOME_EMAIL_GRACE_PERIOD = int(os.environ.get('WELCOME_EMAIL_GRACE_PERIOD', 24 * 60 * 60))

    # Debug mode
    DEBUG = os.environ.get('DEBUG', 'true').lower() == 'true'

    # FREE PLAN LIMITS
    FREE_PLAN_LIMITS = {
        'workers': {
            'max_job_applications': 5,
            'featured_listing': False,
            'verified_badge': False,
            'job_alerts': False,
            'analytics': False,
            'qr_code': False,
            'can_post_jobs': False,
            'can_view_verification_details': False,
            'max_profile_views_per_day': 50,
            'max_messages_per_day': 10
        },
        'customers': {
            'max_job_posts': 3,
            'priority_listing': False,
            'worker_verification_access': False,
            'advanced_filters': False,
            'can_view_verified_only': False,
            'max_worker_contacts_per_day': 10
        }
    }

    # WORKER PLANS - Features for workers (job applications focus)
    WORKER_PLANS = {
        'daily': {
            'name': 'Daily Premium',
            'price': 50,
            'duration_days': 1,
            'features': {
                'max_job_applications': 999,
                'featured_listing': True,
                'job_alerts': True,
                'analytics': False,
                'verified_badge': False,
                'qr_code': False,
                'max_profile_views_per_day': 999,
                'max_messages_per_day': 999
            }
        },
        'weekly': {
            'name': 'Weekly Premium',
            'price': 200,
            'duration_days': 7,
            'features': {
                'max_job_applications': 999,
                'featured_listing': True,
                'job_alerts': True,
                'analytics': True,
                'verified_badge': True,
                'qr_code': False,
                'max_profile_views_per_day': 999,
                'max_messages_per_day': 999
            }
        },
        'monthly': {
            'name': 'Monthly Premium',
            'price': 500,
            'duration_days': 30,
            'features': {
                'max_job_applications': 999,
                'featured_listing': True,
                'job_alerts': True,
                'analytics': True,
                'verified_badge': True,
                'qr_code': True,
                'max_profile_views_per_day': 999,
                'max_messages_per_day': 999
            }
        },
        'annual': {
            'name': 'Annual Premium',
            'price': 5000,
            'duration_days': 365,
            'features': {
                'max_job_applications': 999,
                'featured_listing': True,
                'job_alerts': True,
                'analytics': True,
                'verified_badge': True,
                'qr_code': True,
                'max_profile_views_per_day': 999,
                'max_messages_per_day': 999,
                'priority_support': True
            }
        }
    }

    # CUSTOMER PLANS - Features for customers (job posting focus)
    CUSTOMER_PLANS = {
        'daily': {
            'name': 'Daily Premium',
            'price': 30,
            'duration_days': 1,
            'features': {
                'max_job_posts': 5,
                'priority_listing': False,
                'verified_workers_only': False,
                'view_verification_details': False,
                'advanced_filters': False,
                'max_worker_contacts_per_day': 25
            }
        },
        'weekly': {
            'name': 'Weekly Premium',
            'price': 100,
            'duration_days': 7,
            'features': {
                'max_job_posts': 999,
                'priority_listing': True,
                'verified_workers_only': True,
                'view_verification_details': True,
                'advanced_filters': True,
                'max_worker_contacts_per_day': 999
            }
        },
        'monthly': {
            'name': 'Monthly Premium',
            'price': 300,
            'duration_days': 30,
            'features': {
                'max_job_posts': 999,
                'priority_listing': True,
                'verified_workers_only': True,
                'view_verification_details': True,
                'advanced_filters': True,
                'max_worker_contacts_per_day': 999
            }
        },
        'annual': {
            'name': 'Annual Premium',
            'price': 3000,
            'duration_days': 365,
            'features': {
                'max_job_posts': 999,
                'priority_listing': True,
                'verified_workers_only': True,
                'view_verification_details': True,
                'advanced_filters': True,
                'max_worker_contacts_per_day': 999,
                'priority_support': True,
                'dedicated_account_manager': True
            }
        }
    }

app = Flask(__name__)
app.config.from_object(Config)
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Create directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('logs', exist_ok=True)
os.makedirs('instance', exist_ok=True)
os.makedirs('backups', exist_ok=True)

# Setup logging with rotation
from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler('logs/fundiconnect.log', maxBytes=10485760, backupCount=5)
file_handler.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        file_handler,
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import models
from models import db, User, WorkerProfile, Review, JobPost, JobApplication, Subscription, VerificationRequest, Payment, AuditLog, NewsletterSubscriber, SuccessStory, Report, Notification
db.init_app(app)

# ==================== CATEGORIES ====================

CATEGORIES = {
    'plumbing': {'name': 'Plumbing', 'icon': '🔧', 'description': 'Pipe installation, leak repair, water systems', 'popular': True},
    'electrical': {'name': 'Electrical', 'icon': '⚡', 'description': 'Wiring, circuit installation, lighting', 'popular': True},
    'carpentry': {'name': 'Carpentry', 'icon': '🪵', 'description': 'Woodwork, furniture, cabinets', 'popular': True},
    'painting': {'name': 'Painting', 'icon': '🎨', 'description': 'Interior/exterior painting, wall finishing', 'popular': True},
    'cleaning': {'name': 'Cleaning', 'icon': '🧹', 'description': 'House cleaning, office cleaning, sanitization', 'popular': False},
    'construction': {'name': 'Construction', 'icon': '🏗️', 'description': 'Building, masonry, tiling, concrete work', 'popular': True},
    'mechanical': {'name': 'Mechanical', 'icon': '🔩', 'description': 'Auto repair, engine service, maintenance', 'popular': False},
    'it': {'name': 'IT & Tech', 'icon': '💻', 'description': 'Computer repair, software, networking', 'popular': True},
    'delivery': {'name': 'Delivery', 'icon': '🚚', 'description': 'Parcel delivery, logistics, courier', 'popular': False},
    'landscaping': {'name': 'Landscaping', 'icon': '🌿', 'description': 'Garden design, lawn care, planting', 'popular': False},
    'security': {'name': 'Security', 'icon': '🛡️', 'description': 'Security systems, guards, surveillance', 'popular': False},
    'tutoring': {'name': 'Tutoring', 'icon': '📚', 'description': 'Academic tutoring, test preparation', 'popular': True},
    'events': {'name': 'Events', 'icon': '🎉', 'description': 'Event planning, decoration, catering', 'popular': False},
    'general': {'name': 'General', 'icon': '📋', 'description': 'General services', 'popular': True}
}

# ==================== NOTIFICATION SYSTEM ====================

class NotificationManager:
    """Manage admin notifications with real-time updates"""
    def __init__(self):
        self.notifications = []
        self.notification_id_counter = 1

    def add_notification(self, title, message, type="info", user_id=None, user_name=None, action_url=None):
        notification = {
            'id': self.notification_id_counter,
            'title': title,
            'message': message,
            'type': type,
            'user_id': user_id,
            'user_name': user_name,
            'action_url': action_url,
            'created_at': datetime.utcnow().isoformat(),
            'read': False
        }
        self.notifications.insert(0, notification)
        self.notification_id_counter += 1
        if len(self.notifications) > 100:
            self.notifications = self.notifications[:100]
        logger.info(f"📢 NOTIFICATION: {title} - {message}")
        return notification

    def get_unread_count(self):
        return len([n for n in self.notifications if not n.get('read', False)])

    def get_all_notifications(self):
        return self.notifications

    def get_recent_notifications(self, limit=20):
        return self.notifications[:limit]

    def mark_as_read(self, notification_id):
        for n in self.notifications:
            if n['id'] == notification_id:
                n['read'] = True
                return True
        return False

    def mark_all_as_read(self):
        for n in self.notifications:
            n['read'] = True
        return True

    def clear_all(self):
        self.notifications = []
        self.notification_id_counter = 1
        return True

notification_manager = NotificationManager()


# ==================== NOTIFICATION HELPER FUNCTIONS ====================

def notify_admin(title, message, type="info", user_id=None, user_name=None, action_url=None):
    notification = notification_manager.add_notification(title, message, type, user_id, user_name, action_url)
    try:
        admin = User.query.filter_by(is_admin=True).first()
        if admin:
            log_audit_event(admin.id, 'admin_notification', f"{title}: {message}")
    except:
        pass
    return notification

def notify_user_activity(user, activity_type, details=""):
    if user.is_admin:
        return

    notification_templates = {
        'register': {'title': '👤 New User Registration', 'message': f'New {user.user_type.upper()} has joined: {user.name} ({user.phone})', 'type': 'success'},
        'login': {'title': '🔐 User Login', 'message': f'{user.name} ({user.user_type}) logged in at {datetime.utcnow().strftime("%H:%M:%S")}', 'type': 'info'},
        'payment': {'title': '💰 New Payment Request', 'message': f'{user.name} submitted payment for subscription. Waiting for verification.', 'type': 'warning'},
        'verification': {'title': '✅ Verification Request', 'message': f'{user.name} requested worker verification. Check and approve.', 'type': 'warning'},
        'job_post': {'title': '📋 New Job Posted', 'message': f'{user.name} posted a new job: "{details}"', 'type': 'info'},
        'application': {'title': '📝 Job Application', 'message': f'{user.name} applied for a job. Review application.', 'type': 'info'},
        'review': {'title': '⭐ New Review', 'message': f'{user.name} left a review for a worker.', 'type': 'info'},
        'subscription': {'title': '💎 Subscription Purchase', 'message': f'{user.name} purchased a {details} subscription. Awaiting payment verification.', 'type': 'warning'},
        'story_submission': {'title': '📖 New Success Story', 'message': f'New story from {user.name} is pending approval.', 'type': 'warning'}
    }

    template = notification_templates.get(activity_type, {
        'title': '📢 User Activity',
        'message': f'{user.name} performed: {activity_type}',
        'type': 'info'
    })

    return notify_admin(
        title=template['title'],
        message=template['message'],
        type=template['type'],
        user_id=user.id,
        user_name=user.name
    )


# ==================== SETTINGS MANAGEMENT ====================

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), 'instance', 'settings.json')

def load_settings():
    default_settings = {
        'platform_name': 'FundiConnect',
        'platform_tagline': 'Connecting Kenya with Trusted Skilled Workers',
        'contact_email': 'support@fundiconnect.co.ke',
        'contact_phone': '+254 713 324 672',
        'mpesa_paybill': '123456',
        'mpesa_account_name': 'FundiConnect',
        'updated_at': None,
        'updated_by': None,
        'maintenance_mode': False,
        'maintenance_message': 'Under maintenance. Please check back soon.',
        'registration_enabled': True,
        'job_posting_enabled': True
    }
    try:
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                saved_settings = json.load(f)
                default_settings.update(saved_settings)
        return default_settings
    except Exception as e:
        logger.error(f"Error loading settings: {e}")
        return default_settings

def save_settings(settings):
    try:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(settings, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving settings: {e}")
        return False

# ==================== EMAIL FUNCTIONS ====================

def send_email(to_email, subject, template_name, context):
    if not app.config['SEND_EMAILS']:
        logger.info(f"📧 EMAIL SIMULATION: Would send to {to_email} with subject: {subject}")
        return True
    if not to_email:
        logger.warning(f"Cannot send email: No recipient email address")
        return False
    if not app.config['MAIL_USERNAME'] or not app.config['MAIL_PASSWORD']:
        logger.warning(f"⚠️ EMAIL NOT SENT - Missing credentials. Would send to {to_email}")
        return False
    try:
        template = render_template(f'emails/{template_name}', **context)
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = to_email

        # Add text version as fallback
        import re
        text_part = MIMEText(re.sub(r'<[^>]+>', '', template), 'plain')
        html_part = MIMEText(template, 'html')
        msg.attach(text_part)
        msg.attach(html_part)

        logger.info(f"📧 Attempting to send email to {to_email} via {app.config['MAIL_SERVER']}:{app.config['MAIL_PORT']}")
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        if app.config['MAIL_USE_TLS']:
            server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        logger.info(f"✅ Email sent successfully to {to_email}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email to {to_email}: {str(e)}")
        return False

def send_welcome_email(user):
    if not user or not user.email:
        return False
    time_since_creation = datetime.utcnow() - user.created_at
    if time_since_creation.total_seconds() > app.config['WELCOME_EMAIL_GRACE_PERIOD']:
        logger.info(f"User {user.email} is not new (created {time_since_creation.total_seconds()/3600:.1f} hours ago), skipping welcome email")
        return True
    settings = load_settings()
    base_url = request.url_root.rstrip('/')
    subscribe_url = f"{base_url}/subscribe-email?email={user.email}&user_id={user.id}"
    context = {
        'user_name': user.name,
        'user_email': user.email,
        'contact_email': settings.get('contact_email', 'support@fundiconnect.co.ke'),
        'contact_phone': settings.get('contact_phone', '+254 713 324 672'),
        'platform_name': settings.get('platform_name', 'FundiConnect'),
        'subscribe_url': subscribe_url,
        'pricing_url': f"{base_url}/pricing",
        'unsubscribe_url': f"{base_url}/unsubscribe?email={user.email}",
        'preferences_url': f"{base_url}/email-preferences?email={user.email}"
    }
    if user.user_type == 'worker':
        context.update({
            'dashboard_url': f"{base_url}/dashboard",
            'workers_url': f"{base_url}/workers",
            'verify_url': f"{base_url}/verify",
            'browse_jobs_url': f"{base_url}/jobs"
        })
        template = 'worker_welcome.html'
        subject = f"Welcome to {settings.get('platform_name', 'FundiConnect')}, {user.name}! Start Your Journey"
    else:
        context.update({
            'browse_jobs_url': f"{base_url}/jobs",
            'workers_url': f"{base_url}/workers",
            'post_job_url': f"{base_url}/post-job",
            'support_email': f"mailto:{settings.get('contact_email', 'support@fundiconnect.co.ke')}"
        })
        template = 'customer_welcome.html'
        subject = f"Welcome to {settings.get('platform_name', 'FundiConnect')}, {user.name}! Find Your Perfect Worker"
    logger.info(f"📧 Sending welcome email to {user.email} ({user.user_type}) - Created {time_since_creation.total_seconds()/3600:.1f} hours ago")
    return send_email(user.email, subject, template, context)


def send_subscription_activated_email(user, plan_type, expires_at):
    if not user.email:
        return False
    context = {
        'user_name': user.name,
        'plan_type': plan_type.upper(),
        'expires_at': expires_at.strftime('%B %d, %Y') if expires_at else 'Not specified',
        'platform_name': load_settings().get('platform_name', 'FundiConnect'),
        'dashboard_url': url_for('dashboard', _external=True),
        'contact_email': load_settings().get('contact_email', 'support@fundiconnect.co.ke'),
        'contact_phone': load_settings().get('contact_phone', '+254 713 324 672')
    }
    return send_email(user.email, f'Your {plan_type.upper()} Subscription is Now Active!',
                     'subscription_activated.html', context)


def send_subscription_expired_email(user, plan_type):
    if not user.email:
        return False
    context = {
        'user_name': user.name,
        'plan_type': plan_type.upper(),
        'platform_name': load_settings().get('platform_name', 'FundiConnect'),
        'pricing_url': url_for('pricing', _external=True),
        'renew_url': url_for('subscribe', _external=True),
        'contact_email': load_settings().get('contact_email', 'support@fundiconnect.co.ke'),
        'contact_phone': load_settings().get('contact_phone', '+254 713 324 672')
    }
    return send_email(user.email, f'Your {plan_type.upper()} Subscription Has Expired',
                    'subscription_expired.html', context)


# ==================== SUBSCRIPTION EXPIRATION FUNCTIONS ====================

def check_expired_subscriptions():
    try:
        now = datetime.utcnow()
        logger.info(f"🔍 Checking for expired subscriptions at {now}")
        expired_subs = Subscription.query.filter(
            Subscription.is_active == True,
            Subscription.payment_status == 'completed',
            Subscription.plan_type != 'free',
            Subscription.expires_at <= now
        ).all()
        expired_count = 0
        for sub in expired_subs:
            logger.info(f"⏰ Expiring subscription: User {sub.user.name} - Plan: {sub.plan_type} - Expired: {sub.expires_at}")
            sub.is_active = False
            sub.updated_at = now

            # Remove verification badge if worker and no other active premium
            if sub.user.user_type == 'worker' and sub.user.worker_profile:
                worker = sub.user.worker_profile
                has_other_active = Subscription.query.filter(
                    Subscription.user_id == sub.user.id,
                    Subscription.is_active == True,
                    Subscription.payment_status == 'completed',
                    Subscription.plan_type != 'free',
                    Subscription.id != sub.id,
                    Subscription.expires_at > now
                ).first()
                if not has_other_active and worker.is_verified:
                    worker.is_verified = False
                    worker.verification_badge = 'expired'

                    # Create notification for user
                    notification = Notification(
                        user_id=sub.user.id,
                        title="Verification Badge Removed",
                        message=f"Your verification badge has been removed because your {sub.plan_type.upper()} subscription expired. Renew to restore verification.",
                        type="warning",
                        created_at=now
                    )
                    db.session.add(notification)

            db.session.commit()
            expired_count += 1
            if sub.user.email and app.config['SEND_EMAILS']:
                send_subscription_expired_email(sub.user, sub.plan_type)
            notify_admin(
                title='⏰ Subscription Expired',
                message=f'{sub.user.name}\'s {sub.plan_type.upper()} subscription has expired.',
                type='warning',
                user_id=sub.user.id,
                user_name=sub.user.name
            )
        if expired_count > 0:
            logger.info(f"✅ Expired {expired_count} subscriptions")
        return expired_count
    except Exception as e:
        logger.error(f"Error checking expired subscriptions: {e}")
        logger.error(traceback.format_exc())
        return 0


# ==================== DATABASE INITIALIZATION ====================

def init_database():
    with app.app_context():
        try:
            db.create_all()
            db_path = os.path.join(os.path.dirname(__file__), 'instance', 'fundiconnect.db')
            if os.path.exists(db_path):
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                # Add missing columns to users table
                cursor.execute("PRAGMA table_info(users)")
                cols = [c[1] for c in cursor.fetchall()]

                if 'admin_phone_verified' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN admin_phone_verified BOOLEAN DEFAULT 0")
                if 'suspended' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN suspended BOOLEAN DEFAULT 0")
                if 'suspension_reason' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN suspension_reason TEXT")
                if 'suspended_at' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN suspended_at DATETIME")
                if 'suspended_by' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN suspended_by INTEGER REFERENCES users(id)")
                if 'email_verified' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT 0")
                if 'welcome_email_sent' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN welcome_email_sent BOOLEAN DEFAULT 0")
                if 'welcome_email_sent_at' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN welcome_email_sent_at DATETIME")
                if 'is_active' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1")
                if 'last_login' not in cols:
                    cursor.execute("ALTER TABLE users ADD COLUMN last_login DATETIME")

                # Add missing columns to worker_profiles table
                cursor.execute("PRAGMA table_info(worker_profiles)")
                cols = [c[1] for c in cursor.fetchall()]
                required_cols = {
                    'primary_category': "ALTER TABLE worker_profiles ADD COLUMN primary_category VARCHAR(50) DEFAULT 'general'",
                    'secondary_categories': "ALTER TABLE worker_profiles ADD COLUMN secondary_categories TEXT",
                    'cover_image': "ALTER TABLE worker_profiles ADD COLUMN cover_image VARCHAR(200) DEFAULT 'default-cover.jpg'",
                    'rating_score': "ALTER TABLE worker_profiles ADD COLUMN rating_score FLOAT DEFAULT 0.0",
                    'rating_count': "ALTER TABLE worker_profiles ADD COLUMN rating_count INTEGER DEFAULT 0",
                    'verified_at': "ALTER TABLE worker_profiles ADD COLUMN verified_at DATETIME",
                    'verified_by': "ALTER TABLE worker_profiles ADD COLUMN verified_by INTEGER",
                    'verification_badge': "ALTER TABLE worker_profiles ADD COLUMN verification_badge VARCHAR(20) DEFAULT 'none'",
                    'portfolio_images': "ALTER TABLE worker_profiles ADD COLUMN portfolio_images TEXT",
                    'certifications': "ALTER TABLE worker_profiles ADD COLUMN certifications TEXT",
                    'whatsapp': "ALTER TABLE worker_profiles ADD COLUMN whatsapp VARCHAR(20)",
                    'facebook': "ALTER TABLE worker_profiles ADD COLUMN facebook VARCHAR(200)",
                    'instagram': "ALTER TABLE worker_profiles ADD COLUMN instagram VARCHAR(100)",
                    'twitter': "ALTER TABLE worker_profiles ADD COLUMN twitter VARCHAR(100)",
                    'linkedin': "ALTER TABLE worker_profiles ADD COLUMN linkedin VARCHAR(200)",
                    'website': "ALTER TABLE worker_profiles ADD COLUMN website VARCHAR(200)"
                }
                for col, sql in required_cols.items():
                    if col not in cols:
                        try:
                            cursor.execute(sql)
                            logger.info(f"Added column {col} to worker_profiles")
                        except Exception as e:
                            logger.warning(f"Could not add column {col}: {e}")

                # Add missing columns to job_posts table
                cursor.execute("PRAGMA table_info(job_posts)")
                job_cols = [c[1] for c in cursor.fetchall()]
                if 'category' not in job_cols:
                    cursor.execute("ALTER TABLE job_posts ADD COLUMN category VARCHAR(50) DEFAULT 'general'")
                if 'budget_min' not in job_cols:
                    cursor.execute("ALTER TABLE job_posts ADD COLUMN budget_min FLOAT")
                if 'budget_max' not in job_cols:
                    cursor.execute("ALTER TABLE job_posts ADD COLUMN budget_max FLOAT")
                if 'skills_required' not in job_cols:
                    cursor.execute("ALTER TABLE job_posts ADD COLUMN skills_required TEXT")
                if 'template_used' not in job_cols:
                    cursor.execute("ALTER TABLE job_posts ADD COLUMN template_used VARCHAR(50) DEFAULT 'standard'")

                # Create payments table if not exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payments'")
                if not cursor.fetchone():
                    cursor.execute("""CREATE TABLE payments (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, subscription_id INTEGER, amount FLOAT NOT NULL, plan_type VARCHAR(20) NOT NULL, mpesa_transaction_id VARCHAR(100) UNIQUE, mpesa_phone VARCHAR(15), mpesa_receipt_number VARCHAR(100), screenshot_path VARCHAR(200), payment_date DATETIME, status VARCHAR(20) DEFAULT 'pending', payment_method VARCHAR(20) DEFAULT 'mpesa', verified_by INTEGER, verified_at DATETIME, FOREIGN KEY (user_id) REFERENCES users(id), FOREIGN KEY (subscription_id) REFERENCES subscriptions(id), FOREIGN KEY (verified_by) REFERENCES users(id))""")

                # Create audit_logs table if not exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_logs'")
                if not cursor.fetchone():
                    cursor.execute("""CREATE TABLE audit_logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, action VARCHAR(100) NOT NULL, details TEXT, ip_address VARCHAR(45), created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id))""")

                # Add payment_status to subscriptions table if missing
                cursor.execute("PRAGMA table_info(subscriptions)")
                sub_cols = [c[1] for c in cursor.fetchall()]
                if 'payment_status' not in sub_cols:
                    cursor.execute("ALTER TABLE subscriptions ADD COLUMN payment_status VARCHAR(20) DEFAULT 'pending'")

                # Create newsletter_subscribers table if not exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='newsletter_subscribers'")
                if not cursor.fetchone():
                    cursor.execute("""CREATE TABLE newsletter_subscribers (id INTEGER PRIMARY KEY AUTOINCREMENT, email VARCHAR(100) UNIQUE NOT NULL, user_id INTEGER REFERENCES users(id), is_active BOOLEAN DEFAULT 1, subscribed_at DATETIME DEFAULT CURRENT_TIMESTAMP, unsubscribed_at DATETIME)""")

                # Create success_stories table if not exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='success_stories'")
                if not cursor.fetchone():
                    cursor.execute("""CREATE TABLE success_stories (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER REFERENCES users(id), name VARCHAR(100) NOT NULL, email VARCHAR(100), category VARCHAR(50) NOT NULL, title VARCHAR(200) NOT NULL, story TEXT NOT NULL, rating INTEGER DEFAULT 5, is_approved BOOLEAN DEFAULT 0, featured BOOLEAN DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, approved_at DATETIME, profile_picture_cache VARCHAR(200))""")
                else:
                    cursor.execute("PRAGMA table_info(success_stories)")
                    story_cols = [c[1] for c in cursor.fetchall()]
                    if 'profile_picture_cache' not in story_cols:
                        try:
                            cursor.execute("ALTER TABLE success_stories ADD COLUMN profile_picture_cache VARCHAR(200)")
                            logger.info("Added profile_picture_cache column to success_stories table")
                        except Exception as e:
                            logger.warning(f"Could not add profile_picture_cache column: {e}")

                # Create reports table if not exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='reports'")
                if not cursor.fetchone():
                    cursor.execute("""CREATE TABLE reports (id INTEGER PRIMARY KEY AUTOINCREMENT, tracking_id VARCHAR(50) UNIQUE, reporter_id INTEGER REFERENCES users(id), reporter_name VARCHAR(100), reporter_email VARCHAR(100), reporter_ip VARCHAR(45), reporter_user_agent VARCHAR(500), report_type VARCHAR(50) NOT NULL, issue_title VARCHAR(200) NOT NULL, description TEXT NOT NULL, related_id VARCHAR(100), priority VARCHAR(20) DEFAULT 'medium', is_urgent BOOLEAN DEFAULT 0, escalation_level INTEGER DEFAULT 1, status VARCHAR(20) DEFAULT 'pending', status_history TEXT, resolved_by INTEGER REFERENCES users(id), resolved_at DATETIME, resolution_notes TEXT, resolution_type VARCHAR(50), action_taken TEXT, action_taken_by INTEGER REFERENCES users(id), action_taken_at DATETIME, follow_up_required BOOLEAN DEFAULT 0, follow_up_at DATETIME, follow_up_notes TEXT, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, updated_at DATETIME DEFAULT CURRENT_TIMESTAMP, viewed_at DATETIME, acknowledged_at DATETIME)""")
                else:
                    cursor.execute("PRAGMA table_info(reports)")
                    report_cols = [c[1] for c in cursor.fetchall()]
                    if 'tracking_id' not in report_cols:
                        try:
                            cursor.execute("ALTER TABLE reports ADD COLUMN tracking_id VARCHAR(50) UNIQUE")
                            logger.info("Added tracking_id column to reports table")
                        except Exception as e:
                            logger.warning(f"Could not add tracking_id column: {e}")
                    if 'reporter_ip' not in report_cols:
                        try:
                            cursor.execute("ALTER TABLE reports ADD COLUMN reporter_ip VARCHAR(45)")
                            logger.info("Added reporter_ip column to reports table")
                        except Exception as e:
                            logger.warning(f"Could not add reporter_ip column: {e}")
                    if 'reporter_user_agent' not in report_cols:
                        try:
                            cursor.execute("ALTER TABLE reports ADD COLUMN reporter_user_agent VARCHAR(500)")
                            logger.info("Added reporter_user_agent column to reports table")
                        except Exception as e:
                            logger.warning(f"Could not add reporter_user_agent column: {e}")
                    if 'updated_at' not in report_cols:
                        try:
                            cursor.execute("ALTER TABLE reports ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP")
                            logger.info("Added updated_at column to reports table")
                        except Exception as e:
                            logger.warning(f"Could not add updated_at column: {e}")

                # Create notifications table if not exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notifications'")
                if not cursor.fetchone():
                    cursor.execute("""CREATE TABLE notifications (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, title VARCHAR(200) NOT NULL, message TEXT NOT NULL, type VARCHAR(20) DEFAULT 'info', read BOOLEAN DEFAULT 0, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (user_id) REFERENCES users(id))""")

                conn.commit()
                conn.close()

            # Ensure all users have a free subscription
            for user in User.query.all():
                existing = Subscription.query.filter_by(user_id=user.id, plan_type='free').first()
                if not existing:
                    free_sub = Subscription(user_id=user.id, plan_type='free', amount_paid=0, payment_status='completed', is_active=True, expires_at=datetime.utcnow() + timedelta(days=36500))
                    db.session.add(free_sub)
            db.session.commit()
            logger.info("Database initialization completed")
        except Exception as e:
            logger.error(f"Database initialization error: {e}")
            db.session.rollback()

init_database()

# ==================== MIDDLEWARE ====================

@app.before_request
def check_suspended_user():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.suspended:
            session['suspended_user_id'] = user.id
            session['suspension_reason'] = user.suspension_reason
            session.pop('user_id', None)
            session.pop('user_type', None)
            session.pop('user_name', None)
            session.pop('is_admin', None)
            session.pop('has_admin_access', None)
            return redirect(url_for('suspended_account'))
    return None

@app.before_request
def check_maintenance_mode():
    """Check if site is in maintenance mode"""
    settings = load_settings()
    if settings.get('maintenance_mode', False):
        if request.endpoint not in ['maintenance', 'static'] and not session.get('is_admin'):
            return render_template('maintenance.html', message=settings.get('maintenance_message', 'Under maintenance')), 503
    return None

# ==================== HELPER FUNCTIONS ====================

def get_current_user():
    if 'user_id' not in session:
        return None
    return User.query.get(session['user_id'])

def user_has_premium(user):
    if not user:
        return False
    if user.is_admin:
        return True
    subscription = user.get_active_subscription()
    return subscription and subscription.plan_type != 'free' and subscription.is_active and not subscription.is_expired()

def user_can_get_verified_badge(user):
    if not user or user.user_type != 'worker':
        return False
    if user.is_admin:
        return True
    subscription = user.get_active_subscription()
    if not subscription:
        return False
    return subscription.plan_type in ['weekly', 'monthly', 'annual'] and subscription.is_active and not subscription.is_expired()

def user_has_admin_access(user):
    if not user:
        return False
    if user.is_admin:
        return True
    admin = User.query.filter_by(is_admin=True).first()
    if admin and admin.phone == user.phone:
        return True
    return False

def is_admin_worker(user):
    if not user or user.user_type != 'worker':
        return False
    return user_has_admin_access(user)

def get_excluded_admin_worker_ids():
    admin_users = User.query.filter((User.is_admin == True) | (User.admin_phone_verified == True)).all()
    return [user.id for user in admin_users]

def get_plans_for_user_type(user_type):
    """Get the appropriate plans based on user type"""
    if user_type == 'worker':
        return Config.WORKER_PLANS
    else:
        return Config.CUSTOMER_PLANS

def get_user_features(user):
    """Get feature access for user based on subscription and user type"""
    if not user:
        return Config.FREE_PLAN_LIMITS.get('workers', Config.FREE_PLAN_LIMITS['workers'])

    if user.is_admin:
        # Admin gets all features based on their type
        if user.user_type == 'worker':
            return Config.WORKER_PLANS['monthly']['features']
        else:
            return Config.CUSTOMER_PLANS['monthly']['features']

    subscription = user.get_active_subscription()

    # Check if user has active premium subscription
    if subscription and subscription.plan_type != 'free' and subscription.is_active and not subscription.is_expired():
        if user.user_type == 'worker':
            plan = Config.WORKER_PLANS.get(subscription.plan_type)
            if plan:
                return plan['features']
        else:
            plan = Config.CUSTOMER_PLANS.get(subscription.plan_type)
            if plan:
                return plan['features']

    # Return free plan limits based on user type
    return Config.FREE_PLAN_LIMITS.get(user.user_type, Config.FREE_PLAN_LIMITS['workers'])

def has_feature_access(user, feature_name):
    """Check if user has access to a specific premium feature"""
    if not user:
        return False
    if user.is_admin:
        return True
    features = get_user_features(user)
    return features.get(feature_name, False)

def get_remaining_job_posts(user):
    """Calculate remaining job posts for customer"""
    if not user or user.user_type != 'customer':
        return 0
    if user.is_admin:
        return 999
    features = get_user_features(user)
    max_posts = features.get('max_job_posts', 3)
    if max_posts >= 999:
        return 999
    current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    posts_this_month = JobPost.query.filter(
        JobPost.customer_id == user.id,
        JobPost.created_at >= current_month
    ).count()
    return max(0, max_posts - posts_this_month)

def get_remaining_applications(user):
    """Calculate remaining job applications for worker"""
    if not user or user.user_type != 'worker':
        return 0
    if user.is_admin:
        return 999
    features = get_user_features(user)
    max_apps = features.get('max_job_applications', 5)
    if max_apps >= 999:
        return 999
    current_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    apps_this_month = JobApplication.query.filter(
        JobApplication.worker_id == user.id,
        JobApplication.created_at >= current_month
    ).count()
    return max(0, max_apps - apps_this_month)

def can_post_job(user):
    """Check if user can post a job (customers only)"""
    if not user or user.user_type != 'customer':
        return False
    if user.is_admin:
        return True
    remaining = get_remaining_job_posts(user)
    return remaining > 0

def can_apply_job(user):
    """Check if user can apply to a job (workers only)"""
    if not user or user.user_type != 'worker':
        return False
    if user.is_admin:
        return True
    if user_has_premium(user):
        remaining = get_remaining_applications(user)
        return remaining > 0
    return False

def can_view_verification_details(user):
    """Check if user can view worker verification details"""
    if not user:
        return False
    if user.is_admin or user_has_admin_access(user):
        return True
    return has_feature_access(user, 'view_verification_details')

def can_see_verified_only(user):
    """Check if user can filter to see only verified workers"""
    if not user:
        return False
    if user.is_admin or user_has_admin_access(user):
        return True
    return has_feature_access(user, 'verified_workers_only')

def can_use_advanced_filters(user):
    """Check if user can use advanced search filters"""
    if not user:
        return False
    if user.is_admin or user_has_admin_access(user):
        return True
    return has_feature_access(user, 'advanced_filters')

def can_view_full_job_details(user, job):
    return True

def update_job_expiration():
    try:
        db_path = os.path.join(os.path.dirname(__file__), 'instance', 'fundiconnect.db')
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("UPDATE job_posts SET status = 'expired' WHERE deadline IS NOT NULL AND deadline <= datetime('now') AND status = 'open'")
            conn.commit()
            conn.close()
        return 0
    except Exception as e:
        logger.error(f"Update job expiration error: {e}")
        return 0

def format_phone(phone):
    if not phone:
        return ''
    phone = re.sub(r'\D', '', phone)
    if phone.startswith('0'):
        phone = '254' + phone[1:]
    if phone.startswith('+'):
        phone = phone[1:]
    if len(phone) > 12:
        phone = phone[:12]
    return phone

def generate_transaction_id(user_id):
    return f"FUNDI-{user_id}-{uuid.uuid4().hex[:12].upper()}"

def generate_tracking_id():
    return f"REP-{uuid.uuid4().hex[:8].upper()}-{datetime.utcnow().strftime('%Y%m')}"

def log_audit_event(user_id, action, details):
    try:
        audit = AuditLog(user_id=user_id, action=action, details=details, ip_address=request.remote_addr if hasattr(request, 'remote_addr') else None)
        db.session.add(audit)
        db.session.commit()
    except:
        db.session.rollback()

def validate_phone(phone):
    if not phone:
        return False
    pattern = r'^254[0-9]{9}$'
    return bool(re.match(pattern, phone))

def validate_password(password):
    if not password:
        return False
    return len(password) >= 6

def validate_email(email):
    if not email:
        return True
    pattern = r'^[^\s@]+@([^\s@]+\.)+[^\s@]+$'
    return bool(re.match(pattern, email))

def safe_division(numerator, denominator, default=0.0):
    try:
        if denominator == 0:
            return default
        return numerator / denominator
    except (TypeError, ZeroDivisionError):
        return default

# ==================== DECORATORS ====================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page.', 'warning')
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('login'))
        if not user_has_admin_access(user):
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

def feature_required(feature_name=None):
    """Decorator to check if user has access to a feature"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Please login to access this page.', 'warning')
                return redirect(url_for('login'))
            user = get_current_user()
            if not user:
                flash('User not found.', 'danger')
                return redirect(url_for('login'))
            if user.is_admin:
                return f(*args, **kwargs)
            if feature_name and not has_feature_access(user, feature_name):
                flash(f'This feature is not available on your current plan. Please upgrade to access it.', 'warning')
                return redirect(url_for('pricing'))
            if feature_name == 'max_job_posts' and user.user_type == 'customer':
                remaining = get_remaining_job_posts(user)
                if remaining <= 0:
                    flash(f'You have reached your job posting limit. Upgrade to premium to post more jobs.', 'warning')
                    return redirect(url_for('pricing'))
            if feature_name == 'max_job_applications' and user.user_type == 'worker':
                remaining = get_remaining_applications(user)
                if remaining <= 0:
                    flash(f'You have reached your application limit. Upgrade to premium to apply to more jobs.', 'warning')
                    return redirect(url_for('pricing'))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ==================== CONTEXT PROCESSORS ====================

@app.context_processor
def utility_processor():
    settings = load_settings()

    def get_worker_rating(worker_id):
        try:
            worker = WorkerProfile.query.filter_by(user_id=worker_id).first()
            if worker and worker.rating_score is not None:
                return float(worker.rating_score)
            return 0.0
        except:
            return 0.0

    def get_safe_rating(worker):
        try:
            if not worker:
                return 0.0
            return float(worker.rating_score) if worker.rating_score is not None else 0.0
        except:
            return 0.0

    def user_has_feature(feature_name):
        user = get_current_user()
        if not user:
            return False
        return has_feature_access(user, feature_name)

    def user_can_verify():
        user = get_current_user()
        return user_can_get_verified_badge(user)

    def remaining_job_posts():
        user = get_current_user()
        if not user:
            return 0
        return get_remaining_job_posts(user)

    def remaining_applications():
        user = get_current_user()
        if not user:
            return 0
        return get_remaining_applications(user)

    def is_premium_user():
        user = get_current_user()
        return user_has_premium(user)

    def can_see_admin_link():
        user = get_current_user()
        return user_has_admin_access(user)

    def is_admin_worker_check():
        user = get_current_user()
        return is_admin_worker(user)

    def can_view_verification():
        user = get_current_user()
        return can_view_verification_details(user)

    def can_view_full_details(job=None):
        return True

    def get_setting(key):
        return settings.get(key, '')

    def get_notifications():
        if session.get('has_admin_access'):
            return notification_manager.get_all_notifications()
        return []

    def get_unread_notification_count():
        if session.get('has_admin_access'):
            return notification_manager.get_unread_count()
        return 0

    def get_user_active_subscription():
        user = get_current_user()
        if user:
            return user.get_active_subscription()
        return None

    def get_subscription_expiry():
        sub = get_user_active_subscription()
        if sub and sub.expires_at:
            return sub.expires_at.strftime('%b %d, %Y')
        return None

    def get_subscription_days_remaining():
        sub = get_user_active_subscription()
        if sub and sub.expires_at:
            return sub.days_remaining()
        return None

    return dict(
        categories=CATEGORIES,
        WORKER_PLANS=Config.WORKER_PLANS,
        CUSTOMER_PLANS=Config.CUSTOMER_PLANS,
        FREE_PLAN_LIMITS=Config.FREE_PLAN_LIMITS,
        get_worker_rating=get_worker_rating,
        get_safe_rating=get_safe_rating,
        user_has_feature=user_has_feature,
        user_can_verify=user_can_verify,
        remaining_job_posts=remaining_job_posts,
        remaining_applications=remaining_applications,
        user_has_premium=is_premium_user,
        can_see_admin_link=can_see_admin_link,
        is_admin_worker=is_admin_worker_check,
        can_view_verification=can_view_verification,
        can_view_full_details=can_view_full_details,
        settings=settings,
        get_setting=get_setting,
        notifications=get_notifications,
        unread_notification_count=get_unread_notification_count,
        get_user_active_subscription=get_user_active_subscription,
        get_subscription_expiry=get_subscription_expiry,
        get_subscription_days_remaining=get_subscription_days_remaining
    )

# ==================== API ROUTES ====================

@app.route('/api/notifications')
@login_required
def api_notifications():
    user = get_current_user()
    if not user or not user_has_admin_access(user):
        return jsonify({'error': 'Unauthorized'}), 403
    return jsonify({'notifications': notification_manager.get_all_notifications(), 'unread_count': notification_manager.get_unread_count(), 'total_count': len(notification_manager.get_all_notifications())})

@app.route('/api/notifications/mark-read/<int:notification_id>', methods=['POST'])
@login_required
def api_mark_notification_read(notification_id):
    user = get_current_user()
    if not user or not user_has_admin_access(user):
        return jsonify({'error': 'Unauthorized'}), 403
    if notification_manager.mark_as_read(notification_id):
        return jsonify({'success': True, 'unread_count': notification_manager.get_unread_count()})
    return jsonify({'error': 'Notification not found'}), 404

@app.route('/api/notifications/mark-all-read', methods=['POST'])
@login_required
def api_mark_all_notifications_read():
    user = get_current_user()
    if not user or not user_has_admin_access(user):
        return jsonify({'error': 'Unauthorized'}), 403
    notification_manager.mark_all_as_read()
    return jsonify({'success': True, 'unread_count': notification_manager.get_unread_count()})

@app.route('/api/notifications/latest')
@login_required
def api_latest_notifications():
    user = get_current_user()
    if not user or not user_has_admin_access(user):
        return jsonify({'error': 'Unauthorized'}), 403
    latest = notification_manager.get_all_notifications()[:5]
    return jsonify({'notifications': latest, 'unread_count': notification_manager.get_unread_count(), 'timestamp': datetime.utcnow().isoformat()})

# ==================== EMAIL SUBSCRIPTION ROUTES ====================

@app.route('/subscribe-email', methods=['GET', 'POST'])
def subscribe_email():
    email = request.args.get('email') or request.form.get('email')
    user_id = request.args.get('user_id') or request.form.get('user_id')
    if not email:
        flash('Email address is required.', 'danger')
        return redirect(request.referrer or url_for('index'))
    try:
        existing = NewsletterSubscriber.query.filter_by(email=email).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.unsubscribed_at = None
                db.session.commit()
                flash('Successfully re-subscribed to updates!', 'success')
            else:
                flash('You are already subscribed to our updates.', 'info')
        else:
            subscriber = NewsletterSubscriber(email=email, user_id=int(user_id) if user_id else None, is_active=True)
            db.session.add(subscriber)
            db.session.commit()
            flash('Successfully subscribed to updates! Check your inbox for confirmation.', 'success')
        settings = load_settings()
        base_url = request.url_root.rstrip('/')
        user = User.query.get(user_id) if user_id else None
        context = {'user_name': user.name if user else email.split('@')[0], 'contact_email': settings.get('contact_email', 'support@fundiconnect.co.ke'), 'unsubscribe_url': f"{base_url}/unsubscribe?email={email}", 'preferences_url': f"{base_url}/email-preferences?email={email}"}
        send_email(email, "Subscription Confirmed - FundiConnect", "subscribe_confirmation.html", context)
    except Exception as e:
        db.session.rollback()
        logger.error(f"Subscribe email error: {e}")
        flash('Failed to subscribe. Please try again.', 'danger')
    return redirect(request.referrer or url_for('index'))

@app.route('/unsubscribe', methods=['GET', 'POST'])
def unsubscribe():
    email = request.args.get('email') or request.form.get('email')
    if not email:
        flash('Email address is required.', 'danger')
        return redirect(url_for('index'))
    try:
        subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
        if subscriber:
            subscriber.is_active = False
            subscriber.unsubscribed_at = datetime.utcnow()
            db.session.commit()
            flash('Successfully unsubscribed from updates.', 'info')
        else:
            flash('Email not found in our subscriber list.', 'warning')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unsubscribe error: {e}")
        flash('Failed to unsubscribe. Please try again.', 'danger')
    return redirect(url_for('index'))

@app.route('/email-preferences', methods=['GET', 'POST'])
def email_preferences():
    email = request.args.get('email') or request.form.get('email')
    if not email:
        flash('Email address is required.', 'danger')
        return redirect(url_for('index'))
    subscriber = NewsletterSubscriber.query.filter_by(email=email).first()
    if request.method == 'POST':
        try:
            if subscriber:
                subscriber.is_active = request.form.get('subscribe') == 'on'
                db.session.commit()
                flash('Email preferences updated successfully!', 'success')
            else:
                subscriber = NewsletterSubscriber(email=email, is_active=request.form.get('subscribe') == 'on')
                db.session.add(subscriber)
                db.session.commit()
                flash('Email preferences saved successfully!', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Update preferences error: {e}")
            flash('Failed to update preferences. Please try again.', 'danger')
    return render_template('email_preferences.html', subscriber=subscriber)

# ==================== PUBLIC ROUTES ====================

@app.route('/')
def index():
    try:
        excluded_ids = get_excluded_admin_worker_ids()
        featured_workers_query = WorkerProfile.query.filter_by(is_verified=True)
        if excluded_ids:
            featured_workers_query = featured_workers_query.filter(~WorkerProfile.user_id.in_(excluded_ids))
        featured_workers = featured_workers_query.limit(6).all()
        recent_jobs = JobPost.query.filter_by(status='open').order_by(JobPost.created_at.desc()).limit(6).all()
        avg_rating_result = db.session.query(db.func.avg(WorkerProfile.rating_score)).scalar()
        avg_rating = avg_rating_result if avg_rating_result is not None else 4.8
        workers_count_query = WorkerProfile.query
        if excluded_ids:
            workers_count_query = workers_count_query.filter(~WorkerProfile.user_id.in_(excluded_ids))
        workers_count = workers_count_query.count()
        featured_stories = SuccessStory.query.filter_by(is_approved=True, featured=True).order_by(SuccessStory.created_at.desc()).all()
        stats = {'workers': workers_count, 'jobs': JobPost.query.filter_by(status='open').count(), 'users': User.query.filter(User.user_type != 'admin').count(), 'rating': round(avg_rating, 1)}
        return render_template('index.html', featured_workers=featured_workers, recent_jobs=recent_jobs, stats=stats, featured_stories=featured_stories)
    except Exception as e:
        logger.error(f"Index error: {e}")
        return render_template('index.html', featured_workers=[], recent_jobs=[], stats={'workers':0, 'jobs':0, 'users':0, 'rating':4.8}, featured_stories=[])

@app.route('/pricing')
def pricing():
    user = get_current_user()
    current_subscription = user.get_active_subscription() if user else None
    return render_template('pricing.html', current_subscription=current_subscription)

# ==================== MAIN SUBSCRIPTION ROUTE ====================

@app.route('/subscribe', methods=['GET', 'POST'])
@login_required
def subscribe():
    """Main subscription page - handles both GET and POST for workers and customers"""
    user = get_current_user()

    # Determine which plans to show based on user type
    if user.user_type == 'worker':
        plans = Config.WORKER_PLANS
    else:
        plans = Config.CUSTOMER_PLANS

    if request.method == 'POST':
        try:
            plan = request.form.get('plan')
            if plan not in plans:
                flash('Invalid plan selected.', 'danger')
                return redirect(url_for('subscribe'))
            plan_config = plans[plan]
            price = plan_config['price']
            days = plan_config['duration_days']
            tx_id = generate_transaction_id(user.id)

            # Create payment record
            payment = Payment(
                user_id=user.id,
                amount=price,
                plan_type=plan,
                mpesa_transaction_id=tx_id,
                mpesa_phone=user.phone,
                status='pending',
                payment_method='mpesa'
            )
            db.session.add(payment)
            db.session.flush()

            # Create subscription record (inactive until payment verified)
            subscription = Subscription(
                user_id=user.id,
                plan_type=plan,
                amount_paid=price,
                transaction_id=tx_id,
                payment_status='pending',
                is_active=False,
                expires_at=datetime.utcnow() + timedelta(days=days)
            )
            db.session.add(subscription)
            db.session.flush()

            payment.subscription_id = subscription.id
            db.session.commit()

            log_audit_event(user.id, 'subscribe', f'Subscription initiated: {plan} plan')
            notify_user_activity(user, 'subscription', plan_config['name'])

            # Notify admin about new subscription request
            notify_admin(
                title='💎 New Subscription Request',
                message=f'{user.name} ({user.user_type}) has requested {plan_config["name"]} subscription. Payment pending verification.',
                type='warning',
                user_id=user.id,
                user_name=user.name
            )

            return render_template('payment_instructions.html',
                                user=user,
                                plan=plan,
                                price=price,
                                transaction_id=tx_id)
        except Exception as e:
            db.session.rollback()
            logger.error(f"Subscribe error: {e}")
            flash('Failed to initiate subscription. Please try again.', 'danger')
            return redirect(url_for('subscribe'))

    current_subscription = user.get_active_subscription()
    return render_template('subscribe.html',
                         user=user,
                         current_subscription=current_subscription,
                         plans=plans)

@app.route('/submit-payment-proof', methods=['POST'])
@login_required
def submit_payment_proof():
    user = get_current_user()
    tx_id = request.form.get('transaction_id')
    receipt = request.form.get('mpesa_receipt_number')
    screenshot = request.files.get('mpesa_screenshot')
    payment = Payment.query.filter_by(mpesa_transaction_id=tx_id, user_id=user.id).first()
    if not payment:
        flash('Invalid transaction.', 'danger')
        return redirect(url_for('subscribe'))
    try:
        path = None
        if screenshot and screenshot.filename:
            filename = secure_filename(f"payment_{user.id}_{uuid.uuid4().hex}_{screenshot.filename}")
            screenshot.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            path = filename
        payment.mpesa_receipt_number = receipt
        payment.screenshot_path = path
        payment.status = 'pending_verification'
        db.session.commit()
        log_audit_event(user.id, 'submit_payment', f'Payment proof submitted for {tx_id}')
        notify_user_activity(user, 'payment')

        # Notify admin about payment proof
        notify_admin(
            title='📸 Payment Proof Submitted',
            message=f'{user.name} has submitted payment proof for {payment.plan_type} subscription. Please verify.',
            type='warning',
            user_id=user.id,
            user_name=user.name
        )

        flash('Payment proof submitted! Admin will verify within 24 hours.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Submit payment proof error: {e}")
        flash('Failed to submit payment proof. Please try again.', 'danger')
    return redirect(url_for('dashboard'))

# ==================== WORKER ROUTES ====================

@app.route('/workers')
def workers():
    try:
        skill = request.args.get('skill', '')
        location = request.args.get('location', '')
        category = request.args.get('category', '')
        verified_only = request.args.get('verified', 'false') == 'true'
        min_rating = request.args.get('min_rating', 0, type=float)
        sort_by = request.args.get('sort', 'rating')
        query = WorkerProfile.query
        excluded_ids = get_excluded_admin_worker_ids()
        if excluded_ids:
            query = query.filter(~WorkerProfile.user_id.in_(excluded_ids))
        if skill:
            query = query.filter(WorkerProfile.skills.ilike(f'%{skill}%'))
        if location:
            query = query.filter(WorkerProfile.location.ilike(f'%{location}%'))
        if category:
            query = query.filter((WorkerProfile.primary_category == category) | (WorkerProfile.secondary_categories.ilike(f'%{category}%')))

        current_user = get_current_user()
        if verified_only and current_user and can_see_verified_only(current_user):
            query = query.filter(WorkerProfile.is_verified == True)
        elif verified_only:
            flash('Verified workers filter is only available for premium customers. Upgrade to access this feature.', 'info')

        if min_rating > 0:
            query = query.filter(WorkerProfile.rating_score >= min_rating)
        if sort_by == 'rating':
            query = query.order_by(WorkerProfile.rating_score.desc())
        elif sort_by == 'experience':
            query = query.order_by(WorkerProfile.years_experience.desc())
        elif sort_by == 'jobs':
            query = query.order_by(WorkerProfile.total_jobs_completed.desc())
        elif sort_by == 'rate':
            query = query.order_by(WorkerProfile.hourly_rate.asc())
        workers_list = query.all()
        return render_template('workers.html', workers=workers_list, can_use_advanced_filters=can_use_advanced_filters(current_user))
    except Exception as e:
        logger.error(f"Workers error: {e}")
        flash('Unable to load workers. Please try again.', 'danger')
        return render_template('workers.html', workers=[], can_use_advanced_filters=False)

# ==================== FIXED WORKER PROFILE ROUTE ====================
@app.route('/worker/<int:worker_id>')
def worker_profile(worker_id):
    try:
        worker = WorkerProfile.query.filter_by(user_id=worker_id).first()
        if not worker:
            flash('Worker profile not found.', 'danger')
            return redirect(url_for('workers'))
        if worker.user.is_admin or worker.user.admin_phone_verified:
            current_user = get_current_user()
            if not current_user or not user_has_admin_access(current_user):
                flash('Worker profile not found.', 'danger')
                return redirect(url_for('workers'))

        # Parse certifications if they exist
        certifications_list = []
        if worker.certifications and worker.certifications != '[]' and worker.certifications != 'null':
            try:
                certifications_list = json.loads(worker.certifications)
                logger.info(f"Loaded {len(certifications_list)} certifications for worker {worker.user.name}")
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing certifications for worker {worker.user.name}: {e}")
                certifications_list = []

        # Ensure social links are not None (convert None to empty string for template)
        if worker.whatsapp is None:
            worker.whatsapp = ''
        if worker.facebook is None:
            worker.facebook = ''
        if worker.instagram is None:
            worker.instagram = ''
        if worker.twitter is None:
            worker.twitter = ''
        if worker.linkedin is None:
            worker.linkedin = ''
        if worker.website is None:
            worker.website = ''

        reviews = Review.query.filter_by(worker_id=worker.user_id).order_by(Review.created_at.desc()).all()
        avg_rating = 0
        if reviews and len(reviews) > 0:
            total_rating = sum(r.rating for r in reviews)
            avg_rating = safe_division(total_rating, len(reviews), 0.0)
        else:
            avg_rating = worker.rating_score if worker.rating_score is not None else 0.0
        can_see_verification = can_view_verification_details(get_current_user())

        # Log social links for debugging
        logger.info(f"Worker {worker.user.name} social links - WhatsApp: '{worker.whatsapp}', Facebook: '{worker.facebook}', Instagram: '{worker.instagram}'")

        return render_template('worker_profile.html',
                             worker=worker,
                             categories=CATEGORIES,
                             reviews=reviews,
                             avg_rating=avg_rating,
                             can_see_verification=can_see_verification,
                             certifications_list=certifications_list)
    except Exception as e:
        logger.error(f"Worker profile error: {e}")
        logger.error(traceback.format_exc())
        flash('Unable to load worker profile. Please try again.', 'danger')
        return redirect(url_for('workers'))

# ==================== JOB ROUTES ====================

@app.route('/jobs')
def browse_jobs():
    try:
        update_job_expiration()
        skill = request.args.get('skill', '').strip()
        location = request.args.get('location', '').strip()
        category = request.args.get('category', '').strip()
        min_budget = request.args.get('min_budget', type=float)
        max_budget = request.args.get('max_budget', type=float)
        posted_within = request.args.get('posted_within', type=int)
        job_status = request.args.get('job_status', '')
        sort_by = request.args.get('sort', 'newest')

        current_user = get_current_user()
        can_use_advanced = can_use_advanced_filters(current_user)

        try:
            if job_status:
                all_jobs = JobPost.query.filter_by(status=job_status).all()
            else:
                all_jobs = JobPost.query.filter_by(status='open').all()
        except Exception as e:
            logger.error(f"Error fetching jobs: {e}")
            all_jobs = []

        filtered_jobs = []
        for job in all_jobs:
            include = True
            if skill and include:
                job_title = job.title.lower() if job.title else ''
                job_desc = job.description.lower() if job.description else ''
                if skill.lower() not in job_title and skill.lower() not in job_desc:
                    include = False
            if location and include:
                job_location = job.location.lower() if job.location else ''
                if location.lower() not in job_location:
                    include = False
            if category and include:
                try:
                    job_category = getattr(job, 'category', 'general')
                    if job_category != category:
                        include = False
                except:
                    pass
            if can_use_advanced:
                if min_budget and include:
                    try:
                        job_budget_max = getattr(job, 'budget_max', None)
                        if job_budget_max is None or job_budget_max < min_budget:
                            include = False
                    except:
                        pass
                if max_budget and include:
                    try:
                        job_budget_min = getattr(job, 'budget_min', None)
                        if job_budget_min is None or job_budget_min > max_budget:
                            include = False
                    except:
                        pass
                if posted_within and include:
                    try:
                        cutoff_date = datetime.utcnow() - timedelta(days=posted_within)
                        if job.created_at < cutoff_date:
                            include = False
                    except:
                        pass
            if include:
                filtered_jobs.append(job)

        try:
            if sort_by == 'newest':
                filtered_jobs.sort(key=lambda x: x.created_at, reverse=True)
            elif sort_by == 'budget_high':
                filtered_jobs.sort(key=lambda x: getattr(x, 'budget_max', 0) or 0, reverse=True)
            elif sort_by == 'budget_low':
                filtered_jobs.sort(key=lambda x: getattr(x, 'budget_min', 0) or 0)
            elif sort_by == 'deadline':
                filtered_jobs.sort(key=lambda x: getattr(x, 'deadline', datetime.max) or datetime.max)
        except Exception as e:
            logger.error(f"Error sorting jobs: {e}")

        try:
            expired_count = JobPost.query.filter_by(status='expired').count()
        except:
            expired_count = 0

        return render_template('browse_jobs.html', jobs=filtered_jobs, expired_count=expired_count, can_use_advanced_filters=can_use_advanced)
    except Exception as e:
        logger.error(f"Browse jobs critical error: {e}")
        logger.error(traceback.format_exc())
        flash('Unable to load jobs. Please try again.', 'danger')
        return render_template('browse_jobs.html', jobs=[], expired_count=0, can_use_advanced_filters=False)

@app.route('/job/<int:job_id>')
def job_detail(job_id):
    try:
        job = JobPost.query.get(job_id)
        if not job:
            flash('Job not found.', 'danger')
            return redirect(url_for('browse_jobs'))
        try:
            applications = JobApplication.query.filter_by(job_id=job_id).all()
        except Exception as e:
            logger.error(f"Error fetching applications for job {job_id}: {e}")
            applications = []
        current_user = get_current_user()
        can_view_full = True
        if job.status != 'open':
            if not current_user or (current_user.id != job.customer_id and not user_has_admin_access(current_user)):
                flash('This job is no longer accepting applications, but you can still view the details.', 'info')
        return render_template('job_detail.html', job=job, applications=applications, can_view_full=can_view_full, current_user=current_user)
    except Exception as e:
        logger.error(f"Job detail error for job {job_id}: {e}")
        logger.error(traceback.format_exc())
        flash('Unable to load job details. Please try again.', 'danger')
        return redirect(url_for('browse_jobs'))

# ==================== FIXED POST JOB ROUTE ====================
@app.route('/post-job', methods=['GET', 'POST'])
@login_required
@feature_required('max_job_posts')
def post_job():
    user = get_current_user()
    if user.user_type != 'customer' and not user_has_admin_access(user):
        flash('Only customers can post jobs.', 'danger')
        return redirect(url_for('dashboard'))
    if not user_has_admin_access(user) and not can_post_job(user):
        flash('You have reached your job posting limit. Upgrade to premium to post more jobs.', 'warning')
        return redirect(url_for('pricing'))

    if request.method == 'POST':
        try:
            # Get form data
            title = request.form.get('title')
            description = request.form.get('description')
            location = request.form.get('location')
            budget_min = request.form.get('budget_min')
            budget_max = request.form.get('budget_max')
            deadline_str = request.form.get('deadline')
            category = request.form.get('job_category', 'general')
            skills_required = request.form.get('skills_required', '')

            # Validate required fields
            if not title or not title.strip():
                flash('Job title is required.', 'danger')
                return redirect(url_for('post_job'))

            if not description or not description.strip():
                flash('Job description is required.', 'danger')
                return redirect(url_for('post_job'))

            # Parse deadline
            deadline = None
            if deadline_str:
                try:
                    deadline = datetime.strptime(deadline_str, '%Y-%m-%d')
                except ValueError:
                    flash('Invalid deadline format.', 'danger')
                    return redirect(url_for('post_job'))

            # Parse budgets
            budget_min_val = None
            if budget_min and budget_min.strip():
                try:
                    budget_min_val = float(budget_min)
                    if budget_min_val < 0:
                        flash('Budget cannot be negative.', 'danger')
                        return redirect(url_for('post_job'))
                except ValueError:
                    flash('Invalid minimum budget amount.', 'danger')
                    return redirect(url_for('post_job'))

            budget_max_val = None
            if budget_max and budget_max.strip():
                try:
                    budget_max_val = float(budget_max)
                    if budget_max_val < 0:
                        flash('Budget cannot be negative.', 'danger')
                        return redirect(url_for('post_job'))
                except ValueError:
                    flash('Invalid maximum budget amount.', 'danger')
                    return redirect(url_for('post_job'))

            # Validate budget range
            if budget_min_val and budget_max_val and budget_min_val > budget_max_val:
                flash('Minimum budget cannot be greater than maximum budget.', 'danger')
                return redirect(url_for('post_job'))

            # Create job post (without template_used - it's not in the JobPost model)
            job = JobPost(
                customer_id=user.id,
                title=title.strip(),
                description=description.strip(),
                location=location.strip() if location else None,
                budget_min=budget_min_val,
                budget_max=budget_max_val,
                deadline=deadline,
                category=category,
                skills_required=skills_required.strip() if skills_required else None,
                status='open'
            )
            db.session.add(job)
            db.session.commit()

            log_audit_event(user.id, 'post_job', f'Job posted: {job.title}')
            notify_user_activity(user, 'job_post', job.title)
            flash('Job posted successfully!', 'success')
            return redirect(url_for('customer_dashboard'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Post job error: {e}")
            logger.error(traceback.format_exc())
            flash(f'Failed to post job. Please try again. Error: {str(e)}', 'danger')
            return redirect(url_for('post_job'))

    return render_template('post_job.html', user=user)

@app.route('/apply-job/<int:job_id>', methods=['POST'])
@login_required
def apply_job(job_id):
    user = get_current_user()
    if user.user_type != 'worker' and not user_has_admin_access(user):
        flash('Only workers can apply to jobs.', 'danger')
        return redirect(url_for('dashboard'))
    if not user_has_admin_access(user):
        if not user_has_premium(user):
            flash('You need an active premium subscription to apply for jobs. Please upgrade to continue.', 'warning')
            return redirect(url_for('pricing'))
        if not can_apply_job(user):
            flash('You have reached your application limit for this month. Upgrade your plan to apply for more jobs.', 'warning')
            return redirect(url_for('pricing'))
    try:
        job = JobPost.query.get_or_404(job_id)
        if not job.can_apply():
            flash('This job is no longer accepting applications.', 'danger')
            return redirect(url_for('job_detail', job_id=job_id))
        existing = JobApplication.query.filter_by(job_id=job_id, worker_id=user.id).first()
        if existing:
            flash('You have already applied for this job.', 'warning')
            return redirect(url_for('job_detail', job_id=job_id))
        application = JobApplication(job_id=job_id, worker_id=user.id, bid_amount=float(request.form.get('bid_amount', 0)) if request.form.get('bid_amount') else None, message=request.form.get('message', ''), status='pending')
        db.session.add(application)
        db.session.commit()
        log_audit_event(user.id, 'apply_job', f'Applied to job: {job.title}')
        notify_user_activity(user, 'application')
        flash('Application submitted successfully!', 'success')
        return redirect(url_for('job_detail', job_id=job_id))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Apply job error: {e}")
        flash('Failed to submit application. Please try again.', 'danger')
        return redirect(url_for('job_detail', job_id=job_id))

@app.route('/update-application/<int:app_id>', methods=['POST'])
@login_required
def update_application(app_id):
    user = get_current_user()
    application = JobApplication.query.get_or_404(app_id)
    job = JobPost.query.get(application.job_id)
    if job.customer_id != user.id and not user_has_admin_access(user):
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('dashboard'))
    status = request.form.get('status')
    if status in ['accepted', 'rejected']:
        application.status = status
        if status == 'accepted':
            job.status = 'in_progress'
        db.session.commit()
        log_audit_event(user.id, 'update_application', f'Application {app_id} {status}')
        flash(f'Application {status}ed successfully.', 'success')
    return redirect(url_for('job_detail', job_id=job.id))

@app.route('/complete-job/<int:job_id>', methods=['POST'])
@login_required
def complete_job(job_id):
    user = get_current_user()
    job = JobPost.query.get_or_404(job_id)
    if job.customer_id != user.id and not user_has_admin_access(user):
        flash('Unauthorized action.', 'danger')
        return redirect(url_for('dashboard'))
    job.status = 'completed'
    accepted = JobApplication.query.filter_by(job_id=job_id, status='accepted').first()
    if accepted:
        worker = WorkerProfile.query.filter_by(user_id=accepted.worker_id).first()
        if worker:
            worker.total_jobs_completed += 1
            worker.update_rating()
    db.session.commit()
    log_audit_event(user.id, 'complete_job', f'Job completed: {job.title}')
    flash('Job marked as completed!', 'success')
    return redirect(url_for('dashboard'))

# ==================== REVIEW ROUTES ====================

@app.route('/leave-review/<int:worker_id>', methods=['POST'])
@login_required
def leave_review(worker_id):
    user = get_current_user()
    if user.user_type != 'customer' and not user_has_admin_access(user):
        flash('Only customers can leave reviews.', 'danger')
        return redirect(url_for('index'))
    rating = int(request.form.get('rating'))
    comment = request.form.get('comment')
    if rating < 1 or rating > 5:
        flash('Invalid rating.', 'danger')
        return redirect(url_for('worker_profile', worker_id=worker_id))
    try:
        review = Review(worker_id=worker_id, customer_id=user.id, rating=rating, comment=comment)
        db.session.add(review)
        db.session.commit()
        worker = WorkerProfile.query.filter_by(user_id=worker_id).first()
        if worker:
            worker.update_rating()
        log_audit_event(user.id, 'leave_review', f'Review left for worker {worker_id}')
        notify_user_activity(user, 'review')
        flash('Review submitted! Thank you for your feedback.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Leave review error: {e}")
        flash('Failed to submit review. Please try again.', 'danger')
    return redirect(url_for('worker_profile', worker_id=worker_id))

# ==================== PROFILE ROUTES ====================
@app.route('/profile/edit', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = get_current_user()

    # IMPORTANT: Load worker profile for the GET request
    worker = None
    if user.user_type == 'worker':
        worker = WorkerProfile.query.filter_by(user_id=user.id).first()
        if not worker:
            worker = WorkerProfile(user_id=user.id)
            db.session.add(worker)
            db.session.commit()
        # Refresh to ensure we have the latest data from database
        db.session.refresh(worker)

        # DEBUG: Log current values
        logger.info(f"Loaded worker profile for user {user.id}:")
        logger.info(f"  - certifications: {worker.certifications}")
        logger.info(f"  - whatsapp: {worker.whatsapp}")
        logger.info(f"  - facebook: {worker.facebook}")
        logger.info(f"  - instagram: {worker.instagram}")

        # Ensure certifications is properly initialized
        if worker.certifications is None:
            worker.certifications = '[]'
            db.session.commit()

    if request.method == 'POST':
        try:
            # Basic user info
            user.name = request.form.get('name')
            user.email = request.form.get('email')

            # Handle profile picture
            if 'profile_picture' in request.files:
                file = request.files['profile_picture']
                if file and file.filename:
                    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                    filename = secure_filename(f"profile_{user.id}_{uuid.uuid4().hex}.{ext}")
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                    if user.profile_picture and user.profile_picture != 'default-avatar.png':
                        old = os.path.join(app.config['UPLOAD_FOLDER'], user.profile_picture)
                        if os.path.exists(old):
                            os.remove(old)
                    user.profile_picture = filename

                    # Update profile picture in success stories
                    approved_stories = SuccessStory.query.filter_by(user_id=user.id, is_approved=True).all()
                    for story in approved_stories:
                        story.profile_picture_cache = user.profile_picture
                    db.session.commit()

            # Handle worker-specific fields
            if user.user_type == 'worker':
                worker = WorkerProfile.query.filter_by(user_id=user.id).first()
                if not worker:
                    worker = WorkerProfile(user_id=user.id)
                    db.session.add(worker)

                # Basic worker info
                worker.business_name = request.form.get('business_name', user.name)
                worker.location = request.form.get('location')
                worker.primary_category = request.form.get('primary_category', 'general')
                worker.secondary_categories = request.form.get('secondary_categories', '')
                worker.skills = request.form.get('skills')
                worker.description = request.form.get('description')
                worker.hourly_rate = float(request.form.get('hourly_rate')) if request.form.get('hourly_rate') else None
                worker.years_experience = int(request.form.get('years_experience', 0))
                worker.is_available = request.form.get('is_available') == 'on'
                worker.response_time_avg = int(request.form.get('response_time', 60))

                # Handle cover image
                if 'cover_image' in request.files:
                    file = request.files['cover_image']
                    if file and file.filename:
                        ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                        filename = secure_filename(f"cover_{user.id}_{uuid.uuid4().hex}.{ext}")
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        if worker.cover_image and worker.cover_image != 'default-cover.jpg':
                            old = os.path.join(app.config['UPLOAD_FOLDER'], worker.cover_image)
                            if os.path.exists(old):
                                os.remove(old)
                        worker.cover_image = filename

                # PREMIUM FEATURES - Only for premium users
                if user_has_premium(user):
                    # Handle portfolio images
                    portfolio_images_list = []
                    if worker.portfolio_images:
                        portfolio_images_list = worker.portfolio_images.split(',')

                    # Handle removed images
                    removed_images = request.form.getlist('removed_portfolio_images')
                    for img in removed_images:
                        if img in portfolio_images_list:
                            portfolio_images_list.remove(img)
                            img_path = os.path.join(app.config['UPLOAD_FOLDER'], img)
                            if os.path.exists(img_path):
                                os.remove(img_path)

                    # Handle new portfolio uploads
                    if 'portfolio_images' in request.files:
                        files = request.files.getlist('portfolio_images')
                        for file in files:
                            if file and file.filename:
                                if file.filename and file.filename.strip():
                                    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                                    filename = secure_filename(f"portfolio_{user.id}_{uuid.uuid4().hex}.{ext}")
                                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                                    portfolio_images_list.append(filename)

                    # Also check for individual portfolio_* fields (backward compatibility)
                    for key in request.files:
                        if key.startswith('portfolio_') and key != 'portfolio_images':
                            file = request.files[key]
                            if file and file.filename:
                                ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
                                filename = secure_filename(f"portfolio_{user.id}_{uuid.uuid4().hex}.{ext}")
                                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                                portfolio_images_list.append(filename)

                    # Limit to 5 images
                    portfolio_images_list = portfolio_images_list[:5]
                    worker.portfolio_images = ','.join(portfolio_images_list) if portfolio_images_list else None

                    # Handle certifications
                    certifications_data = request.form.get('certifications_data', '[]')
                    logger.info(f"Received certifications_data: {certifications_data}")

                    try:
                        certifications = json.loads(certifications_data)
                        if certifications and len(certifications) > 0:
                            worker.certifications = json.dumps(certifications)
                            logger.info(f"Saved {len(certifications)} certifications for user {user.id}")
                        else:
                            worker.certifications = '[]'
                            logger.info(f"Cleared certifications for user {user.id}")
                    except json.JSONDecodeError as e:
                        logger.error(f"Error parsing certifications data: {e}, data: {certifications_data}")
                        worker.certifications = '[]'
                    except Exception as e:
                        logger.error(f"Unexpected error saving certifications: {e}")
                        worker.certifications = '[]'

                    # Handle social links
                    worker.whatsapp = request.form.get('whatsapp', '').strip() or None
                    worker.facebook = request.form.get('facebook', '').strip() or None
                    worker.instagram = request.form.get('instagram', '').strip() or None
                    worker.twitter = request.form.get('twitter', '').strip() or None
                    worker.linkedin = request.form.get('linkedin', '').strip() or None
                    worker.website = request.form.get('website', '').strip() or None

                    logger.info(f"Saved social links for user {user.id}: WhatsApp={worker.whatsapp}, Facebook={worker.facebook}, Instagram={worker.instagram}")

                db.session.commit()
                logger.info(f"Successfully committed profile changes for user {user.id}")

            # ==================== CUSTOMER PREMIUM FEATURES SECTION (FIXED) ====================
            # Handle customer-specific fields
            if user.user_type == 'customer':
                # Get the subscription to check if premium
                subscription = user.get_active_subscription()
                is_premium_customer = subscription and subscription.plan_type in ['weekly', 'monthly', 'annual'] and subscription.is_active and not subscription.is_expired()

                # Log the incoming form data for debugging
                logger.info(f"Customer {user.id} form data - company_name: {request.form.get('company_name', '')}")
                logger.info(f"Customer {user.id} form data - business_location: {request.form.get('business_location', '')}")
                logger.info(f"Customer {user.id} form data - company_description: {request.form.get('company_description', '')}")
                logger.info(f"Customer {user.id} form data - preferred_categories: {request.form.get('preferred_categories', '')}")
                logger.info(f"Customer {user.id} form data - budget_range: {request.form.get('budget_range', '')}")
                logger.info(f"Customer {user.id} form data - verified_only: {request.form.get('verified_only')}")
                logger.info(f"Customer {user.id} form data - priority_listing: {request.form.get('priority_listing')}")
                logger.info(f"Customer {user.id} - is_premium_customer: {is_premium_customer}, plan: {subscription.plan_type if subscription else 'no subscription'}")

                # Always save company name and location (basic info for all customers)
                user.company_name = request.form.get('company_name', '').strip() or None
                user.business_location = request.form.get('business_location', '').strip() or None

                # Get premium field values from form
                company_description = request.form.get('company_description', '').strip()
                preferred_categories = request.form.get('preferred_categories', '').strip()
                budget_range = request.form.get('budget_range', '').strip()
                verified_only = request.form.get('verified_only') == 'on'
                priority_listing = request.form.get('priority_listing') == 'on'

                # Log what we're about to save
                logger.info(f"Customer {user.id} - About to save premium fields:")
                logger.info(f"  - company_description: '{company_description}' (empty? {not company_description})")
                logger.info(f"  - preferred_categories: '{preferred_categories}'")
                logger.info(f"  - budget_range: '{budget_range}'")
                logger.info(f"  - verified_only: {verified_only}")
                logger.info(f"  - priority_listing: {priority_listing}")

                # Only save premium fields if user has premium subscription
                if is_premium_customer:
                    user.company_description = company_description if company_description else None
                    user.preferred_categories = preferred_categories if preferred_categories else None
                    user.budget_range = budget_range if budget_range else None
                    user.verified_only = verified_only
                    user.priority_listing = priority_listing

                    logger.info(f"✅ SAVED premium customer fields for user {user.id}:")
                    logger.info(f"   - company_description: {user.company_description}")
                    logger.info(f"   - preferred_categories: {user.preferred_categories}")
                    logger.info(f"   - budget_range: {user.budget_range}")
                    logger.info(f"   - verified_only: {user.verified_only}")
                    logger.info(f"   - priority_listing: {user.priority_listing}")
                else:
                    # Clear premium fields for non-premium customers (free or daily plan)
                    user.company_description = None
                    user.preferred_categories = None
                    user.budget_range = None
                    user.verified_only = False
                    user.priority_listing = False

                    logger.info(f"Cleared premium fields for non-premium customer {user.id}")

            db.session.commit()
            log_audit_event(user.id, 'edit_profile', 'Profile updated')
            flash('Profile updated successfully!', 'success')

            # Return JSON response for AJAX requests
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': True, 'message': 'Profile updated successfully!', 'redirect': url_for('dashboard')})

            return redirect(url_for('dashboard'))

        except Exception as e:
            db.session.rollback()
            logger.error(f"Edit profile error: {e}")
            logger.error(traceback.format_exc())
            flash('Failed to update profile. Please try again.', 'danger')

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': str(e)}), 500

            return redirect(url_for('edit_profile'))

    # For GET request - pass both user and worker to the template
    return render_template('edit_profile.html', user=user, worker=worker)


@app.route('/verify', methods=['GET', 'POST'])
@login_required
def verify():
    user = get_current_user()
    if user.user_type != 'worker' and not user_has_admin_access(user):
        flash('Only workers can request verification.', 'danger')
        return redirect(url_for('dashboard'))
    if not user_can_get_verified_badge(user) and not user_has_admin_access(user):
        subscription = user.get_active_subscription()
        if subscription and subscription.plan_type == 'daily':
            flash('The Daily plan does NOT include verification. Please upgrade to Weekly, Monthly, or Annual plan to apply for verification.', 'warning')
        else:
            flash('Verification is only available for Weekly, Monthly, and Annual premium plans. Upgrade to get verified.', 'warning')
        return redirect(url_for('pricing'))
    if request.method == 'POST':
        try:
            verification_type = request.form.get('verification_type')
            file = request.files.get('evidence')
            path = None
            if file and file.filename:
                filename = secure_filename(f"verification_{user.id}_{uuid.uuid4().hex}_{file.filename}")
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                path = filename
            verification = VerificationRequest(worker_id=user.id, verification_type=verification_type, evidence_path=path, status='pending')
            db.session.add(verification)
            db.session.commit()
            log_audit_event(user.id, 'verify', f'Verification request submitted: {verification_type}')
            notify_user_activity(user, 'verification')
            flash('Verification request submitted! Our team will review within 48 hours.', 'success')
            return redirect(url_for('dashboard'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Verify error: {e}")
            flash('Failed to submit verification request. Please try again.', 'danger')
    return render_template('verify.html', user=user)

# ==================== DASHBOARD ROUTES ====================

@app.route('/worker-dashboard')
@login_required
def worker_dashboard():
    try:
        user = get_current_user()
        if not user:
            session.clear()
            flash('Session expired. Please login again.', 'warning')
            return redirect(url_for('login'))
        if user.user_type != 'worker' and not user_has_admin_access(user):
            flash('Access denied. Worker dashboard only.', 'danger')
            return redirect(url_for('index'))
        worker = WorkerProfile.query.filter_by(user_id=user.id).first()
        if not worker:
            worker = WorkerProfile(user_id=user.id, business_name=user.name, is_available=True, rating_score=0.0, rating_count=0)
            db.session.add(worker)
            db.session.commit()
        applications = JobApplication.query.filter_by(worker_id=user.id).order_by(JobApplication.created_at.desc()).all()
        reviews = Review.query.filter_by(worker_id=user.id).order_by(Review.created_at.desc()).all()
        subscription = user.get_active_subscription()
        features = get_user_features(user)
        remaining_apps = get_remaining_applications(user)
        has_premium = user_has_premium(user)
        has_admin_access = user_has_admin_access(user)

        # Calculate application stats
        pending_apps = len([a for a in applications if a.status == 'pending'])
        accepted_apps = len([a for a in applications if a.status == 'accepted'])
        rejected_apps = len([a for a in applications if a.status == 'rejected'])

        # Check expiry warning
        expiry_warning = False
        if subscription and subscription.plan_type != 'free' and subscription.expires_at:
            days_left = subscription.days_remaining()
            if days_left <= 3:
                expiry_warning = True

        return render_template('dashboard.html',
                             user=user,
                             worker=worker,
                             applications=applications,
                             reviews=reviews,
                             subscription=subscription,
                             features=features,
                             remaining_apps=remaining_apps,
                             has_premium=has_premium,
                             has_admin_access=has_admin_access,
                             pending_apps=pending_apps,
                             accepted_apps=accepted_apps,
                             rejected_apps=rejected_apps,
                             expiry_warning=expiry_warning)
    except Exception as e:
        logger.error(f"Worker dashboard error: {e}")
        logger.error(traceback.format_exc())
        flash('Unable to load dashboard. Please try again.', 'danger')
        return redirect(url_for('index'))

@app.route('/customer-dashboard')
@login_required
def customer_dashboard():
    try:
        user = get_current_user()
        if not user:
            session.clear()
            flash('Session expired. Please login again.', 'warning')
            return redirect(url_for('login'))
        if user.user_type != 'customer' and not user_has_admin_access(user):
            flash('Access denied. Customer dashboard only.', 'danger')
            return redirect(url_for('index'))
        jobs = JobPost.query.filter_by(customer_id=user.id).order_by(JobPost.created_at.desc()).all()
        applications_received = JobApplication.query.join(JobPost).filter(JobPost.customer_id == user.id).all()
        subscription = user.get_active_subscription()
        features = get_user_features(user)
        remaining_posts = get_remaining_job_posts(user)
        has_premium = user_has_premium(user)
        has_admin_access = user_has_admin_access(user)

        # Calculate job stats
        open_jobs = len([j for j in jobs if j.status == 'open'])
        in_progress_jobs = len([j for j in jobs if j.status == 'in_progress'])
        completed_jobs = len([j for j in jobs if j.status == 'completed'])
        pending_apps = len([a for a in applications_received if a.status == 'pending'])

        # Check expiry warning
        expiry_warning = False
        if subscription and subscription.plan_type != 'free' and subscription.expires_at:
            days_left = subscription.days_remaining()
            if days_left <= 3:
                expiry_warning = True

        return render_template('customer_dashboard.html',
                             user=user,
                             jobs=jobs,
                             applications_received=applications_received,
                             subscription=subscription,
                             features=features,
                             remaining_posts=remaining_posts,
                             has_premium=has_premium,
                             has_admin_access=has_admin_access,
                             open_jobs=open_jobs,
                             in_progress_jobs=in_progress_jobs,
                             completed_jobs=completed_jobs,
                             pending_apps=pending_apps,
                             expiry_warning=expiry_warning)
    except Exception as e:
        logger.error(f"Customer dashboard error: {e}")
        logger.error(traceback.format_exc())
        flash('Unable to load dashboard. Please try again.', 'danger')
        return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_current_user()
    if not user:
        session.clear()
        flash('Session expired. Please login again.', 'warning')
        return redirect(url_for('login'))
    if user_has_admin_access(user):
        return redirect(url_for('admin_dashboard'))
    elif user.user_type == 'worker':
        return redirect(url_for('worker_dashboard'))
    elif user.user_type == 'customer':
        return redirect(url_for('customer_dashboard'))
    else:
        return redirect(url_for('index'))

# ==================== WORKER FEATURE ROUTES ====================

@app.route('/worker/analytics')
@login_required
def worker_analytics():
    """Worker analytics dashboard - only for weekly/monthly/annual plans"""
    user = get_current_user()
    if user.user_type != 'worker':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    if not has_feature_access(user, 'analytics'):
        flash('Analytics is only available for Weekly, Monthly, and Annual premium plans.', 'warning')
        return redirect(url_for('subscribe'))

    # Get analytics data
    worker = user.worker_profile
    applications = JobApplication.query.filter_by(worker_id=user.id).all()
    accepted_apps = [a for a in applications if a.status == 'accepted']
    completed_jobs = JobPost.query.filter_by(status='completed').join(JobApplication).filter(JobApplication.worker_id == user.id).count()

    # Prepare chart data (last 30 days)
    from collections import defaultdict
    daily_counts = defaultdict(int)
    for app in applications:
        if app.created_at > datetime.utcnow() - timedelta(days=30):
            daily_counts[app.created_at.strftime('%Y-%m-%d')] += 1

    chart_labels = list(daily_counts.keys())[-30:]
    chart_data = [daily_counts[date] for date in chart_labels]

    total_earnings = sum(a.bid_amount for a in accepted_apps if a.bid_amount)

    # Calculate response rate
    response_rate = 80
    if len(applications) > 0:
        accepted_count = len(accepted_apps)
        response_rate = int((accepted_count / len(applications)) * 100) if len(applications) > 0 else 0

    return render_template('worker_analytics.html',
                         user=user,
                         worker=worker,
                         total_applications=len(applications),
                         accepted_applications=len(accepted_apps),
                         completion_rate=int((completed_jobs / len(accepted_apps) * 100) if accepted_apps else 0),
                         avg_rating=worker.rating_score,
                         profile_views=0,
                         response_rate=response_rate,
                         total_earnings=total_earnings,
                         chart_labels=chart_labels,
                         chart_data=chart_data)

@app.route('/worker/qr-code')
@login_required
def worker_qr_code():
    """Generate QR code for worker profile - only for monthly/annual plans"""
    user = get_current_user()
    if user.user_type != 'worker':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    if not has_feature_access(user, 'qr_code'):
        flash('QR Code profile is only available for Monthly and Annual premium plans.', 'warning')
        return redirect(url_for('subscribe'))

    base_url = request.url_root.rstrip('/')
    profile_url = f"{base_url}/worker/{user.id}"

    return render_template('worker_qr_code.html', user=user, profile_url=profile_url)

@app.route('/worker/job-alerts', methods=['GET', 'POST'])
@login_required
def worker_job_alerts():
    """Manage job alerts - for all premium plans"""
    user = get_current_user()
    if user.user_type != 'worker':
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))

    if not has_feature_access(user, 'job_alerts'):
        flash('Job alerts are only available for premium plans.', 'warning')
        return redirect(url_for('subscribe'))

    # Alert settings - store in session for now (should use database in production)
    alert_settings = {
        'email_alerts': session.get('job_alerts_email', True),
        'sms_alerts': session.get('job_alerts_sms', False),
        'location': session.get('job_alerts_location', user.worker_profile.location or '')
    }
    selected_categories = session.get('job_alerts_categories', [user.worker_profile.primary_category] if user.worker_profile.primary_category else [])

    if request.method == 'POST':
        # Save alert settings to session
        email_alerts = request.form.get('email_alerts') == 'on'
        sms_alerts = request.form.get('sms_alerts') == 'on'
        location = request.form.get('location', '')
        categories = request.form.get('categories', '').split(',') if request.form.get('categories') else []

        session['job_alerts_email'] = email_alerts
        session['job_alerts_sms'] = sms_alerts
        session['job_alerts_location'] = location
        session['job_alerts_categories'] = categories

        flash('Alert preferences saved successfully!', 'success')
        return redirect(url_for('worker_job_alerts'))

    return render_template('worker_job_alerts.html',
                         user=user,
                         alert_settings=alert_settings,
                         selected_categories=selected_categories)

# ==================== AUTHENTICATION ROUTES ====================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        try:
            phone = format_phone(request.form.get('phone'))
            password = request.form.get('password')
            user_type = request.form.get('user_type')
            name = request.form.get('name')
            email = request.form.get('email', '').strip()
            logger.info(f"Registration attempt - Phone: {phone}, Type: {user_type}, Name: {name}, Email: {email}")
            if not validate_phone(phone):
                flash('Invalid phone number. Must be 254XXXXXXXXX format.', 'danger')
                return redirect(url_for('register'))
            if User.query.filter_by(phone=phone).first():
                flash('Phone number already registered.', 'danger')
                return redirect(url_for('register'))
            if not validate_password(password):
                flash('Password must be at least 6 characters.', 'danger')
                return redirect(url_for('register'))
            if user_type == 'customer':
                if not email:
                    flash('Email is required for customer accounts.', 'danger')
                    return redirect(url_for('register'))
                if not validate_email(email):
                    flash('Please enter a valid email address.', 'danger')
                    return redirect(url_for('register'))
            else:
                if email and not validate_email(email):
                    flash('Please enter a valid email address.', 'danger')
                    return redirect(url_for('register'))
            user = User(phone=phone, password_hash=generate_password_hash(password, method='pbkdf2:sha256'), user_type=user_type, name=name, email=email if email else None, is_admin=False)
            db.session.add(user)
            db.session.flush()
            if user_type == 'worker':
                worker = WorkerProfile(user_id=user.id, business_name=name, location=request.form.get('location', ''), skills=request.form.get('skills', ''), primary_category=request.form.get('primary_category', 'general'), secondary_categories=request.form.get('secondary_categories', ''), description=request.form.get('description', ''), hourly_rate=float(request.form.get('hourly_rate', 0)) if request.form.get('hourly_rate') else None, years_experience=int(request.form.get('years_experience', 0)) if request.form.get('years_experience') else 0, is_available=True, rating_score=0.0, rating_count=0)
                db.session.add(worker)
            free_sub = Subscription(user_id=user.id, plan_type='free', amount_paid=0, payment_status='completed', is_active=True, expires_at=datetime.utcnow() + timedelta(days=36500))
            db.session.add(free_sub)
            log_audit_event(user.id, 'register', f'User {user.name} registered as {user_type}')
            db.session.commit()
            notify_user_activity(user, 'register')
            if user.email:
                logger.info(f"Attempting to send welcome email to new {user_type}: {user.email}")
                email_sent = send_welcome_email(user)
                if email_sent:
                    user.welcome_email_sent = True
                    user.welcome_email_sent_at = datetime.utcnow()
                    db.session.commit()
                    logger.info(f"✅ Welcome email sent successfully to {user.email}")
                    flash('Registration successful! Check your email for a welcome message.', 'success')
                else:
                    logger.warning(f"❌ Failed to send welcome email to {user.email}")
                    if app.config['SEND_EMAILS']:
                        flash('Registration successful! (Welcome email could not be sent - please check email configuration)', 'warning')
                    else:
                        flash('Registration successful! (Email sending is disabled in configuration)', 'info')
            else:
                flash('Registration successful!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Registration error: {e}")
            logger.error(traceback.format_exc())
            flash(f'Registration failed: {str(e)}', 'danger')
            return redirect(url_for('register'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
            phone = format_phone(request.form.get('phone'))
            password = request.form.get('password')
            user = User.query.filter_by(phone=phone).first()
            if user and check_password_hash(user.password_hash, password):
                if user.suspended:
                    session['suspended_user_id'] = user.id
                    session['suspension_reason'] = user.suspension_reason
                    return redirect(url_for('suspended_account'))
                session.clear()
                session['user_id'] = user.id
                session['user_type'] = user.user_type
                session['user_name'] = user.name
                session['is_admin'] = user.is_admin
                session['has_admin_access'] = user_has_admin_access(user)
                log_audit_event(user.id, 'login', f'User {user.name} logged in')
                if not user.is_admin:
                    notify_user_activity(user, 'login')
                if not user.welcome_email_sent and user.email:
                    time_since_creation = datetime.utcnow() - user.created_at
                    if time_since_creation.total_seconds() <= app.config['WELCOME_EMAIL_GRACE_PERIOD']:
                        logger.info(f"Resending welcome email to {user.email} on login")
                        email_sent = send_welcome_email(user)
                        if email_sent:
                            user.welcome_email_sent = True
                            user.welcome_email_sent_at = datetime.utcnow()
                            db.session.commit()
                            flash('Welcome! Check your email for a welcome message.', 'info')
                if not user.is_admin and session['has_admin_access']:
                    flash('Welcome! You have admin access because your phone number matches the admin account.', 'info')
                else:
                    flash(f'Welcome back, {user.name}!', 'success')
                if session['has_admin_access']:
                    return redirect(url_for('admin_dashboard'))
                elif user.user_type == 'worker':
                    return redirect(url_for('worker_dashboard'))
                elif user.user_type == 'customer':
                    return redirect(url_for('customer_dashboard'))
                else:
                    return redirect(url_for('index'))
            flash('Invalid phone number or password.', 'danger')
        except Exception as e:
            logger.error(f"Login error: {e}")
            flash('Login failed. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/suspended-account')
def suspended_account():
    user_id = session.get('suspended_user_id')
    suspension_reason = session.get('suspension_reason', 'No reason provided.')
    if not user_id:
        return redirect(url_for('login'))
    user = User.query.get(user_id)
    if not user or not user.suspended:
        session.pop('suspended_user_id', None)
        session.pop('suspension_reason', None)
        return redirect(url_for('login'))
    return render_template('suspended.html', user=user, suspension_reason=suspension_reason)

@app.route('/logout')
def logout():
    if 'user_id' in session:
        log_audit_event(session['user_id'], 'logout', 'User logged out')
    session.clear()
    flash('Logged out successfully.', 'success')
    return redirect(url_for('index'))

# ==================== ADMIN ROUTES ====================

@app.route('/admin')
@login_required
def admin_dashboard():
    user = get_current_user()
    if not user_has_admin_access(user):
        flash('Access denied. Administrator privileges required.', 'danger')
        return redirect(url_for('index'))
    if not user.is_admin:
        log_audit_event(user.id, 'admin_access_by_phone_match', f'User {user.name} accessed admin via phone match')
        flash('You are accessing admin panel because your phone number matches the admin account.', 'info')
    try:
        pending_payments = Payment.query.filter_by(status='pending_verification').order_by(Payment.payment_date.desc()).all()
        all_payments = Payment.query.order_by(Payment.payment_date.desc()).limit(50).all()
        all_users = User.query.all()
        total_revenue = db.session.query(db.func.sum(Payment.amount)).filter(Payment.status == 'completed').scalar() or 0
        active_subscriptions = Subscription.query.filter_by(payment_status='completed', is_active=True).count()
        pending_verifications = VerificationRequest.query.filter_by(status='pending').count()
        total_payments = Payment.query.count()
        total_success_stories = SuccessStory.query.filter_by(is_approved=True).count()
        pending_success_stories = SuccessStory.query.filter_by(is_approved=False).count()
        try:
            reported_issues_pending = Report.query.filter_by(status='pending').count() if Report.query.first() is not None else 0
            reported_issues_total = Report.query.count() if Report.query.first() is not None else 0
            reported_issues_in_progress = Report.query.filter_by(status='in_progress').count() if Report.query.first() is not None else 0
            reported_issues_resolved = Report.query.filter_by(status='resolved').count() if Report.query.first() is not None else 0
        except Exception as e:
            logger.warning(f"Reports table may not exist yet: {e}")
            reported_issues_pending = 0
            reported_issues_total = 0
            reported_issues_in_progress = 0
            reported_issues_resolved = 0
        today = datetime.utcnow().date()
        week_start = datetime.utcnow() - timedelta(days=7)
        month_start = datetime.utcnow() - timedelta(days=30)
        today_payments = Payment.query.filter(Payment.status == 'completed', db.func.date(Payment.payment_date) == today).all()
        today_revenue = sum(p.amount for p in today_payments)
        today_count = len(today_payments)
        week_payments = Payment.query.filter(Payment.status == 'completed', Payment.payment_date >= week_start).all()
        week_revenue = sum(p.amount for p in week_payments)
        week_count = len(week_payments)
        month_payments = Payment.query.filter(Payment.status == 'completed', Payment.payment_date >= month_start).all()
        month_revenue = sum(p.amount for p in month_payments)
        month_count = len(month_payments)
        plan_stats = {}
        for plan_name in ['daily', 'weekly', 'monthly', 'annual']:
            subs = Subscription.query.filter_by(plan_type=plan_name, payment_status='completed', is_active=True).all()
            revenue = sum(s.amount_paid for s in subs)
            plan_stats[plan_name] = {'count': len(subs), 'revenue': revenue}
        stats = {
            'pending_payments': len(pending_payments),
            'total_payments': total_payments,
            'total_revenue': total_revenue,
            'total_users': len(all_users),
            'active_subscriptions': active_subscriptions,
            'pending_verifications': pending_verifications,
            'total_success_stories': total_success_stories,
            'pending_success_stories': pending_success_stories,
            'reported_issues_pending': reported_issues_pending,
            'reported_issues_total': reported_issues_total,
            'reported_issues_in_progress': reported_issues_in_progress,
            'reported_issues_resolved': reported_issues_resolved
        }
        return render_template('admin_dashboard.html', user=user, pending_payments=pending_payments, all_payments=all_payments, all_users=all_users, stats=stats, VerificationRequest=VerificationRequest, Subscription=Subscription, Report=Report, today_revenue=today_revenue, today_count=today_count, week_revenue=week_revenue, week_count=week_count, month_revenue=month_revenue, month_count=month_count, plan_stats=plan_stats, now=datetime.utcnow(), notifications=notification_manager.get_all_notifications(), unread_count=notification_manager.get_unread_count(), pending_success_stories=pending_success_stories)
    except Exception as e:
        logger.error(f"Admin dashboard error: {e}")
        logger.error(traceback.format_exc())
        flash('Unable to load admin dashboard.', 'danger')
        return redirect(url_for('index'))

@app.route('/admin/verify-payment/<int:payment_id>', methods=['POST'])
@admin_required
def verify_payment(payment_id):
    admin = get_current_user()
    payment = Payment.query.get_or_404(payment_id)
    try:
        payment.status = 'completed'
        payment.verified_by = admin.id
        payment.verified_at = datetime.utcnow()
        if payment.user:
            other_subs = Subscription.query.filter(Subscription.user_id == payment.user.id, Subscription.id != (payment.subscription.id if payment.subscription else 0), Subscription.is_active == True).all()
            for sub in other_subs:
                sub.is_active = False
                logger.info(f"Deactivated subscription {sub.id} ({sub.plan_type}) for user {payment.user.name}")
        if payment.subscription:
            subscription = payment.subscription
            subscription.payment_status = 'completed'
            subscription.is_active = True
            if not subscription.expires_at:
                if payment.user.user_type == 'worker':
                    plan_config = Config.WORKER_PLANS.get(payment.plan_type)
                else:
                    plan_config = Config.CUSTOMER_PLANS.get(payment.plan_type)
                if plan_config:
                    subscription.expires_at = datetime.utcnow() + timedelta(days=plan_config['duration_days'])
            db.session.commit()
            logger.info(f"✅ Subscription activated: User {payment.user.name} - Plan: {payment.plan_type} - Expires: {subscription.expires_at}")
        # Handle verification eligibility for workers
        if payment.user.user_type == 'worker' and payment.plan_type in ['weekly', 'monthly', 'annual']:
            worker = payment.user.worker_profile
            if worker:
                pending_verification = VerificationRequest.query.filter_by(worker_id=payment.user.id, status='pending').first()
                if pending_verification:
                    notify_admin(title='📋 Pending Verification Request', message=f'Worker {payment.user.name} has an active {payment.plan_type.upper()} plan and a pending verification request. Please review and approve.', type='warning', user_id=payment.user.id, user_name=payment.user.name)
                    flash(f'✅ Subscription activated! There is a pending verification request for {payment.user.name}. Please review it in the Verifications tab.', 'success')
                else:
                    notification = Notification(user_id=payment.user.id, title="🎉 Premium Subscription Activated!", message=f"Your {payment.plan_type.upper()} premium plan is now active. You are now eligible to apply for verification. Go to your dashboard and click 'Get Verified' to submit your documents.", type="success", created_at=datetime.utcnow(), read=False)
                    db.session.add(notification)
                    db.session.commit()
                    flash(f'✅ Subscription activated! You can now apply for verification from your dashboard.', 'success')
        elif payment.user.user_type == 'worker' and payment.plan_type == 'daily':
            notification = Notification(user_id=payment.user.id, title="🎉 Daily Premium Activated!", message=f"Your DAILY premium plan is now active. Note: Daily plan does NOT include verification badge. Upgrade to Weekly/Monthly/Annual to become eligible for verification!", type="info", created_at=datetime.utcnow(), read=False)
            db.session.add(notification)
            db.session.commit()
            flash(f'✅ Daily subscription activated! Note: Daily plan does NOT include verification badge. Upgrade to Weekly/Monthly/Annual to become eligible for verification.', 'info')
        elif payment.user.user_type == 'customer':
            notification = Notification(user_id=payment.user.id, title="🎉 Premium Subscription Activated!", message=f"Your {payment.plan_type.upper()} premium plan is now active. You now have unlimited job posts and priority listing!", type="success", created_at=datetime.utcnow(), read=False)
            db.session.add(notification)
            db.session.commit()
        log_audit_event(admin.id, 'verify_payment', f'Payment {payment_id} verified for user {payment.user.name}. Plan: {payment.plan_type} activated.')
        notify_admin(title='✅ Payment Verified', message=f'Payment of KES {payment.amount} from {payment.user.name} has been verified. {payment.plan_type.upper()} subscription activated.', type='success', user_id=payment.user.id, user_name=payment.user.name)
        if payment.user.email and app.config['SEND_EMAILS']:
            send_subscription_activated_email(payment.user, payment.plan_type, subscription.expires_at if payment.subscription else None)
        flash(f'✅ Payment #{payment.mpesa_transaction_id} verified! {payment.plan_type.upper()} subscription activated for {payment.user.name}.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Verify payment error: {e}")
        logger.error(traceback.format_exc())
        flash('Failed to verify payment. Please try again.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject-payment/<int:payment_id>', methods=['POST'])
@admin_required
def reject_payment(payment_id):
    admin = get_current_user()
    payment = Payment.query.get_or_404(payment_id)
    try:
        payment.status = 'failed'
        payment.verified_by = admin.id
        payment.verified_at = datetime.utcnow()
        if payment.subscription:
            payment.subscription.payment_status = 'failed'
        db.session.commit()
        log_audit_event(admin.id, 'reject_payment', f'Payment {payment_id} rejected')
        notify_admin(title='❌ Payment Rejected', message=f'Payment of KES {payment.amount} from {payment.user.name} has been rejected.', type='danger', user_id=payment.user.id, user_name=payment.user.name)
        flash(f'Payment #{payment.mpesa_transaction_id} rejected.', 'warning')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Reject payment error: {e}")
        flash('Failed to reject payment.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/verify-worker/<int:worker_id>', methods=['POST'])
@admin_required
def verify_worker(worker_id):
    admin = get_current_user()
    user = User.query.get_or_404(worker_id)
    if user.user_type != 'worker':
        flash('This user is not a worker', 'warning')
        return redirect(url_for('admin_dashboard'))
    worker_profile = WorkerProfile.query.filter_by(user_id=user.id).first()
    if not worker_profile:
        flash('Worker profile not found', 'danger')
        return redirect(url_for('admin_dashboard'))
    if worker_profile.is_verified:
        flash(f'Worker {user.name} is already verified', 'info')
        return redirect(url_for('admin_dashboard'))
    try:
        worker_profile.is_verified = True
        worker_profile.verification_badge = 'verified'
        worker_profile.verified_at = datetime.utcnow()
        worker_profile.verified_by = admin.id
        pending_req = VerificationRequest.query.filter_by(worker_id=user.id, status='pending').first()
        if pending_req:
            pending_req.status = 'approved'
            pending_req.reviewed_by = admin.id
            pending_req.reviewed_at = datetime.utcnow()
            pending_req.comments = f'Verified by admin {admin.name}'
        db.session.commit()
        log_audit_event(admin.id, 'verify_worker', f'Worker {user.name} (ID: {user.id}) verified by {admin.name}')
        try:
            notification = Notification(user_id=user.id, title="Verification Approved! ✅", message=f"Congratulations! Your profile has been verified. You can now access all premium features.", type="success", created_at=datetime.utcnow(), read=False)
            db.session.add(notification)
            db.session.commit()
        except Exception as e:
            logger.warning(f"Could not create notification: {e}")
        notify_admin(title='✅ Worker Verified', message=f'Worker {user.name} has been verified successfully!', type='success', user_id=user.id, user_name=user.name)
        flash(f'✅ Worker {user.name} has been verified successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Verify worker error: {e}")
        logger.error(traceback.format_exc())
        flash(f'Failed to verify worker: {str(e)}', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/suspend-user/<int:user_id>', methods=['POST'])
@admin_required
def suspend_user(user_id):
    admin = get_current_user()
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot suspend another admin user.', 'danger')
        return redirect(url_for('admin_dashboard'))
    if user.suspended:
        flash(f'User {user.name} is already suspended.', 'warning')
        return redirect(url_for('admin_dashboard'))
    try:
        suspension_reason = request.form.get('suspension_reason', 'No reason provided.')
        user.suspended = True
        user.suspension_reason = suspension_reason
        user.suspended_at = datetime.utcnow()
        user.suspended_by = admin.id
        user.is_active = False
        db.session.commit()
        log_audit_event(admin.id, 'suspend_user', f'User {user.name} suspended. Reason: {suspension_reason}')
        notify_admin(title='⚠️ User Suspended', message=f'User {user.name} has been suspended. Reason: {suspension_reason}', type='warning', user_id=user.id, user_name=user.name)
        flash(f'User {user.name} has been suspended immediately. Reason: {suspension_reason}', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Suspend user error: {e}")
        flash('Failed to suspend user.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/activate-user/<int:user_id>', methods=['POST'])
@admin_required
def activate_user(user_id):
    admin = get_current_user()
    user = User.query.get_or_404(user_id)
    try:
        user.suspended = False
        user.suspension_reason = None
        user.suspended_at = None
        user.suspended_by = None
        user.is_active = True
        db.session.commit()
        log_audit_event(admin.id, 'activate_user', f'User {user.name} activated immediately')
        notify_admin(title='✅ User Activated', message=f'User {user.name} has been activated.', type='success', user_id=user.id, user_name=user.name)
        flash(f'User {user.name} has been activated immediately. They can now log in.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Activate user error: {e}")
        flash('Failed to activate user.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete-user/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    admin = get_current_user()
    user = User.query.get_or_404(user_id)
    if user.is_admin:
        flash('Cannot delete the admin account.', 'danger')
        return redirect(url_for('admin_dashboard'))
    if user.id == admin.id:
        flash('You cannot delete your own account.', 'danger')
        return redirect(url_for('admin_dashboard'))
    try:
        user_name = user.name
        user_phone = user.phone
        VerificationRequest.query.filter_by(worker_id=user.id).delete()
        Review.query.filter_by(worker_id=user.id).delete()
        Review.query.filter_by(customer_id=user.id).delete()
        JobApplication.query.filter_by(worker_id=user.id).delete()
        JobPost.query.filter_by(customer_id=user.id).delete()
        Subscription.query.filter_by(user_id=user.id).delete()
        Payment.query.filter_by(user_id=user.id).delete()
        AuditLog.query.filter_by(user_id=user.id).delete()
        NewsletterSubscriber.query.filter_by(user_id=user.id).delete()
        SuccessStory.query.filter_by(user_id=user.id).delete()
        try:
            Report.query.filter_by(reporter_id=user.id).delete()
        except:
            pass
        if user.worker_profile:
            db.session.delete(user.worker_profile)
        db.session.delete(user)
        db.session.commit()
        log_audit_event(admin.id, 'delete_user', f'User {user_name} ({user_phone}) permanently deleted by {admin.name}')
        notify_admin(title='🗑️ User Deleted', message=f'User {user_name} has been permanently deleted from the system.', type='danger', user_id=user.id, user_name=user_name)
        flash(f'User {user_name} has been permanently deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete user error: {e}")
        logger.error(traceback.format_exc())
        flash('Failed to delete user. Please try again.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/reject-verification/<int:request_id>', methods=['POST'])
@admin_required
def reject_verification(request_id):
    admin = get_current_user()
    verification_req = VerificationRequest.query.get_or_404(request_id)
    try:
        verification_req.status = 'rejected'
        verification_req.reviewed_by = admin.id
        verification_req.reviewed_at = datetime.utcnow()
        verification_req.comments = request.form.get('rejection_reason', f'Rejected by admin {admin.name}')
        db.session.commit()
        log_audit_event(admin.id, 'reject_verification', f'Verification request for worker {verification_req.worker.name} rejected. Reason: {verification_req.comments}')
        notify_admin(title='❌ Verification Rejected', message=f'Verification request from {verification_req.worker.name} has been rejected.', type='danger', user_id=verification_req.worker.id, user_name=verification_req.worker.name)
        flash(f'Verification request for {verification_req.worker.name} rejected.', 'warning')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Reject verification error: {e}")
        flash('Failed to reject verification.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/settings', methods=['POST'])
@admin_required
def admin_settings():
    admin = get_current_user()
    platform_name = request.form.get('platform_name')
    contact_email = request.form.get('contact_email')
    contact_phone = request.form.get('contact_phone')
    mpesa_paybill = request.form.get('mpesa_paybill')
    settings = {'platform_name': platform_name, 'contact_email': contact_email, 'contact_phone': contact_phone, 'mpesa_paybill': mpesa_paybill, 'updated_at': datetime.utcnow().isoformat(), 'updated_by': admin.name}
    if save_settings(settings):
        log_audit_event(admin.id, 'update_settings', f'System settings updated immediately by {admin.name}')
        notify_admin(title='⚙️ Settings Updated', message=f'System settings were updated by {admin.name}', type='info')
        flash('Settings saved successfully and applied immediately!', 'success')
    else:
        flash('Failed to save settings. Please try again.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/refresh-subscriptions')
@admin_required
def admin_refresh_subscriptions():
    admin = get_current_user()
    try:
        expired_count = check_expired_subscriptions()
        log_audit_event(admin.id, 'refresh_subscriptions', f'Manually refreshed subscriptions, {expired_count} expired')
        flash(f'✅ Subscription refresh completed. {expired_count} subscriptions expired.', 'success')
    except Exception as e:
        logger.error(f"Manual subscription refresh error: {e}")
        flash('❌ Error refreshing subscriptions.', 'danger')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/notifications/clear-all', methods=['POST'])
@admin_required
def admin_clear_notifications():
    admin = get_current_user()
    notification_manager.clear_all()
    log_audit_event(admin.id, 'clear_notifications', 'All notifications cleared')
    flash('All notifications cleared.', 'success')
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/notifications/delete/<int:notification_id>', methods=['POST'])
@admin_required
def admin_delete_notification(notification_id):
    admin = get_current_user()
    try:
        notifications = notification_manager.get_all_notifications()
        notification_to_delete = None
        for notif in notifications:
            if notif['id'] == notification_id:
                notification_to_delete = notif
                break
        if notification_to_delete:
            notification_manager.notifications = [n for n in notification_manager.notifications if n['id'] != notification_id]
            log_audit_event(admin.id, 'delete_notification', f'Deleted notification: {notification_to_delete["title"]}')
            return jsonify({'success': True, 'message': 'Notification deleted successfully', 'unread_count': notification_manager.get_unread_count()})
        else:
            return jsonify({'success': False, 'message': 'Notification not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting notification: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/create-admin', methods=['GET', 'POST'])
def create_admin():
    if User.query.filter_by(is_admin=True).first():
        flash('Admin already exists. Only one admin account is allowed.', 'warning')
        return redirect(url_for('login'))
    if request.method == 'POST':
        try:
            phone = format_phone(request.form.get('phone'))
            password = request.form.get('password')
            name = request.form.get('name')
            existing_user = User.query.filter_by(phone=phone).first()
            if existing_user:
                existing_user.is_admin = True
                existing_user.name = name
                existing_user.admin_phone_verified = True
                db.session.commit()
                log_audit_event(existing_user.id, 'create_admin', f'Existing user {existing_user.name} promoted to admin')
                flash(f'User {existing_user.name} has been promoted to admin immediately! Please login.', 'success')
                return redirect(url_for('login'))
            if not validate_phone(phone):
                flash('Invalid phone number. Must be 254XXXXXXXXX format.', 'danger')
                return redirect(url_for('create_admin'))
            if not validate_password(password):
                flash('Password must be at least 6 characters.', 'danger')
                return redirect(url_for('create_admin'))
            admin = User(phone=phone, password_hash=generate_password_hash(password), user_type='admin', name=name, is_admin=True, admin_phone_verified=True)
            db.session.add(admin)
            db.session.commit()
            free_sub = Subscription(user_id=admin.id, plan_type='free', amount_paid=0, payment_status='completed', is_active=True, expires_at=datetime.utcnow() + timedelta(days=36500))
            db.session.add(free_sub)
            db.session.commit()
            log_audit_event(admin.id, 'create_admin', 'Admin account created')
            flash('Admin account created successfully! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            logger.error(f"Create admin error: {e}")
            flash('Failed to create admin account.', 'danger')
    return render_template('create_admin.html')

# ==================== STATIC PAGE ROUTES ====================

@app.route('/how-it-works')
def how_it_works():
    return render_template('how_it_works.html')

@app.route('/success-stories')
def success_stories():
    approved_stories = SuccessStory.query.filter_by(is_approved=True).order_by(SuccessStory.created_at.desc()).all()
    total_stories = SuccessStory.query.filter_by(is_approved=True).count()
    total_workers = User.query.filter_by(user_type='worker', is_active=True).count()
    total_jobs = JobPost.query.filter_by(status='completed').count()
    avg_rating_result = db.session.query(db.func.avg(Review.rating)).scalar()
    satisfaction_rate = round((avg_rating_result or 4.8) * 20, 0)
    stats = {'stories': total_stories, 'workers': total_workers, 'jobs_completed': total_jobs, 'satisfaction': satisfaction_rate}
    return render_template('success_stories.html', stories=approved_stories, stats=stats)

@app.route('/tips-for-success')
def tips_for_success():
    return render_template('tips_for_success.html')

@app.route('/safety-tips')
def safety_tips():
    return render_template('safety_tips.html')

@app.route('/help-center')
def help_center():
    return render_template('help_center.html')

@app.route('/report-issue')
def report_issue():
    user = get_current_user()
    return render_template('report_issue.html', user=user)

@app.route('/track-report')
def track_report():
    try:
        tracking_id = request.args.get('tracking', '').strip()
        if not tracking_id:
            flash('Please provide a tracking ID.', 'warning')
            return redirect(url_for('report_issue'))
        report = Report.query.filter_by(tracking_id=tracking_id).first()
        if not report:
            flash('Report not found with that tracking ID.', 'danger')
            return redirect(url_for('report_issue'))
        return render_template('track_report.html', report=report)
    except Exception as e:
        logger.error(f"Track report error: {e}")
        flash('Unable to track report. Please try again.', 'danger')
        return redirect(url_for('index'))

@app.route('/terms')
def terms():
    return render_template('terms.html')

# ==================== SUCCESS STORIES API ROUTES ====================

@app.route('/api/submit-story', methods=['POST'])
def submit_story():
    try:
        data = request.get_json()
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        category = data.get('category', '').strip()
        title = data.get('title', '').strip()
        story = data.get('story', '').strip()
        rating = int(data.get('rating', 5))
        if not name:
            return jsonify({'success': False, 'message': 'Please enter your name'}), 400
        if not category:
            return jsonify({'success': False, 'message': 'Please select a category'}), 400
        if not title:
            return jsonify({'success': False, 'message': 'Please enter a title'}), 400
        if not story or len(story) < 20:
            return jsonify({'success': False, 'message': 'Please share your story (at least 20 characters)'}), 400
        user_id = session.get('user_id')
        current_user = get_current_user()
        profile_picture = None
        if current_user and current_user.profile_picture and current_user.profile_picture != 'default-avatar.png':
            profile_picture = current_user.profile_picture
        new_story = SuccessStory(user_id=user_id, name=name, email=email if email else None, category=category, title=title, story=story, rating=rating, is_approved=False, featured=False, profile_picture_cache=profile_picture)
        db.session.add(new_story)
        db.session.commit()
        pending_count = SuccessStory.query.filter_by(is_approved=False).count()
        notify_admin(title='📖 New Success Story Submitted', message=f'New story from {name} about {category} - "{title[:50]}..." is pending approval. ({pending_count} total pending)', type='warning', user_id=user_id, user_name=name, action_url=url_for('admin_success_stories'))
        return jsonify({'success': True, 'message': 'Thank you for sharing your story! It will be reviewed by our team and published soon.'})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Submit story error: {e}")
        return jsonify({'success': False, 'message': 'Failed to submit story. Please try again.'}), 500

# ==================== ADMIN SUCCESS STORIES ROUTES ====================

@app.route('/admin/success-stories')
@admin_required
def admin_success_stories():
    user = get_current_user()
    pending_stories = SuccessStory.query.filter_by(is_approved=False).order_by(SuccessStory.created_at.desc()).all()
    approved_stories = SuccessStory.query.filter_by(is_approved=True).order_by(SuccessStory.created_at.desc()).all()
    return render_template('admin_success_stories.html', user=user, pending_stories=pending_stories, approved_stories=approved_stories)

@app.route('/admin/approve-story/<int:story_id>', methods=['POST'])
@admin_required
def approve_story(story_id):
    admin = get_current_user()
    story = SuccessStory.query.get_or_404(story_id)
    try:
        story.is_approved = True
        story.approved_at = datetime.utcnow()
        if story.user_id:
            user = User.query.get(story.user_id)
            if user and user.profile_picture and user.profile_picture != 'default-avatar.png':
                story.profile_picture_cache = user.profile_picture
        db.session.commit()
        log_audit_event(admin.id, 'approve_story', f'Story "{story.title}" by {story.name} approved')
        notify_admin(title='✅ Story Approved', message=f'Story "{story.title}" by {story.name} has been approved and published.', type='success')
        flash(f'Story "{story.title}" has been approved and published.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Approve story error: {e}")
        flash('Failed to approve story.', 'danger')
    return redirect(url_for('admin_success_stories'))

@app.route('/admin/reject-story/<int:story_id>', methods=['POST'])
@admin_required
def reject_story(story_id):
    admin = get_current_user()
    story = SuccessStory.query.get_or_404(story_id)
    try:
        rejection_reason = request.form.get('rejection_reason', 'No reason provided')
        db.session.delete(story)
        db.session.commit()
        log_audit_event(admin.id, 'reject_story', f'Story "{story.title}" by {story.name} rejected. Reason: {rejection_reason}')
        notify_admin(title='❌ Story Rejected', message=f'Story "{story.title}" by {story.name} has been rejected.', type='warning')
        flash(f'Story has been rejected and removed.', 'warning')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Reject story error: {e}")
        flash('Failed to reject story.', 'danger')
    return redirect(url_for('admin_success_stories'))

@app.route('/admin/feature-story/<int:story_id>', methods=['POST'])
@admin_required
def feature_story(story_id):
    admin = get_current_user()
    story = SuccessStory.query.get_or_404(story_id)
    try:
        SuccessStory.query.update({SuccessStory.featured: False})
        db.session.commit()
        story.featured = True
        db.session.commit()
        log_audit_event(admin.id, 'feature_story', f'Story "{story.title}" by {story.name} featured')
        flash(f'Story "{story.title}" is now featured on the homepage!', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Feature story error: {e}")
        flash('Failed to feature story.', 'danger')
    return redirect(url_for('admin_success_stories'))

@app.route('/admin/unfeature-story/<int:story_id>', methods=['POST'])
@admin_required
def unfeature_story(story_id):
    admin = get_current_user()
    story = SuccessStory.query.get_or_404(story_id)
    try:
        story.featured = False
        db.session.commit()
        log_audit_event(admin.id, 'unfeature_story', f'Story "{story.title}" by {story.name} removed from featured')
        notify_admin(title='⭐ Story Unfeatured', message=f'Story "{story.title}" by {story.name} is no longer featured on the homepage.', type='info')
        flash(f'Story "{story.title}" is no longer featured on the homepage.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Unfeature story error: {e}")
        flash('Failed to remove featured status.', 'danger')
    return redirect(url_for('admin_success_stories'))

@app.route('/admin/delete-story/<int:story_id>', methods=['POST'])
@admin_required
def delete_story(story_id):
    admin = get_current_user()
    story = SuccessStory.query.get_or_404(story_id)
    try:
        story_title = story.title
        story_name = story.name
        db.session.delete(story)
        db.session.commit()
        log_audit_event(admin.id, 'delete_story', f'Story "{story_title}" by {story_name} deleted')
        flash(f'Story has been permanently deleted.', 'success')
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete story error: {e}")
        flash('Failed to delete story.', 'danger')
    return redirect(url_for('admin_success_stories'))

# ==================== ERROR HANDLERS ====================

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f'500 error: {error}\n{traceback.format_exc()}')
    return render_template('500.html'), 500

# ==================== REPORT ISSUE ROUTES ====================

def send_report_confirmation_email(report, reporter_email, tracking_id):
    try:
        settings = load_settings()
        base_url = request.url_root.rstrip('/')
        subject = f"[FundiConnect] Report Confirmation - {tracking_id}"
        html_content = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{{font-family:Arial,sans-serif;line-height:1.6;color:#333;}}.container{{max-width:600px;margin:0 auto;padding:20px;}}.header{{background:linear-gradient(135deg,#059669 0%,#047857 100%);color:white;padding:20px;text-align:center;border-radius:10px 10px 0 0;}}.content{{background:#f9fafb;padding:20px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 10px 10px;}}.tracking-box{{background:white;padding:15px;border-radius:10px;border:1px solid #e5e7eb;margin:15px 0;text-align:center;}}.tracking-code{{font-size:20px;font-weight:bold;color:#059669;font-family:monospace;}}.button{{display:inline-block;background:#059669;color:white;padding:10px 20px;text-decoration:none;border-radius:8px;margin-top:15px;}}.footer{{text-align:center;margin-top:20px;padding-top:20px;border-top:1px solid #e5e7eb;font-size:12px;color:#6b7280;}}</style></head><body><div class="container"><div class="header"><h2>📋 Report Received</h2><p>{settings.get('platform_name', 'FundiConnect')}</p></div><div class="content"><p>Hello {report.reporter_name or 'there'},</p><p>Thank you for reporting an issue. We have received your report and our team will review it shortly.</p><div class="tracking-box"><div style="font-size:12px;color:#6b7280;margin-bottom:5px;">Your Tracking ID</div><div class="tracking-code">{tracking_id}</div><div style="font-size:12px;color:#6b7280;margin-top:5px;">Use this ID to track your report status</div></div><div style="text-align:center;"><a href="{base_url}/track-report?tracking={tracking_id}" class="button">Track Your Report</a></div><p style="margin-top:20px;">Our support team will review your report within 24-48 hours. You will receive email updates when the status changes.</p></div><div class="footer"><p>This is an automated confirmation from {settings.get('platform_name', 'FundiConnect')}.</p><p>If you have any questions, please contact us at {settings.get('contact_email', 'support@fundiconnect.co.ke')}</p></div></div></body></html>"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = app.config['MAIL_DEFAULT_SENDER'] or app.config['MAIL_USERNAME']
        msg['To'] = reporter_email
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        if app.config['MAIL_USE_TLS']:
            server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send confirmation email: {e}")
        return False

def send_report_email(report):
    if not app.config['SEND_EMAILS']:
        return True
    admin_email = app.config['MAIL_USERNAME']
    if not admin_email:
        return False
    try:
        settings = load_settings()
        base_url = request.url_root.rstrip('/')
        subject = f"[FundiConnect Report] {report.report_type.upper()} - {report.issue_title[:50]}"
        html_content = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{{font-family:Arial,sans-serif;line-height:1.6;}}.container{{max-width:600px;margin:0 auto;padding:20px;}}.header{{background:linear-gradient(135deg,#059669 0%,#047857 100%);color:white;padding:20px;text-align:center;border-radius:10px 10px 0 0;}}.content{{background:#f9fafb;padding:20px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 10px 10px;}}.field{{margin-bottom:15px;}}.field-label{{font-weight:bold;color:#374151;margin-bottom:5px;}}.field-value{{background:white;padding:10px;border-radius:8px;border:1px solid #e5e7eb;}}.button{{display:inline-block;background:#059669;color:white;padding:10px 20px;text-decoration:none;border-radius:8px;margin-top:15px;}}</style></head><body><div class="container"><div class="header"><h2>📋 New Report Received</h2><p>{settings.get('platform_name', 'FundiConnect')}</p></div><div class="content"><div class="field"><div class="field-label">Tracking ID:</div><div class="field-value"><strong>{report.tracking_id}</strong></div></div><div class="field"><div class="field-label">Priority:</div><div class="field-value>{report.priority.upper()}</div></div><div class="field"><div class="field-label">Report Type:</div><div class="field-value">{report.report_type.upper()}</div></div><div class="field"><div class="field-label">Issue Title:</div><div class="field-value">{report.issue_title}</div></div><div class="field"><div class="field-label">Description:</div><div class="field-value">{report.description}</div></div><div class="field"><div class="field-label">Reporter:</div><div class="field-value">{report.reporter_name or 'Anonymous'} ({report.reporter_email or 'No email'})</div></div><div style="text-align:center;"><a href="{base_url}/admin" class="button">Go to Admin Dashboard</a></div></div></div></body></html>"""
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = admin_email
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        if app.config['MAIL_USE_TLS']:
            server.starttls()
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        logger.error(f"Failed to send report email: {e}")
        return False

@app.route('/submit-report', methods=['POST'])
def submit_report():
    try:
        report_type = request.form.get('report_type')
        issue_title = request.form.get('issue_title')
        description = request.form.get('description')
        reporter_name = request.form.get('reporter_name', '').strip()
        reporter_email = request.form.get('reporter_email', '').strip()
        related_id = request.form.get('related_id', '').strip()
        priority = request.form.get('priority', 'medium')
        if not report_type:
            return jsonify({'success': False, 'message': 'Please select a report type'}), 400
        if not issue_title or len(issue_title) < 5:
            return jsonify({'success': False, 'message': 'Please enter a valid issue title (at least 5 characters)'}), 400
        if not description or len(description) < 20:
            return jsonify({'success': False, 'message': 'Please provide a detailed description (at least 20 characters)'}), 400
        if reporter_email and not validate_email(reporter_email):
            return jsonify({'success': False, 'message': 'Please enter a valid email address'}), 400
        if not reporter_name and not reporter_email:
            return jsonify({'success': False, 'message': 'Please provide either your name or email for follow-up'}), 400
        current_user = get_current_user()
        reporter_id = current_user.id if current_user else None
        tracking_id = generate_tracking_id()
        if not reporter_name and current_user:
            reporter_name = current_user.name
        if not reporter_email and current_user and current_user.email:
            reporter_email = current_user.email
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent', '')[:500]
        report = Report(reporter_id=reporter_id, reporter_name=reporter_name if reporter_name else None, reporter_email=reporter_email if reporter_email else None, reporter_ip=ip_address, reporter_user_agent=user_agent, report_type=report_type, issue_title=issue_title, description=description, related_id=related_id if related_id else None, priority=priority, status='pending', is_urgent=(priority == 'urgent'), tracking_id=tracking_id)
        db.session.add(report)
        db.session.commit()
        logger.info(f"Report #{report.id} saved with tracking ID: {tracking_id}")
        if reporter_email and app.config['SEND_EMAILS'] and app.config['MAIL_USERNAME']:
            try:
                send_report_confirmation_email(report, reporter_email, tracking_id)
            except Exception as e:
                logger.error(f"Failed to send confirmation email: {e}")
        if app.config['SEND_EMAILS'] and app.config['MAIL_USERNAME']:
            try:
                send_report_email(report)
            except Exception as e:
                logger.error(f"Failed to send report email: {e}")
        notify_admin(title=f'📋 New Report: {report_type.upper()}', message=f'New report from {reporter_name or "Anonymous"}: "{issue_title[:50]}..." Priority: {priority.upper()}', type='warning' if priority in ['high', 'urgent'] else 'info', user_id=reporter_id, user_name=reporter_name)
        return jsonify({'success': True, 'message': f'Report submitted successfully! Your tracking ID is: {tracking_id}', 'report_id': report.id, 'tracking_id': tracking_id})
    except Exception as e:
        db.session.rollback()
        logger.error(f"Submit report error: {e}")
        logger.error(traceback.format_exc())
        return jsonify({'success': False, 'message': f'Failed to submit report: {str(e)}'}), 500

# ==================== ADMIN REPORTED ISSUES ROUTES ====================

@app.route('/admin/reported-issues')
@admin_required
def admin_reported_issues():
    user = get_current_user()
    status_filter = request.args.get('status', 'all')
    type_filter = request.args.get('type', 'all')
    priority_filter = request.args.get('priority', 'all')
    query = Report.query
    if status_filter != 'all':
        query = query.filter_by(status=status_filter)
    if type_filter != 'all':
        query = query.filter_by(report_type=type_filter)
    if priority_filter != 'all':
        query = query.filter_by(priority=priority_filter)
    reports = query.order_by(db.case((Report.status == 'pending', 1), (Report.status == 'in_progress', 2), (Report.status == 'resolved', 3), (Report.status == 'dismissed', 4), else_=5), db.case((Report.priority == 'urgent', 1), (Report.priority == 'high', 2), (Report.priority == 'medium', 3), (Report.priority == 'low', 4), else_=5), Report.created_at.desc()).all()
    stats = {'total': Report.query.count(), 'pending': Report.query.filter_by(status='pending').count(), 'in_progress': Report.query.filter_by(status='in_progress').count(), 'resolved': Report.query.filter_by(status='resolved').count(), 'dismissed': Report.query.filter_by(status='dismissed').count(), 'urgent': Report.query.filter_by(priority='urgent', status='pending').count(), 'high': Report.query.filter_by(priority='high', status='pending').count()}
    return render_template('admin_reports.html', user=user, reports=reports, stats=stats, current_status=status_filter, current_type=type_filter, current_priority=priority_filter)

@app.route('/admin/report-detail/<int:report_id>')
@admin_required
def admin_report_detail(report_id):
    user = get_current_user()
    report = Report.query.get_or_404(report_id)
    report.viewed_at = datetime.utcnow()
    db.session.commit()
    return render_template('admin_report_detail.html', user=user, report=report)

@app.route('/admin/reported-issue/<int:report_id>/update-status', methods=['POST'])
@admin_required
def admin_update_reported_issue_status(report_id):
    admin = get_current_user()
    report = Report.query.get_or_404(report_id)
    try:
        new_status = request.form.get('status')
        resolution_notes = request.form.get('resolution_notes', '').strip()
        if new_status not in ['pending', 'in_progress', 'resolved', 'dismissed']:
            flash('Invalid status.', 'danger')
            return redirect(url_for('admin_report_detail', report_id=report_id))
        old_status = report.status
        report.status = new_status
        report.updated_at = datetime.utcnow()
        if new_status in ['resolved', 'dismissed']:
            report.resolved_by = admin.id
            report.resolved_at = datetime.utcnow()
            if resolution_notes:
                report.resolution_notes = resolution_notes
        db.session.commit()
        log_audit_event(admin.id, 'update_report_status', f'Report #{report.id} status changed from {old_status} to {new_status}')
        notify_admin(title=f'📋 Report Status Updated', message=f'Report #{report.id} - {report.issue_title[:50]} status changed to {new_status.upper()}', type='info')
        flash(f'Report #{report.id} status updated to {new_status.upper()}.', 'success')
        return redirect(url_for('admin_report_detail', report_id=report_id))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Update report status error: {e}")
        flash('Failed to update report status.', 'danger')
        return redirect(url_for('admin_reported_issue_detail', report_id=report_id))

@app.route('/admin/reported-issue/<int:report_id>/delete', methods=['POST'])
@admin_required
def admin_delete_reported_issue(report_id):
    admin = get_current_user()
    report = Report.query.get_or_404(report_id)
    try:
        report_title = report.issue_title
        report_id_num = report.id
        log_audit_event(admin.id, 'delete_report', f'Report #{report_id_num} deleted: {report_title}')
        notify_admin(title='🗑️ Report Deleted', message=f'Report #{report_id_num} - "{report_title[:50]}" has been permanently deleted by {admin.name}', type='danger')
        db.session.delete(report)
        db.session.commit()
        flash(f'Report #{report_id_num} has been permanently deleted.', 'success')
        return redirect(url_for('admin_dashboard', _anchor='issues-tab'))
    except Exception as e:
        db.session.rollback()
        logger.error(f"Delete report error: {e}")
        flash('Failed to delete report. Please try again.', 'danger')
        return redirect(url_for('admin_reported_issue_detail', report_id=report_id))

@app.route('/my-reports')
@login_required
def my_reports():
    try:
        user = get_current_user()
        if not user:
            flash('Please login to view your reports.', 'warning')
            return redirect(url_for('login'))
        reports = Report.query.filter_by(reporter_id=user.id).order_by(Report.created_at.desc()).all()
        return render_template('my_reports.html', reports=reports, user=user)
    except Exception as e:
        logger.error(f"My reports error: {e}")
        logger.error(traceback.format_exc())
        flash('Unable to load your reports. Please try again.', 'danger')
        return redirect(url_for('index'))

@app.route('/submit-appeal', methods=['POST'])
def submit_appeal():
    try:
        user_id = session.get('suspended_user_id')
        if not user_id:
            flash('Session expired. Please login again.', 'warning')
            return redirect(url_for('login'))
        user = User.query.get(user_id)
        if not user:
            flash('User not found.', 'danger')
            return redirect(url_for('login'))
        appeal_message = request.form.get('appeal_message', '').strip()
        if not appeal_message:
            flash('Please provide a message explaining your appeal.', 'danger')
            return redirect(url_for('suspended_account'))
        if len(appeal_message) < 20:
            flash('Please provide a more detailed explanation (at least 20 characters).', 'danger')
            return redirect(url_for('suspended_account'))
        log_audit_event(user.id, 'appeal_submission', f'Appeal submitted: {appeal_message[:200]}')
        if app.config['SEND_EMAILS'] and app.config['MAIL_USERNAME']:
            try:
                settings = load_settings()
                admin_email = app.config['MAIL_USERNAME']
                subject = f"[APPEAL] Account Suspension Appeal - {user.name}"
                html_content = f"""<!DOCTYPE html><html><head><meta charset="UTF-8"><style>body{{font-family:Arial,sans-serif;line-height:1.6;}}.container{{max-width:600px;margin:0 auto;padding:20px;}}.header{{background:linear-gradient(135deg,#059669 0%,#047857 100%);color:white;padding:20px;text-align:center;border-radius:10px 10px 0 0;}}.content{{background:#f9fafb;padding:20px;border:1px solid #e5e7eb;border-top:none;border-radius:0 0 10px 10px;}}.field{{margin-bottom:15px;}}.field-label{{font-weight:bold;color:#374151;margin-bottom:5px;}}.field-value{{background:white;padding:10px;border-radius:8px;border:1px solid #e5e7eb;}}</style></head><body><div class="container"><div class="header"><h2>Account Suspension Appeal</h2><p>{settings.get('platform_name', 'FundiConnect')}</p></div><div class="content"><div class="field"><div class="field-label">User Name:</div><div class="field-value">{user.name}</div></div><div class="field"><div class="field-label">Phone:</div><div class="field-value">{user.phone}</div></div><div class="field"><div class="field-label">Email:</div><div class="field-value">{user.email or 'Not provided'}</div></div><div class="field"><div class="field-label">Suspension Reason:</div><div class="field-value">{user.suspension_reason or 'No reason provided'}</div></div><div class="field"><div class="field-label">Appeal Message:</div><div class="field-value">{appeal_message}</div></div></div></div></body></html>"""
                msg = MIMEMultipart('alternative')
                msg['Subject'] = subject
                msg['From'] = app.config['MAIL_DEFAULT_SENDER'] or app.config['MAIL_USERNAME']
                msg['To'] = admin_email
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
                server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
                if app.config['MAIL_USE_TLS']:
                    server.starttls()
                server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
                server.send_message(msg)
                server.quit()
            except Exception as e:
                logger.error(f"Failed to send appeal email: {e}")
        notify_admin(title='📋 Account Suspension Appeal', message=f'User {user.name} has submitted an appeal for their suspended account.', type='warning', user_id=user.id, user_name=user.name, action_url=url_for('admin_dashboard'))
        flash('Your appeal has been submitted successfully! Our team will review it within 24-48 hours.', 'success')
        return redirect(url_for('suspended_account'))
    except Exception as e:
        logger.error(f"Appeal submission error: {e}")
        logger.error(traceback.format_exc())
        flash('Failed to submit appeal. Please try again or contact support directly.', 'danger')
        return redirect(url_for('suspended_account'))

# ==================== START SUBSCRIPTION SCHEDULER ====================

def start_subscription_scheduler():
    try:
        def run_scheduler():
            logger.info("🚀 Subscription scheduler started")
            while True:
                with app.app_context():
                    try:
                        expired = check_expired_subscriptions()
                        update_job_expiration()
                        if expired > 0:
                            logger.info(f"Subscription scheduler: {expired} subscriptions expired")
                    except Exception as e:
                        logger.error(f"Subscription scheduler error: {e}")
                time.sleep(3600)
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        logger.info("✅ Subscription expiration scheduler started (checking every hour)")
    except Exception as e:
        logger.warning(f"Could not start subscription scheduler: {e}")

if __name__ != '__main__':
    start_subscription_scheduler()

def add_premium_columns():
    """Add premium feature columns to worker_profiles table if they don't exist"""

    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        print("Please make sure the database exists before running this script.")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check existing columns in worker_profiles
        cursor.execute("PRAGMA table_info(worker_profiles)")
        existing_columns = [col[1] for col in cursor.fetchall()]

        print("=" * 60)
        print("FundiConnect - Database Update Utility")
        print("=" * 60)
        print(f"\n📁 Database: {db_path}")
        print(f"📊 Existing columns in worker_profiles: {len(existing_columns)}")
        print("-" * 60)

        # Columns to add if they don't exist
        columns_to_add = {
            'portfolio_images': {
                'sql': "ALTER TABLE worker_profiles ADD COLUMN portfolio_images TEXT",
                'description': 'Portfolio images (comma-separated filenames)'
            },
            'certifications': {
                'sql': "ALTER TABLE worker_profiles ADD COLUMN certifications TEXT",
                'description': 'Certifications & licenses (JSON format)'
            },
            'whatsapp': {
                'sql': "ALTER TABLE worker_profiles ADD COLUMN whatsapp VARCHAR(20)",
                'description': 'WhatsApp phone number'
            },
            'facebook': {
                'sql': "ALTER TABLE worker_profiles ADD COLUMN facebook VARCHAR(200)",
                'description': 'Facebook profile URL'
            },
            'instagram': {
                'sql': "ALTER TABLE worker_profiles ADD COLUMN instagram VARCHAR(100)",
                'description': 'Instagram handle'
            },
            'twitter': {
                'sql': "ALTER TABLE worker_profiles ADD COLUMN twitter VARCHAR(100)",
                'description': 'Twitter handle'
            },
            'linkedin': {
                'sql': "ALTER TABLE worker_profiles ADD COLUMN linkedin VARCHAR(200)",
                'description': 'LinkedIn profile URL'
            },
            'website': {
                'sql': "ALTER TABLE worker_profiles ADD COLUMN website VARCHAR(200)",
                'description': 'Personal website or portfolio URL'
            }
        }

        added_columns = []
        skipped_columns = []
        failed_columns = []

        # Add missing columns
        for col_name, col_info in columns_to_add.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(col_info['sql'])
                    added_columns.append(col_name)
                    print(f"✅ Added column: {col_name:20} - {col_info['description']}")
                except Exception as e:
                    failed_columns.append(col_name)
                    print(f"❌ Failed to add {col_name}: {str(e)}")
            else:
                skipped_columns.append(col_name)
                print(f"✓  Column already exists: {col_name:20} - {col_info['description']}")

        # Commit the changes
        conn.commit()

        # Verify columns were added
        cursor.execute("PRAGMA table_info(worker_profiles)")
        final_columns = [col[1] for col in cursor.fetchall()]

        print("-" * 60)
        print("\n📊 Summary:")
        print(f"   • Columns added: {len(added_columns)}")
        print(f"   • Columns already existed: {len(skipped_columns)}")
        print(f"   • Columns failed: {len(failed_columns)}")
        print(f"   • Total columns now: {len(final_columns)}")

        if added_columns:
            print("\n✨ Successfully added columns:")
            for col in added_columns:
                print(f"   - {col}")

        if failed_columns:
            print("\n⚠️ Failed to add columns:")
            for col in failed_columns:
                print(f"   - {col}")

        conn.close()

        print("\n" + "=" * 60)
        print("✅ Database update completed successfully!")
        print("=" * 60)
        print("\nYou can now restart your Flask application to use the new premium features.")
        print("The certifications and social links will now be saved to the database.")

        return True

    except Exception as e:
        print(f"\n❌ Error updating database: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def verify_columns():
    """Verify that all premium columns exist in the database"""

    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(worker_profiles)")
        columns = [col[1] for col in cursor.fetchall()]

        expected_columns = [
            'portfolio_images', 'certifications', 'whatsapp', 'facebook',
            'instagram', 'twitter', 'linkedin', 'website'
        ]

        print("\n🔍 Verifying premium columns...")
        print("-" * 40)

        missing = []
        for col in expected_columns:
            if col in columns:
                print(f"✅ {col}: PRESENT")
            else:
                print(f"❌ {col}: MISSING")
                missing.append(col)

        conn.close()

        if missing:
            print(f"\n⚠️ Missing {len(missing)} column(s). Run the script again to add them.")
            return False
        else:
            print("\n✅ All premium columns are present!")
            return True

    except Exception as e:
        print(f"❌ Error verifying columns: {str(e)}")
        return False

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print(" FundiConnect - Premium Features Database Update")
    print("=" * 60)
    print("\nThis script will add the following columns to the worker_profiles table:")
    print("  • portfolio_images - Portfolio images storage")
    print("  • certifications   - Certifications & licenses (JSON format)")
    print("  • whatsapp         - WhatsApp number")
    print("  • facebook         - Facebook profile URL")
    print("  • instagram        - Instagram handle")
    print("  • twitter          - Twitter handle")
    print("  • linkedin         - LinkedIn profile URL")
    print("  • website          - Personal website URL")
    print("\n" + "-" * 60)

    # Ask for confirmation
    response = input("\nDo you want to proceed? (y/n): ").strip().lower()

    if response in ['y', 'yes']:
        success = add_premium_columns()
        if success:
            print("\nVerifying the update...")
            verify_columns()
    else:
        print("\n❌ Operation cancelled.")
        sys.exit(0)

if __name__ == '__main__':
    start_subscription_scheduler()
    app.run(debug=Config.DEBUG, host='0.0.0.0', port=5000)
