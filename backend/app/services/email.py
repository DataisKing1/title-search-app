"""Email service for sending application emails"""
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List

from app.config import settings

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails via SMTP"""

    def __init__(self):
        self.smtp_host = settings.SMTP_HOST
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
        self.use_tls = settings.SMTP_TLS
        self.from_email = settings.FROM_EMAIL
        self.from_name = settings.FROM_NAME

    def is_configured(self) -> bool:
        """Check if email settings are properly configured"""
        return all([
            self.smtp_host,
            self.from_email
        ])

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: Optional[str] = None
    ) -> bool:
        """
        Send an email.

        Args:
            to_email: Recipient email address
            subject: Email subject
            html_body: HTML content of the email
            text_body: Plain text fallback (optional)

        Returns:
            bool: True if email was sent successfully
        """
        if not self.is_configured():
            logger.warning("Email not configured. Skipping email send.")
            return False

        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email

            # Add text and HTML parts
            if text_body:
                msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Connect and send
            if self.use_tls:
                server = smtplib.SMTP(self.smtp_host, self.smtp_port)
                server.starttls()
            else:
                server = smtplib.SMTP_SSL(self.smtp_host, self.smtp_port)

            if self.smtp_user and self.smtp_password:
                server.login(self.smtp_user, self.smtp_password)

            server.sendmail(self.from_email, to_email, msg.as_string())
            server.quit()

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email to {to_email}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {e}")
            return False

    def send_password_reset_email(self, to_email: str, reset_token: str, reset_url: str = None) -> bool:
        """
        Send password reset email.

        Args:
            to_email: Recipient email address
            reset_token: The password reset token
            reset_url: Optional base URL for the reset link

        Returns:
            bool: True if email was sent successfully
        """
        # Default reset URL if not provided
        if not reset_url:
            reset_url = "http://localhost:5173/reset-password"

        # Construct full reset link
        reset_link = f"{reset_url}?token={reset_token}"

        subject = f"{settings.APP_NAME} - Password Reset Request"

        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2563eb;">Password Reset Request</h2>

                <p>You have requested to reset your password for your {settings.APP_NAME} account.</p>

                <p>Click the button below to reset your password:</p>

                <p style="text-align: center; margin: 30px 0;">
                    <a href="{reset_link}"
                       style="background-color: #2563eb; color: white; padding: 12px 24px;
                              text-decoration: none; border-radius: 4px; display: inline-block;">
                        Reset Password
                    </a>
                </p>

                <p>Or copy and paste this link into your browser:</p>
                <p style="background-color: #f3f4f6; padding: 10px; border-radius: 4px; word-break: break-all;">
                    {reset_link}
                </p>

                <p><strong>This link will expire in 1 hour.</strong></p>

                <p>If you did not request a password reset, please ignore this email or contact support
                   if you have concerns about your account security.</p>

                <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 30px 0;">

                <p style="color: #6b7280; font-size: 12px;">
                    This email was sent by {settings.APP_NAME}.
                    Please do not reply to this email.
                </p>
            </div>
        </body>
        </html>
        """

        text_body = f"""
Password Reset Request

You have requested to reset your password for your {settings.APP_NAME} account.

To reset your password, visit the following link:
{reset_link}

This link will expire in 1 hour.

If you did not request a password reset, please ignore this email or contact support
if you have concerns about your account security.

This email was sent by {settings.APP_NAME}.
        """

        return self.send_email(to_email, subject, html_body, text_body)


# Singleton instance
_email_service: Optional[EmailService] = None


def get_email_service() -> EmailService:
    """Get or create the email service singleton"""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
