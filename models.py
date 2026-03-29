"""
FundiConnect Database Models
Enterprise-grade database schema with complete relationships
"""

from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()


class User(db.Model):
    """User model for customers, workers, and admin"""
    __tablename__ = 'users'
    __table_args__ = (
        db.Index('idx_user_phone', 'phone'),
        db.Index('idx_user_type', 'user_type'),
    )

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(15), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    user_type = db.Column(db.String(20), nullable=False, index=True)
    profile_picture = db.Column(db.String(200), default='default-avatar.png')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    last_login = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    admin_phone_verified = db.Column(db.Boolean, default=False)

    # Suspension fields
    suspended = db.Column(db.Boolean, default=False)
    suspension_reason = db.Column(db.Text, nullable=True)
    suspended_at = db.Column(db.DateTime, nullable=True)
    suspended_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    # Email fields
    email_verified = db.Column(db.Boolean, default=False)
    welcome_email_sent = db.Column(db.Boolean, default=False)
    welcome_email_sent_at = db.Column(db.DateTime, nullable=True)

    # ==================== CUSTOMER PREMIUM FEATURE FIELDS ====================
    # These fields are for premium customers (Weekly, Monthly, Annual plans)
    company_name = db.Column(db.String(200), nullable=True)  # Company/Business name
    business_location = db.Column(db.String(200), nullable=True)  # Business location
    company_description = db.Column(db.Text, nullable=True)  # Company description for workers
    preferred_categories = db.Column(db.String(500), nullable=True)  # Preferred worker categories (comma-separated)
    budget_range = db.Column(db.String(100), nullable=True)  # Typical hiring budget range
    verified_only = db.Column(db.Boolean, default=False)  # Only show verified workers
    priority_listing = db.Column(db.Boolean, default=False)  # Priority job listing for jobs

    # Relationships
    worker_profile = db.relationship('WorkerProfile', backref='user', uselist=False, cascade='all, delete-orphan')
    jobs_posted = db.relationship('JobPost', backref='customer', cascade='all, delete-orphan')
    subscriptions = db.relationship('Subscription', backref='user', cascade='all, delete-orphan')
    payments = db.relationship('Payment', foreign_keys='Payment.user_id', back_populates='user')
    verified_payments = db.relationship('Payment', foreign_keys='Payment.verified_by', back_populates='verifier')
    reviews_given = db.relationship('Review', foreign_keys='Review.customer_id', back_populates='customer')
    reviews_received = db.relationship('Review', foreign_keys='Review.worker_id', back_populates='worker')
    job_applications = db.relationship('JobApplication', back_populates='worker', cascade='all, delete-orphan')
    success_stories = db.relationship('SuccessStory', back_populates='author', cascade='all, delete-orphan')
    reports = db.relationship('Report', foreign_keys='Report.reporter_id', back_populates='reporter', cascade='all, delete-orphan')
    resolved_reports = db.relationship('Report', foreign_keys='Report.resolved_by', back_populates='resolver')
    notifications = db.relationship('Notification', back_populates='recipient', cascade='all, delete-orphan')

    # Suspension relationship
    suspended_by_user = db.relationship('User', foreign_keys=[suspended_by], remote_side=[id])

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def get_active_subscription(self):
        """Get user's active subscription - PRIORITIZES PREMIUM PLANS"""
        # First try to get active premium subscription
        premium_sub = Subscription.query.filter(
            Subscription.user_id == self.id,
            Subscription.payment_status == 'completed',
            Subscription.is_active == True,
            Subscription.plan_type != 'free',
            Subscription.expires_at > datetime.utcnow()
        ).order_by(Subscription.expires_at.desc()).first()

        if premium_sub:
            return premium_sub

        # If no premium, check for free subscription that hasn't expired
        free_sub = Subscription.query.filter(
            Subscription.user_id == self.id,
            Subscription.payment_status == 'completed',
            Subscription.is_active == True,
            Subscription.plan_type == 'free'
        ).first()

        # Free subscription never expires (expires in 100 years), but still check
        if free_sub and free_sub.expires_at and free_sub.expires_at > datetime.utcnow():
            return free_sub

        # Return any active subscription as fallback
        return Subscription.query.filter(
            Subscription.user_id == self.id,
            Subscription.payment_status == 'completed',
            Subscription.is_active == True
        ).first()

    def has_premium(self):
        """Check if user has premium subscription"""
        sub = self.get_active_subscription()
        return sub and sub.plan_type != 'free' and sub.is_active

    def has_admin_access(self):
        """Check if user can access admin panel"""
        if self.is_admin:
            return True
        admin = User.query.filter_by(is_admin=True).first()
        if admin and admin.phone == self.phone:
            return True
        return False

    def is_suspended(self):
        return self.suspended

    def get_company_info(self):
        """Get company information for display (for customers)"""
        if self.user_type != 'customer':
            return None
        return {
            'company_name': self.company_name,
            'business_location': self.business_location,
            'company_description': self.company_description,
            'preferred_categories': self.preferred_categories.split(',') if self.preferred_categories else [],
            'budget_range': self.budget_range,
            'verified_only': self.verified_only,
            'priority_listing': self.priority_listing
        }

    def __repr__(self):
        return f'<User {self.name} ({self.phone})>'


