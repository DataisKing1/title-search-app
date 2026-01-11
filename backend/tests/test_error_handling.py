"""Tests for error handling service"""
import pytest
from datetime import datetime

from app.services.error_handling import (
    ErrorHandler,
    ErrorCategory,
    RecoveryAction,
    SearchRecoveryManager,
    error_handler,
    recovery_manager,
)


class TestErrorCategorization:
    """Test error categorization"""

    def test_network_errors(self):
        """Test network error detection"""
        network_errors = [
            "connection refused",
            "Connection timed out",
            "ERR_CONNECTION_RESET",
            "socket error",
            "DNS resolution failed",
        ]
        for error in network_errors:
            category = error_handler.categorize_error(error)
            assert category in [ErrorCategory.NETWORK, ErrorCategory.TIMEOUT], \
                f"Expected network/timeout for '{error}', got {category}"

    def test_timeout_errors(self):
        """Test timeout error detection"""
        timeout_errors = [
            "Operation timed out",
            "TimeoutError: Connection",
            "Request took too long",
            "Deadline exceeded",
        ]
        for error in timeout_errors:
            category = error_handler.categorize_error(error)
            assert category == ErrorCategory.TIMEOUT, \
                f"Expected TIMEOUT for '{error}', got {category}"

    def test_rate_limit_errors(self):
        """Test rate limit detection"""
        rate_limit_errors = [
            "Rate limit exceeded",
            "429 Too Many Requests",
            "Request throttled",
            "API quota exceeded",
        ]
        for error in rate_limit_errors:
            category = error_handler.categorize_error(error)
            assert category == ErrorCategory.RATE_LIMIT, \
                f"Expected RATE_LIMIT for '{error}', got {category}"

    def test_auth_errors(self):
        """Test authentication error detection"""
        auth_errors = [
            "401 Unauthorized",
            "403 Forbidden",
            "Login required",
            "Session expired",
            "Authentication failed",
        ]
        for error in auth_errors:
            category = error_handler.categorize_error(error)
            assert category == ErrorCategory.AUTHENTICATION, \
                f"Expected AUTHENTICATION for '{error}', got {category}"

    def test_scraping_errors(self):
        """Test scraping error detection"""
        scraping_errors = [
            "404 Page not found",
            "No results found on page",
            "Website under maintenance",
            "Captcha required",
            "Bot detection triggered",
        ]
        for error in scraping_errors:
            category = error_handler.categorize_error(error)
            assert category == ErrorCategory.SCRAPING, \
                f"Expected SCRAPING for '{error}', got {category}"

    def test_database_errors(self):
        """Test database error detection"""
        db_errors = [
            "Database connection failed",
            "SQL error in query",
            "Postgres connection pool exhausted",
            "Deadlock detected",
            "Integrity constraint violated",
        ]
        for error in db_errors:
            category = error_handler.categorize_error(error)
            assert category == ErrorCategory.DATABASE, \
                f"Expected DATABASE for '{error}', got {category}"

    def test_ai_service_errors(self):
        """Test AI service error detection"""
        ai_errors = [
            "OpenAI API error",
            "Anthropic API error",
            "Invalid OpenAI API key",
            "OpenAI model not found",
            "OpenAI context length exceeded",
        ]
        for error in ai_errors:
            category = error_handler.categorize_error(error)
            assert category == ErrorCategory.AI_SERVICE, \
                f"Expected AI_SERVICE for '{error}', got {category}"

    def test_unknown_errors(self):
        """Test unknown error fallback"""
        unknown_errors = [
            "Something went wrong",
            "Unexpected issue occurred",
            "Random failure 12345",
        ]
        for error in unknown_errors:
            category = error_handler.categorize_error(error)
            assert category == ErrorCategory.UNKNOWN, \
                f"Expected UNKNOWN for '{error}', got {category}"


