"""Unit tests for email service"""
import pytest
from unittest.mock import patch, MagicMock


class TestEmailService:
    """Tests for EmailService class"""

    def test_is_configured_returns_false_when_not_configured(self):
        """Test that is_configured returns False when SMTP is not set up"""
        with patch('app.services.email.settings') as mock_settings:
            mock_settings.SMTP_HOST = None
            mock_settings.FROM_EMAIL = None

            from app.services.email import EmailService
            service = EmailService()

            assert service.is_configured() is False

    def test_is_configured_returns_true_when_configured(self):
        """Test that is_configured returns True when SMTP is set up"""
        with patch('app.services.email.settings') as mock_settings:
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = None
            mock_settings.SMTP_PASSWORD = None
            mock_settings.SMTP_TLS = True
            mock_settings.FROM_EMAIL = "test@example.com"
            mock_settings.FROM_NAME = "Test App"

            from app.services.email import EmailService
            service = EmailService()

            assert service.is_configured() is True

    def test_send_email_returns_false_when_not_configured(self):
        """Test that send_email returns False when not configured"""
        with patch('app.services.email.settings') as mock_settings:
            mock_settings.SMTP_HOST = None
            mock_settings.FROM_EMAIL = None

            from app.services.email import EmailService
            service = EmailService()

            result = service.send_email(
                to_email="test@example.com",
                subject="Test",
                html_body="<p>Test</p>"
            )

            assert result is False

    @patch('app.services.email.smtplib.SMTP')
    def test_send_email_with_tls(self, mock_smtp):
        """Test sending email with TLS"""
        mock_server = MagicMock()
        mock_smtp.return_value = mock_server

        with patch('app.services.email.settings') as mock_settings:
            mock_settings.SMTP_HOST = "smtp.example.com"
            mock_settings.SMTP_PORT = 587
            mock_settings.SMTP_USER = "user"
            mock_settings.SMTP_PASSWORD = "pass"
            mock_settings.SMTP_TLS = True
            mock_settings.FROM_EMAIL = "sender@example.com"
            mock_settings.FROM_NAME = "Test App"

            from app.services.email import EmailService
            service = EmailService()

            result = service.send_email(
                to_email="recipient@example.com",
                subject="Test Subject",
                html_body="<p>Hello</p>",
                text_body="Hello"
            )

            assert result is True
            mock_smtp.assert_called_once_with("smtp.example.com", 587)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user", "pass")
            mock_server.sendmail.assert_called_once()
            mock_server.quit.assert_called_once()

    def test_send_password_reset_email(self):
        """Test password reset email generation"""
        with patch('app.services.email.settings') as mock_settings:
            mock_settings.SMTP_HOST = None
            mock_settings.FROM_EMAIL = None
            mock_settings.APP_NAME = "Test App"

            from app.services.email import EmailService
            service = EmailService()

            # Mock the send_email method
            service.send_email = MagicMock(return_value=True)

            result = service.send_password_reset_email(
                to_email="user@example.com",
                reset_token="test-token-123",
                reset_url="https://example.com/reset"
            )

            # Verify send_email was called with correct parameters
            service.send_email.assert_called_once()
            call_args = service.send_email.call_args

            # Check positional args (to_email, subject, html_body, text_body)
            args = call_args[0]
            assert args[0] == "user@example.com"  # to_email
            assert "Password Reset" in args[1]  # subject
            assert "test-token-123" in args[2]  # html_body
            assert "https://example.com/reset" in args[2]  # html_body


class TestGetEmailService:
    """Tests for get_email_service singleton"""

    def test_get_email_service_returns_singleton(self):
        """Test that get_email_service returns the same instance"""
        from app.services.email import get_email_service, _email_service

        # Reset the singleton
        import app.services.email as email_module
        email_module._email_service = None

        service1 = get_email_service()
        service2 = get_email_service()

        assert service1 is service2