class WorkerProfile(db.Model):
    """Worker profile with professional details"""
    __tablename__ = 'worker_profiles'
    __table_args__ = (
        db.Index('idx_worker_location', 'location'),
        db.Index('idx_worker_category', 'primary_category'),
        db.Index('idx_worker_rating', 'rating_score'),
        db.Index('idx_worker_available', 'is_available'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False, index=True)
    business_name = db.Column(db.String(100))
    location = db.Column(db.String(200), index=True)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    skills = db.Column(db.Text)
    primary_category = db.Column(db.String(50), default='general', index=True)
    secondary_categories = db.Column(db.Text)
    description = db.Column(db.Text)
    years_experience = db.Column(db.Integer, default=0)
    hourly_rate = db.Column(db.Float)
    portfolio_images = db.Column(db.Text)  # Comma-separated filenames
    cover_image = db.Column(db.String(200), default='default-cover.jpg')
    is_verified = db.Column(db.Boolean, default=False, index=True)
    is_available = db.Column(db.Boolean, default=True, index=True)
    verification_badge = db.Column(db.String(20), default='pending')
    total_jobs_completed = db.Column(db.Integer, default=0)
    response_time_avg = db.Column(db.Integer, default=60)
    rating_score = db.Column(db.Float, default=0.0)
    rating_count = db.Column(db.Integer, default=0)
    verified_at = db.Column(db.DateTime, nullable=True)
    verified_by = db.Column(db.Integer, nullable=True)

    # PREMIUM FEATURE FIELDS - Added for premium profiles
    certifications = db.Column(db.Text, nullable=True)  # JSON string of certifications
    whatsapp = db.Column(db.String(20), nullable=True)  # WhatsApp phone number
    facebook = db.Column(db.String(200), nullable=True)  # Facebook profile URL
    instagram = db.Column(db.String(100), nullable=True)  # Instagram handle
    twitter = db.Column(db.String(100), nullable=True)  # Twitter handle
    linkedin = db.Column(db.String(200), nullable=True)  # LinkedIn profile URL
    website = db.Column(db.String(200), nullable=True)  # Personal website URL

    def update_rating(self):
        """Update rating based on reviews"""
        try:
            reviews = Review.query.filter_by(worker_id=self.user_id).all()
            if reviews and len(reviews) > 0:
                self.rating_count = len(reviews)
                total_rating = sum(r.rating for r in reviews)
                self.rating_score = total_rating / len(reviews)
            else:
                self.rating_score = 0.0
                self.rating_count = 0
            db.session.commit()
        except Exception:
            db.session.rollback()
            self.rating_score = 0.0
            self.rating_count = 0
            db.session.commit()

    def get_rating(self):
        try:
            if self.rating_score is not None:
                return float(self.rating_score)
            return 0.0
        except:
            return 0.0

    def get_rating_count(self):
        try:
            if self.rating_count is not None:
                return int(self.rating_count)
            return 0
        except:
            return 0

    def is_verification_eligible(self):
        if not self.user:
            return False
        subscription = self.user.get_active_subscription()
        if not subscription:
            return False
        return subscription.plan_type in ['weekly', 'monthly', 'annual'] and subscription.is_active

    def get_certifications(self):
        """Get certifications as Python list"""
        if not self.certifications:
            return []
        try:
            return json.loads(self.certifications)
        except (json.JSONDecodeError, TypeError):
            return []

    def set_certifications(self, certs_list):
        """Set certifications from Python list"""
        if certs_list:
            self.certifications = json.dumps(certs_list)
        else:
            self.certifications = None

    def __repr__(self):
        return f'<WorkerProfile {self.business_name or self.user.name}>'


class Review(db.Model):
    """Customer reviews for workers"""
    __tablename__ = 'reviews'
    __table_args__ = (
        db.Index('idx_review_worker', 'worker_id'),
        db.Index('idx_review_created', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    job_id = db.Column(db.Integer, db.ForeignKey('job_posts.id'), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    worker = db.relationship('User', foreign_keys=[worker_id], back_populates='reviews_received')
    customer = db.relationship('User', foreign_keys=[customer_id], back_populates='reviews_given')
    job = db.relationship('JobPost', backref='reviews')

    def __repr__(self):
        return f'<Review {self.rating} for worker {self.worker_id}>'


class JobPost(db.Model):
    """Job postings from customers"""
    __tablename__ = 'job_posts'
    __table_args__ = (
        db.Index('idx_job_status', 'status'),
        db.Index('idx_job_category', 'category'),
        db.Index('idx_job_created', 'created_at'),
        db.Index('idx_job_deadline', 'deadline'),
    )

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(200), index=True)
    budget_min = db.Column(db.Float)
    budget_max = db.Column(db.Float)
    deadline = db.Column(db.DateTime, index=True)
    category = db.Column(db.String(50), default='general', index=True)
    skills_required = db.Column(db.Text)
    status = db.Column(db.String(20), default='open', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def get_applications_count(self):
        return JobApplication.query.filter_by(job_id=self.id).count()

    def is_expired(self):
        return self.deadline and datetime.utcnow() > self.deadline

    def can_apply(self):
        return self.status == 'open' and not self.is_expired()

    def __repr__(self):
        return f'<JobPost {self.title}>'


class JobApplication(db.Model):
    """Worker applications to jobs"""
    __tablename__ = 'job_applications'
    __table_args__ = (
        db.Index('idx_application_job', 'job_id'),
        db.Index('idx_application_worker', 'worker_id'),
        db.Index('idx_application_status', 'status'),
        db.UniqueConstraint('job_id', 'worker_id', name='unique_application'),
    )

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_posts.id'), nullable=False, index=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    bid_amount = db.Column(db.Float)
    message = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending', index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    job = db.relationship('JobPost', backref='applications')
    worker = db.relationship('User', foreign_keys=[worker_id], back_populates='job_applications')

    def __repr__(self):
        return f'<JobApplication Job {self.job_id}>'


class Subscription(db.Model):
    """User subscription plans with dynamic days remaining calculation"""
    __tablename__ = 'subscriptions'
    __table_args__ = (
        db.Index('idx_subscription_user', 'user_id'),
        db.Index('idx_subscription_status', 'payment_status'),
        db.Index('idx_subscription_expires', 'expires_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    plan_type = db.Column(db.String(20), nullable=False)  # 'free', 'daily', 'weekly', 'monthly', 'annual'
    amount_paid = db.Column(db.Float, nullable=False, default=0)
    transaction_id = db.Column(db.String(100))
    payment_status = db.Column(db.String(20), default='pending', index=True)  # 'pending', 'completed', 'failed'
    is_active = db.Column(db.Boolean, default=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=True, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def days_remaining(self):
        """Calculate days remaining until subscription expires"""
        if not self.expires_at:
            return 999

        now = datetime.utcnow()
        if self.expires_at <= now:
            return 0

        delta = self.expires_at - now
        return delta.days

    def hours_remaining(self):
        """Get hours remaining for more precise display"""
        if not self.expires_at:
            return None

        now = datetime.utcnow()
        if self.expires_at <= now:
            return 0

        delta = self.expires_at - now
        return delta.total_seconds() / 3600

    def is_expired(self):
        """Check if subscription has expired"""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    def __repr__(self):
        return f'<Subscription {self.plan_type}>'


class Payment(db.Model):
    """Payment transactions"""
    __tablename__ = 'payments'
    __table_args__ = (
        db.Index('idx_payment_user', 'user_id'),
        db.Index('idx_payment_status', 'status'),
        db.Index('idx_payment_date', 'payment_date'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    subscription_id = db.Column(db.Integer, db.ForeignKey('subscriptions.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    plan_type = db.Column(db.String(20), nullable=False)
    mpesa_transaction_id = db.Column(db.String(100), unique=True, index=True)
    mpesa_phone = db.Column(db.String(15))
    mpesa_receipt_number = db.Column(db.String(100))
    screenshot_path = db.Column(db.String(200))
    payment_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    status = db.Column(db.String(20), default='pending', index=True)
    payment_method = db.Column(db.String(20), default='mpesa')
    verified_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    verified_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', foreign_keys=[user_id], back_populates='payments')
    verifier = db.relationship('User', foreign_keys=[verified_by], back_populates='verified_payments')
    subscription = db.relationship('Subscription', backref='payment')

    def __repr__(self):
        return f'<Payment {self.mpesa_transaction_id}>'


class VerificationRequest(db.Model):
    """Worker verification requests"""
    __tablename__ = 'verification_requests'

    id = db.Column(db.Integer, primary_key=True)
    worker_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    verification_type = db.Column(db.String(50), nullable=False)
    evidence_path = db.Column(db.String(200))
    status = db.Column(db.String(20), default='pending', index=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime)
    comments = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    worker = db.relationship('User', foreign_keys=[worker_id], backref='verification_requests')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

    def __repr__(self):
        return f'<VerificationRequest for worker {self.worker_id}>'


class AuditLog(db.Model):
    """Audit log for admin actions"""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    user = db.relationship('User', backref='audit_logs')

    def __repr__(self):
        return f'<AuditLog {self.action}>'


class NewsletterSubscriber(db.Model):
    """Newsletter subscribers for email updates"""
    __tablename__ = 'newsletter_subscribers'
    __table_args__ = (
        db.Index('idx_newsletter_email', 'email'),
        db.Index('idx_newsletter_active', 'is_active'),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(100), unique=True, nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True, index=True)
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    unsubscribed_at = db.Column(db.DateTime, nullable=True)

    user = db.relationship('User', foreign_keys=[user_id], backref='newsletter_subscription')

    def __repr__(self):
        return f'<NewsletterSubscriber {self.email}>'


class SuccessStory(db.Model):
    """User success stories for the platform with dynamic profile picture support"""
    __tablename__ = 'success_stories'
    __table_args__ = (
        db.Index('idx_story_created', 'created_at'),
        db.Index('idx_story_approved', 'is_approved'),
        db.Index('idx_story_user', 'user_id'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=True)
    category = db.Column(db.String(50), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    story = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, default=5)
    is_approved = db.Column(db.Boolean, default=False, index=True)
    featured = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    approved_at = db.Column(db.DateTime, nullable=True)

    # Cache the profile picture at submission time, but will be updated dynamically
    profile_picture_cache = db.Column(db.String(200), nullable=True)

    author = db.relationship('User', foreign_keys=[user_id], back_populates='success_stories')

    def get_profile_picture(self):
        """Get the current profile picture of the author dynamically"""
        if self.user_id:
            user = User.query.get(self.user_id)
            if user and user.profile_picture and user.profile_picture != 'default-avatar.png':
                return user.profile_picture
        return self.profile_picture_cache if self.profile_picture_cache else None

    def get_avatar_initials(self):
        """Get initials for avatar fallback when no profile picture exists"""
        if not self.name:
            return '?'
        parts = self.name.split()
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return self.name[0].upper() if self.name else '?'

    def update_profile_picture_cache(self):
        """Update the cached profile picture to the user's current picture"""
        if self.user_id:
            user = User.query.get(self.user_id)
            if user:
                self.profile_picture_cache = user.profile_picture if user.profile_picture != 'default-avatar.png' else None
                return True
        return False

    def __repr__(self):
        return f'<SuccessStory {self.title} by {self.name}>'


class Notification(db.Model):
    """User notifications for system updates and alerts"""
    __tablename__ = 'notifications'
    __table_args__ = (
        db.Index('idx_notification_user', 'user_id'),
        db.Index('idx_notification_created', 'created_at'),
        db.Index('idx_notification_read', 'read'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    type = db.Column(db.String(20), default='info')  # 'info', 'success', 'warning', 'danger'
    read = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    # Use back_populates instead of backref to avoid naming conflicts
    recipient = db.relationship('User', foreign_keys=[user_id], back_populates='notifications')

    def mark_as_read(self):
        """Mark notification as read"""
        self.read = True
        db.session.commit()

    def __repr__(self):
        return f'<Notification {self.title}>'


class Report(db.Model):
    """Enhanced user reports for issues, scams, misconduct"""
    __tablename__ = 'reports'
    __table_args__ = (
        db.Index('idx_report_status', 'status'),
        db.Index('idx_report_created', 'created_at'),
        db.Index('idx_report_type', 'report_type'),
        db.Index('idx_report_priority', 'priority'),
        db.Index('idx_report_reporter', 'reporter_id'),
        db.Index('idx_report_resolved', 'resolved_at'),
    )

    id = db.Column(db.Integer, primary_key=True)

    # Reporter information
    reporter_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True, index=True)
    reporter_name = db.Column(db.String(100), nullable=True)
    reporter_email = db.Column(db.String(100), nullable=True)
    reporter_ip = db.Column(db.String(45), nullable=True)
    reporter_user_agent = db.Column(db.String(500), nullable=True)

    # Report details
    report_type = db.Column(db.String(50), nullable=False, index=True)
    issue_title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    related_id = db.Column(db.String(100), nullable=True, index=True)

    # ADDED: tracking_id field for report tracking
    tracking_id = db.Column(db.String(50), unique=True, nullable=True)

    # Priority and urgency
    priority = db.Column(db.String(20), default='medium', index=True)
    is_urgent = db.Column(db.Boolean, default=False)
    escalation_level = db.Column(db.Integer, default=1)

    # Status tracking
    status = db.Column(db.String(20), default='pending', index=True)
    status_history = db.Column(db.Text, nullable=True)

    # Resolution details
    resolved_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    resolved_at = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True)
    resolution_type = db.Column(db.String(50), nullable=True)

    # Action taken
    action_taken = db.Column(db.Text, nullable=True)
    action_taken_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action_taken_at = db.Column(db.DateTime, nullable=True)

    # Follow-up
    follow_up_required = db.Column(db.Boolean, default=False)
    follow_up_at = db.Column(db.DateTime, nullable=True)
    follow_up_notes = db.Column(db.Text, nullable=True)

    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    viewed_at = db.Column(db.DateTime, nullable=True)
    acknowledged_at = db.Column(db.DateTime, nullable=True)

    # Relationships
    reporter = db.relationship('User', foreign_keys=[reporter_id], back_populates='reports')
    resolver = db.relationship('User', foreign_keys=[resolved_by], back_populates='resolved_reports')
    action_taken_user = db.relationship('User', foreign_keys=[action_taken_by])

    def __init__(self, **kwargs):
        """Initialize report with additional logic"""
        super(Report, self).__init__(**kwargs)
        # Set is_urgent based on priority if it exists in kwargs
        priority_value = kwargs.get('priority', 'medium')
        if priority_value == 'urgent':
            self.is_urgent = True
            self.escalation_level = 4
        elif priority_value == 'high':
            self.escalation_level = 3
        elif priority_value == 'medium':
            self.escalation_level = 2
        else:
            self.escalation_level = 1

    def mark_as_resolved(self, resolver_id, resolution_notes, resolution_type='action_taken'):
        """Mark report as resolved"""
        self.status = 'resolved'
        self.resolved_by = resolver_id
        self.resolved_at = datetime.utcnow()
        self.resolution_notes = resolution_notes
        self.resolution_type = resolution_type
        self.updated_at = datetime.utcnow()
        self._add_status_history('resolved', f'Resolved by user {resolver_id}: {resolution_notes[:100]}')

    def mark_as_in_progress(self, admin_id):
        """Mark report as in progress"""
        self.status = 'in_progress'
        self.viewed_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._add_status_history('in_progress', f'Started processing by admin {admin_id}')

    def mark_as_acknowledged(self):
        """Mark report as acknowledged"""
        self.acknowledged_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._add_status_history('acknowledged', 'Report has been acknowledged')

    def add_action_taken(self, admin_id, action_description):
        """Add action taken for the report"""
        self.action_taken = action_description
        self.action_taken_by = admin_id
        self.action_taken_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
        self._add_status_history('action_taken', f'Action taken: {action_description[:100]}')

    def set_follow_up(self, follow_up_at, follow_up_notes):
        """Set follow-up requirement"""
        self.follow_up_required = True
        self.follow_up_at = follow_up_at
        self.follow_up_notes = follow_up_notes
        self.updated_at = datetime.utcnow()

    def _add_status_history(self, status, note):
        """Add entry to status history"""
        history_entry = {
            'status': status,
            'note': note,
            'timestamp': datetime.utcnow().isoformat()
        }

        current_history = []
        if self.status_history:
            try:
                current_history = json.loads(self.status_history)
            except:
                current_history = []

        current_history.append(history_entry)
        self.status_history = json.dumps(current_history)

    def get_status_history(self):
        """Get status history as list"""
        if not self.status_history:
            return []
        try:
            return json.loads(self.status_history)
        except:
            return []

    def get_priority_color(self):
        """Get priority color for UI display"""
        colors = {
            'low': '#10B981',
            'medium': '#F59E0B',
            'high': '#EF4444',
            'urgent': '#7C3AED'
        }
        return colors.get(self.priority, '#6B7280')

    def get_time_to_resolution(self):
        """Get time taken to resolve report"""
        if not self.resolved_at:
            return None
        return (self.resolved_at - self.created_at).total_seconds() / 3600

    def is_overdue(self):
        """Check if report is overdue based on priority"""
        if self.status in ['resolved', 'dismissed']:
            return False

        sla_hours = {
            'urgent': 24,
            'high': 48,
            'medium': 72,
            'low': 120
        }

        hours_passed = (datetime.utcnow() - self.created_at).total_seconds() / 3600
        return hours_passed > sla_hours.get(self.priority, 72)

    def __repr__(self):
        return f'<Report {self.id}: {self.report_type} - {self.status}>'