class TestErrorDiagnosis:
    """Test error diagnosis"""

    def test_transient_errors(self):
        """Test transient error detection"""
        handler = ErrorHandler()

        # Network errors are transient
        diag = handler.diagnose_error("Connection refused", "test_task")
        assert diag.is_transient is True
        assert diag.max_retries > 0

        # Rate limit errors are transient
        diag = handler.diagnose_error("429 Too Many Requests", "test_task")
        assert diag.is_transient is True

        # Timeout errors are transient
        diag = handler.diagnose_error("Operation timed out", "test_task")
        assert diag.is_transient is True

    def test_non_transient_errors(self):
        """Test non-transient error detection"""
        handler = ErrorHandler()

        # Auth errors are not transient
        diag = handler.diagnose_error("Authentication failed", "test_task")
        assert diag.is_transient is False

        # Scraping errors are not transient
        diag = handler.diagnose_error("Captcha required", "test_task")
        assert diag.is_transient is False

    def test_severity_levels(self):
        """Test severity level assignment"""
        handler = ErrorHandler()

        # Critical severity
        diag = handler.diagnose_error("Database deadlock", "test_task")
        assert diag.severity == "critical"

        # High severity
        diag = handler.diagnose_error("Authentication failed", "test_task")
        assert diag.severity == "high"

        # Medium severity
        diag = handler.diagnose_error("Connection refused", "test_task")
        assert diag.severity == "medium"

        # Low severity
        diag = handler.diagnose_error("Rate limit exceeded", "test_task")
        assert diag.severity == "low"

    def test_retry_delay(self):
        """Test retry delay calculation"""
        handler = ErrorHandler()

        # Network errors have moderate delay
        diag = handler.diagnose_error("Connection refused", "test_task")
        assert diag.retry_delay_seconds == 30

        # Rate limit has longer delay
        diag = handler.diagnose_error("Rate limit exceeded", "test_task")
        assert diag.retry_delay_seconds == 300

        # Database errors have short delay
        diag = handler.diagnose_error("Database connection failed", "test_task")
        assert diag.retry_delay_seconds == 5

    def test_recovery_actions(self):
        """Test recovery action recommendations"""
        handler = ErrorHandler()

        # Transient errors suggest retry
        diag = handler.diagnose_error("Connection refused", "test_task")
        assert RecoveryAction.RETRY_WITH_DELAY in diag.recovery_actions

        # Auth errors suggest manual review
        diag = handler.diagnose_error("Authentication failed", "test_task")
        assert RecoveryAction.MANUAL_REVIEW in diag.recovery_actions


class TestErrorLogEntry:
    """Test error log entry creation"""

    def test_create_error_entry(self):
        """Test error log entry structure"""
        handler = ErrorHandler()

        entry = handler.create_error_entry(
            "Connection refused",
            "scrape_county_recorder"
        )

        assert "timestamp" in entry
        assert entry["task"] == "scrape_county_recorder"
        assert entry["error"] == "Connection refused"
        assert entry["category"] == "network"
        assert "severity" in entry
        assert "is_transient" in entry
        assert "recommended_action" in entry


class TestRetryLogic:
    """Test retry decision logic"""

    def test_should_retry_transient(self):
        """Test retry for transient errors"""
        handler = ErrorHandler()

        should_retry, delay = handler.should_retry("Connection refused", 0)
        assert should_retry is True
        assert delay > 0

    def test_should_not_retry_non_transient(self):
        """Test no retry for non-transient errors"""
        handler = ErrorHandler()

        should_retry, delay = handler.should_retry("Authentication failed", 0)
        assert should_retry is False

    def test_should_not_retry_max_attempts(self):
        """Test no retry after max attempts"""
        handler = ErrorHandler()

        # After too many retries, even transient errors shouldn't retry
        should_retry, delay = handler.should_retry("Connection refused", 10)
        assert should_retry is False

    def test_exponential_backoff(self):
        """Test exponential backoff in retry delay"""
        handler = ErrorHandler()

        # Use database error which has max_retries=5
        _, delay0 = handler.should_retry("Database connection failed", 0, max_retries=5)
        _, delay1 = handler.should_retry("Database connection failed", 1, max_retries=5)
        _, delay2 = handler.should_retry("Database connection failed", 2, max_retries=5)

        # Delays should increase (exponential backoff)
        assert delay1 > delay0
        assert delay2 > delay1


