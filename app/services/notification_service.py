import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, Dict, List
import logging
from app.config import settings
from datetime import datetime

logger = logging.getLogger(__name__)

class NotificationService:
    """Service for sending notifications (email, push, etc.)"""
    
    def __init__(self):
        self.smtp_configured = all([
            settings.SMTP_SERVER,
            settings.SMTP_USERNAME,
            settings.SMTP_PASSWORD,
            settings.EMAIL_FROM
        ])
        
        if not self.smtp_configured:
            logger.warning("SMTP not configured. Email notifications disabled.")
    
    async def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        html: Optional[str] = None
    ) -> bool:
        """
        Send email notification
        
        Args:
            to_email: Recipient email
            subject: Email subject
            body: Plain text body
            html: Optional HTML body
            
        Returns:
            True if sent successfully, False otherwise
        """
        if not self.smtp_configured:
            logger.warning("Cannot send email: SMTP not configured")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart('alternative')
            msg['From'] = settings.EMAIL_FROM
            msg['To'] = to_email
            msg['Subject'] = subject
            
            # Attach plain text
            part1 = MIMEText(body, 'plain')
            msg.attach(part1)
            
            # Attach HTML if provided
            if html:
                part2 = MIMEText(html, 'html')
                msg.attach(part2)
            
            # Send email
            with smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                server.send_message(msg)
            
            logger.info(f"Email sent to {to_email}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def send_welcome_email(self, user_email: str, username: str) -> bool:
        """Send welcome email to new user"""
        subject = f"Welcome to {settings.APP_NAME}!"
        
        body = f"""
        Hi {username},
        
        Welcome to {settings.APP_NAME}!
        
        We're excited to have you on board. Start building your digital closet
        and get AI-powered outfit suggestions today!
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        html = f"""
        <html>
          <body>
            <h2>Hi {username},</h2>
            <p>Welcome to <strong>{settings.APP_NAME}</strong>!</p>
            <p>We're excited to have you on board. Start building your digital closet
            and get AI-powered outfit suggestions today!</p>
            <p>Best regards,<br>The {settings.APP_NAME} Team</p>
          </body>
        </html>
        """
        
        return await self.send_email(user_email, subject, body, html)
    
    async def send_password_reset_email(
        self,
        user_email: str,
        reset_token: str
    ) -> bool:
        """Send password reset email"""
        subject = f"Password Reset - {settings.APP_NAME}"
        
        # In production, use your actual app URL
        reset_link = f"https://yourapp.com/reset-password?token={reset_token}"
        
        body = f"""
        You requested a password reset for your {settings.APP_NAME} account.
        
        Click the link below to reset your password:
        {reset_link}
        
        This link will expire in 1 hour.
        
        If you didn't request this, please ignore this email.
        """
        
        html = f"""
        <html>
          <body>
            <p>You requested a password reset for your {settings.APP_NAME} account.</p>
            <p><a href="{reset_link}">Click here to reset your password</a></p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request this, please ignore this email.</p>
          </body>
        </html>
        """
        
        return await self.send_email(user_email, subject, body, html)
    
    async def send_outfit_suggestion_notification(
        self,
        user_email: str,
        username: str,
        outfit_count: int
    ) -> bool:
        """Notify user about new outfit suggestions"""
        subject = f"New Outfit Suggestions for You!"
        
        body = f"""
        Hi {username},
        
        We've created {outfit_count} new outfit suggestions based on your wardrobe!
        
        Check them out in the app now.
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        html = f"""
        <html>
          <body>
            <h2>Hi {username},</h2>
            <p>We've created <strong>{outfit_count}</strong> new outfit suggestions based on your wardrobe!</p>
            <p>Check them out in the app now.</p>
            <p>Best regards,<br>The {settings.APP_NAME} Team</p>
          </body>
        </html>
        """
        
        return await self.send_email(user_email, subject, body, html)
    
    async def send_weekly_summary(
        self,
        user_email: str,
        username: str,
        stats: Dict
    ) -> bool:
        """Send weekly activity summary"""
        subject = f"Your Weekly Fashion Summary - {settings.APP_NAME}"
        
        items_added = stats.get('items_added', 0)
        outfits_created = stats.get('outfits_created', 0)
        
        body = f"""
        Hi {username},
        
        Here's your weekly summary:
        
        - Clothing items added: {items_added}
        - Outfits created: {outfits_created}
        
        Keep building your digital wardrobe!
        
        Best regards,
        The {settings.APP_NAME} Team
        """
        
        html = f"""
        <html>
          <body>
            <h2>Hi {username},</h2>
            <p>Here's your weekly summary:</p>
            <ul>
              <li>Clothing items added: <strong>{items_added}</strong></li>
              <li>Outfits created: <strong>{outfits_created}</strong></li>
            </ul>
            <p>Keep building your digital wardrobe!</p>
            <p>Best regards,<br>The {settings.APP_NAME} Team</p>
          </body>
        </html>
        """
        
        return await self.send_email(user_email, subject, body, html)
    
    async def send_push_notification(
        self,
        user_id: str,
        title: str,
        body: str,
        data: Optional[Dict] = None
    ) -> bool:
        """
        Send push notification (placeholder for FCM/APNS integration)
        
        To implement:
        1. Install firebase-admin or similar
        2. Store device tokens in user model
        3. Send push using FCM/APNS
        """
        logger.info(f"Push notification to user {user_id}: {title}")
        
        # TODO: Implement FCM/APNS push notification
        # Example with Firebase:
        # from firebase_admin import messaging
        # message = messaging.Message(
        #     notification=messaging.Notification(title=title, body=body),
        #     data=data or {},
        #     token=user_device_token
        # )
        # response = messaging.send(message)
        
        return True
    
    async def send_bulk_notification(
        self,
        user_emails: List[str],
        subject: str,
        body: str,
        html: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Send notification to multiple users
        
        Returns:
            Dict with 'sent' and 'failed' counts
        """
        sent = 0
        failed = 0
        
        for email in user_emails:
            success = await self.send_email(email, subject, body, html)
            if success:
                sent += 1
            else:
                failed += 1
        
        logger.info(f"Bulk notification: {sent} sent, {failed} failed")
        
        return {
            "sent": sent,
            "failed": failed,
            "total": len(user_emails)
        }
    
    async def log_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        body: str,
        status: str = "sent"
    ):
        """
        Log notification to database for tracking
        
        Args:
            user_id: Recipient user ID
            notification_type: Type (email, push, etc.)
            title: Notification title
            body: Notification body
            status: Status (sent, failed, pending)
        """
        from app.database import get_database
        
        try:
            db = get_database()
            
            notification_log = {
                "user_id": user_id,
                "type": notification_type,
                "title": title,
                "body": body,
                "status": status,
                "created_at": datetime.utcnow(),
                "read": False
            }
            
            await db.notifications.insert_one(notification_log)
            logger.info(f"Notification logged for user {user_id}")
        
        except Exception as e:
            logger.error(f"Failed to log notification: {e}")


# Singleton instance
notification_service = NotificationService()