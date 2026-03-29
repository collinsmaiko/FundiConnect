"""
FundiConnect - Background Scheduler for Subscription Expiration Checks
This script runs in the background to check and expire subscriptions automatically
"""

import time
import threading
import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_expired_subscriptions():
    """
    Check for expired subscriptions and deactivate them
    Also remove verification badges from users whose premium expired

    This function runs within the Flask application context
    """
    try:
        from app import app, db, Subscription, WorkerProfile, VerificationRequest, notify_admin, send_subscription_expired_email

        with app.app_context():
            now = datetime.utcnow()

            # Find expired subscriptions that are still marked as active
            expired_subs = Subscription.query.filter(
                Subscription.is_active == True,
                Subscription.payment_status == 'completed',
                Subscription.plan_type != 'free',
                Subscription.expires_at <= now
            ).all()

            expired_count = 0

            for sub in expired_subs:
                logger.info(f"Expiring subscription: User {sub.user.name} - Plan: {sub.plan_type} - Expired: {sub.expires_at}")

                # Deactivate the subscription
                sub.is_active = False

                # Remove verification badge if this was a premium subscription
                if sub.user.user_type == 'worker' and sub.user.worker_profile:
                    worker = sub.user.worker_profile

                    # Check if they have another active premium subscription
                    has_other_active = Subscription.query.filter(
                        Subscription.user_id == sub.user.id,
                        Subscription.is_active == True,
                        Subscription.payment_status == 'completed',
                        Subscription.plan_type != 'free',
                        Subscription.id != sub.id
                    ).first()

                    if not has_other_active:
                        # No other active premium subscription, remove verification
                        if worker.is_verified:
                            logger.info(f"Removing verification badge for user {sub.user.name} due to subscription expiry")
                            worker.is_verified = False
                            worker.verification_badge = 'expired'

                            # Mark any approved verification requests as expired
                            VerificationRequest.query.filter_by(
                                worker_id=sub.user.id,
                                status='approved'
                            ).update({'status': 'expired'})

                            # Notify admin about verification removal
                            notify_admin(
                                title='⚠️ Verification Badge Removed',
                                message=f'Verification badge for {sub.user.name} has been automatically removed due to subscription expiry.',
                                type='warning',
                                user_id=sub.user.id,
                                user_name=sub.user.name
                            )

                # Send expiration notification email
                if sub.user.email and app.config.get('SEND_EMAILS', True):
                    try:
                        send_subscription_expired_email(sub.user, sub.plan_type)
                        logger.info(f"Expiration email sent to {sub.user.email}")
                    except Exception as e:
                        logger.error(f"Failed to send expiration email to {sub.user.email}: {e}")

                expired_count += 1

                # Notify admin
                notify_admin(
                    title='⏰ Subscription Expired',
                    message=f'{sub.user.name}\'s {sub.plan_type.upper()} subscription has expired. User reverted to free plan.',
                    type='warning',
                    user_id=sub.user.id,
                    user_name=sub.user.name
                )

            # Commit all changes
            if expired_count > 0:
                db.session.commit()
                logger.info(f"✅ Expired {expired_count} subscriptions")

            # Also check for subscriptions expiring in the next 3 days to send reminders
            reminder_threshold = datetime.utcnow() + timedelta(days=3)
            expiring_soon_subs = Subscription.query.filter(
                Subscription.is_active == True,
                Subscription.payment_status == 'completed',
                Subscription.plan_type != 'free',
                Subscription.expires_at <= reminder_threshold,
                Subscription.expires_at > datetime.utcnow()
            ).all()

            reminder_count = 0
            for sub in expiring_soon_subs:
                days_left = (sub.expires_at - datetime.utcnow()).days
                # Send reminder at 3 days and 1 day before expiry
                if days_left == 3 or days_left == 1:
                    logger.info(f"Sending expiry reminder to {sub.user.name} - {days_left} days left")
                    send_expiry_reminder_email(sub.user, sub.plan_type, days_left)
                    reminder_count += 1

            if reminder_count > 0:
                logger.info(f"Sent {reminder_count} expiry reminder emails")

            return expired_count

    except Exception as e:
        logger.error(f"Error checking expired subscriptions: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return 0


def send_expiry_reminder_email(user, plan_type, days_left):
    """Send reminder email to user about upcoming subscription expiry"""
    if not user.email:
        return False

    try:
        from app import send_email, load_settings, url_for

        settings = load_settings()

        # Determine urgency based on days left
        if days_left == 1:
            urgency = "⚠️ URGENT: "
            emoji = "🔴"
            button_color = "#EF4444"
        else:
            urgency = ""
            emoji = "🟡"
            button_color = "#F59E0B"

        # Create email context
        context = {
            'user_name': user.name,
            'plan_type': plan_type.upper(),
            'days_left': days_left,
            'expiry_date': user.get_active_subscription().expires_at.strftime('%B %d, %Y') if user.get_active_subscription() else 'soon',
            'platform_name': settings.get('platform_name', 'FundiConnect'),
            'pricing_url': url_for('pricing', _external=True),
            'renew_url': url_for('subscribe', _external=True),
            'urgency': urgency,
            'emoji': emoji,
            'button_color': button_color
        }

        subject = f"{urgency}Your {plan_type.upper()} Subscription Expires in {days_left} Day{'s' if days_left > 1 else ''}"

        # Send email using the subscription_expired template with reminder context
        return send_email(user.email, subject, 'subscription_expired.html', context)

    except Exception as e:
        logger.error(f"Failed to send expiry reminder to {user.email}: {e}")
        return False


def subscription_scheduler_worker():
    """
    Background worker that runs the subscription check every hour
    """
    while True:
        try:
            logger.info("Running subscription expiration check...")
            expired = check_expired_subscriptions()
            if expired > 0:
                logger.info(f"Subscription check completed: {expired} subscriptions expired")
            else:
                logger.info("Subscription check completed: No expired subscriptions found")
        except Exception as e:
            logger.error(f"Subscription scheduler error: {e}")
            import traceback
            logger.error(traceback.format_exc())

        # Sleep for 1 hour (3600 seconds)
        time.sleep(3600)


def start_subscription_scheduler():
    """
    Start the subscription scheduler in a background thread
    """
    try:
        scheduler_thread = threading.Thread(target=subscription_scheduler_worker, daemon=True)
        scheduler_thread.start()
        logger.info("✅ Subscription expiration scheduler started successfully")
        return scheduler_thread
    except Exception as e:
        logger.error(f"Failed to start subscription scheduler: {e}")
        return None


def run_subscription_check_once():
    """
    Run a one-time subscription check (useful for manual testing or cron jobs)
    """
    try:
        from app import app
        with app.app_context():
            logger.info("Running one-time subscription check...")
            expired = check_expired_subscriptions()
            logger.info(f"One-time check completed: {expired} subscriptions expired")
            return expired
    except Exception as e:
        logger.error(f"One-time check error: {e}")
        return 0


# If run directly, start the scheduler
if __name__ == '__main__':
    print("=" * 60)
    print("FundiConnect Subscription Scheduler")
    print("=" * 60)
    print("This script runs in the background checking for expired subscriptions.")
    print("It will check every hour and send email reminders.")
    print("Press Ctrl+C to stop.")
    print("=" * 60)

    try:
        # Import app to ensure database connection
        from app import app

        # Start the scheduler
        scheduler = start_subscription_scheduler()

        if scheduler:
            print("\n✅ Scheduler started successfully!")
            print("📧 Email reminders will be sent 3 days and 1 day before expiry")
            print("🕐 Checking for expired subscriptions every hour...")
        else:
            print("\n❌ Failed to start scheduler.")

        # Keep the main thread alive
        while True:
            time.sleep(60)

    except KeyboardInterrupt:
        print("\n\n🛑 Scheduler stopped by user.")
        print("Thank you for using FundiConnect Subscription Scheduler!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