class TestRecoverySuggestions:
    """Test recovery suggestion generation"""

    def test_network_error_suggestions(self):
        """Test suggestions for network errors"""
        handler = ErrorHandler()

        error_log = [
            {"category": "network", "error": "Connection refused", "severity": "medium"}
        ]
        suggestions = handler.get_recovery_suggestions(error_log)

        assert len(suggestions["suggestions"]) > 0
        assert suggestions["can_retry"] is True
        assert "network" in str(suggestions["suggestions"]).lower()

    def test_scraping_error_suggestions(self):
        """Test suggestions for scraping errors"""
        handler = ErrorHandler()

        error_log = [
            {"category": "scraping", "error": "Captcha required", "severity": "high"}
        ]
        suggestions = handler.get_recovery_suggestions(error_log)

        assert len(suggestions["suggestions"]) > 0
        assert suggestions["can_retry"] is False

    def test_consecutive_failure_detection(self):
        """Test detection of consecutive failures"""
        handler = ErrorHandler()

        error_log = [
            {"category": "network", "severity": "high", "error": "Error 1"},
            {"category": "network", "severity": "high", "error": "Error 2"},
            {"category": "network", "severity": "high", "error": "Error 3"},
        ]
        suggestions = handler.get_recovery_suggestions(error_log)

        assert suggestions["error_summary"]["consecutive_failures"] == 3
        assert suggestions["can_retry"] is False


class TestSearchRecoveryManager:
    """Test search recovery management"""

    def test_get_last_successful_step(self):
        """Test identifying last successful step"""
        manager = SearchRecoveryManager()

        # Error in scraping means initialization was successful
        error_log = [
            {"task": "scrape_county_recorder", "error": "Failed"}
        ]
        last_step = manager.get_last_successful_step(error_log)
        assert last_step == "orchestrate_search"

        # Error in analysis means scraping was successful
        error_log = [
            {"task": "analyze_all_documents", "error": "Failed"}
        ]
        last_step = manager.get_last_successful_step(error_log)
        assert last_step == "download_all_documents"

    def test_get_resume_step(self):
        """Test identifying resume step"""
        manager = SearchRecoveryManager()

        # After scraping error, resume from scraping
        error_log = [
            {"task": "scrape_county_recorder", "error": "Failed"}
        ]
        resume_step = manager.get_resume_step(error_log)
        assert resume_step == "scrape_county_recorder"

        # After analysis error, resume from analysis
        error_log = [
            {"task": "analyze_all_documents", "error": "Failed"}
        ]
        resume_step = manager.get_resume_step(error_log)
        assert resume_step == "analyze_all_documents"

    def test_can_resume_failed_search(self):
        """Test can_resume for failed searches"""
        manager = SearchRecoveryManager()

        error_log = [
            {"task": "scrape_county_recorder", "error": "Timeout", "category": "timeout"}
        ]
        can_resume, reason = manager.can_resume("failed", error_log, 0)
        assert can_resume is True

    def test_cannot_resume_max_retries(self):
        """Test cannot resume after max retries"""
        manager = SearchRecoveryManager()

        error_log = [
            {"task": "scrape_county_recorder", "error": "Timeout"}
        ]
        can_resume, reason = manager.can_resume("failed", error_log, 5)
        assert can_resume is False
        assert "Maximum" in reason

    def test_get_recovery_options(self):
        """Test recovery options generation"""
        manager = SearchRecoveryManager()

        error_log = [
            {"task": "scrape_county_recorder", "error": "Timeout", "category": "timeout"}
        ]
        options = manager.get_recovery_options("failed", error_log, 1, 30)

        assert "can_retry" in options
        assert "suggestions" in options
        assert "recovery_actions" in options
        assert options["progress_saved"] == 30

        # Should have retry action
        actions = [a["action"] for a in options["recovery_actions"]]
        assert "retry" in actions or "partial_complete" in actions


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
