"""Error Handling Service

Provides comprehensive error categorization, recovery options,
and diagnostics for failed search operations.
"""

import re
import logging
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class ErrorCategory(str, Enum):
    """Categories of errors for better handling"""
    NETWORK = "network"           # Connection issues, timeouts
    AUTHENTICATION = "auth"       # Login failures, session expired
    RATE_LIMIT = "rate_limit"     # Too many requests
    PARSING = "parsing"           # HTML/data parsing failures
    SCRAPING = "scraping"         # Website structure changed
    DATABASE = "database"         # DB connection/query errors
    STORAGE = "storage"           # File storage issues
    AI_SERVICE = "ai_service"     # OpenAI/Anthropic API errors
    VALIDATION = "validation"     # Data validation failures
    TIMEOUT = "timeout"           # Operation timeout
    RESOURCE = "resource"         # Memory, disk space, etc.
    UNKNOWN = "unknown"           # Unclassified errors


class RecoveryAction(str, Enum):
    """Possible recovery actions"""
    RETRY = "retry"                   # Simple retry
    RETRY_WITH_DELAY = "retry_delay"  # Retry after waiting
    RETRY_ALTERNATE = "retry_alt"     # Try alternative approach
    MANUAL_REVIEW = "manual"          # Requires human intervention
    SKIP_STEP = "skip"                # Skip and continue
    PARTIAL_COMPLETE = "partial"      # Mark as partially complete
    ESCALATE = "escalate"             # Notify admin
    ABORT = "abort"                   # Cannot recover


@dataclass
class ErrorDiagnosis:
    """Diagnosis result for an error"""
    category: ErrorCategory
    severity: str  # low, medium, high, critical
    is_transient: bool  # Likely to succeed on retry
    user_message: str
    technical_details: str
    recovery_actions: List[RecoveryAction]
    recommended_action: RecoveryAction
    retry_delay_seconds: int
    max_retries: int


# Error pattern matching for categorization
ERROR_PATTERNS = {
    ErrorCategory.NETWORK: [
        r"connection refused",
        r"connection reset",
        r"connection timed out",
        r"network unreachable",
        r"name resolution",
        r"dns",
        r"socket",
        r"ERR_CONNECTION",
        r"net::",
        r"connectionerror",
    ],
    ErrorCategory.TIMEOUT: [
        r"timeout",
        r"timed out",
        r"took too long",
        r"deadline exceeded",
        r"TimeoutError",
    ],
    ErrorCategory.RATE_LIMIT: [
        r"rate limit",
        r"too many requests",
        r"429",
        r"throttl",
        r"quota exceeded",
    ],
    ErrorCategory.AUTHENTICATION: [
        r"unauthorized",
        r"401",
        r"forbidden",
        r"403",
        r"login required",
        r"session expired",
        r"authentication failed",
        r"access denied",
    ],
    ErrorCategory.PARSING: [
        r"parse error",
        r"invalid json",
        r"malformed",
        r"unexpected token",
        r"xml",
        r"html parsing",
        r"element not found",
        r"selector",
    ],
    ErrorCategory.SCRAPING: [
        r"page not found",
        r"404",
        r"element not found",
        r"no results",
        r"website unavailable",
        r"under maintenance",
        r"captcha",
        r"bot detection",
    ],
    ErrorCategory.DATABASE: [
        r"database",
        r"sql",
        r"postgres",
        r"connection pool",
        r"deadlock",
        r"integrity error",
        r"constraint",
    ],
    ErrorCategory.STORAGE: [
        r"storage",
        r"disk space",
        r"s3",
        r"minio",
        r"file not found",
        r"permission denied",
        r"upload failed",
    ],
    ErrorCategory.AI_SERVICE: [
        r"openai",
        r"anthropic",
        r"api key",
        r"model not found",
        r"context length",
        r"content policy",
    ],
    ErrorCategory.VALIDATION: [
        r"validation",
        r"invalid",
        r"required field",
        r"type error",
        r"value error",
    ],
    ErrorCategory.RESOURCE: [
        r"memory",
        r"out of memory",
        r"oom",
        r"resource exhausted",
        r"cpu",
    ],
}


# Severity and recovery configuration per category
ERROR_CONFIG = {
    ErrorCategory.NETWORK: {
        "severity": "medium",
        "is_transient": True,
        "retry_delay": 30,
        "max_retries": 3,
        "recovery_actions": [RecoveryAction.RETRY_WITH_DELAY, RecoveryAction.RETRY_ALTERNATE],
        "user_message": "Network connection issue. The system will automatically retry.",
    },
    ErrorCategory.TIMEOUT: {
        "severity": "medium",
        "is_transient": True,
        "retry_delay": 60,
        "max_retries": 2,
        "recovery_actions": [RecoveryAction.RETRY_WITH_DELAY, RecoveryAction.SKIP_STEP],
        "user_message": "The operation timed out. Retrying with extended timeout.",
    },
    ErrorCategory.RATE_LIMIT: {
        "severity": "low",
        "is_transient": True,
        "retry_delay": 300,  # 5 minutes
        "max_retries": 3,
        "recovery_actions": [RecoveryAction.RETRY_WITH_DELAY],
        "user_message": "Rate limited by the county website. Will retry after a delay.",
    },
    ErrorCategory.AUTHENTICATION: {
        "severity": "high",
        "is_transient": False,
        "retry_delay": 0,
        "max_retries": 1,
        "recovery_actions": [RecoveryAction.MANUAL_REVIEW, RecoveryAction.ESCALATE],
        "user_message": "Authentication issue with external service. May require credential update.",
    },
    ErrorCategory.PARSING: {
        "severity": "high",
        "is_transient": False,
        "retry_delay": 0,
        "max_retries": 1,
        "recovery_actions": [RecoveryAction.SKIP_STEP, RecoveryAction.PARTIAL_COMPLETE, RecoveryAction.MANUAL_REVIEW],
        "user_message": "Could not parse some data. Results may be incomplete.",
    },
    ErrorCategory.SCRAPING: {
        "severity": "high",
        "is_transient": False,
        "retry_delay": 3600,  # 1 hour
        "max_retries": 1,
        "recovery_actions": [RecoveryAction.RETRY_ALTERNATE, RecoveryAction.MANUAL_REVIEW],
        "user_message": "County website structure may have changed. Attempting alternative method.",
    },
    ErrorCategory.DATABASE: {
        "severity": "critical",
        "is_transient": True,
        "retry_delay": 5,
        "max_retries": 5,
        "recovery_actions": [RecoveryAction.RETRY, RecoveryAction.ESCALATE],
        "user_message": "Database connection issue. Retrying automatically.",
    },
    ErrorCategory.STORAGE: {
        "severity": "high",
        "is_transient": False,
        "retry_delay": 60,
        "max_retries": 2,
        "recovery_actions": [RecoveryAction.RETRY, RecoveryAction.ESCALATE],
        "user_message": "File storage issue. Retrying upload.",
    },
    ErrorCategory.AI_SERVICE: {
        "severity": "medium",
        "is_transient": True,
        "retry_delay": 30,
        "max_retries": 3,
        "recovery_actions": [RecoveryAction.RETRY_WITH_DELAY, RecoveryAction.SKIP_STEP],
        "user_message": "AI analysis service temporarily unavailable. Retrying.",
    },
    ErrorCategory.VALIDATION: {
        "severity": "medium",
        "is_transient": False,
        "retry_delay": 0,
        "max_retries": 0,
        "recovery_actions": [RecoveryAction.SKIP_STEP, RecoveryAction.MANUAL_REVIEW],
        "user_message": "Some data did not pass validation. Review may be required.",
    },
    ErrorCategory.RESOURCE: {
        "severity": "critical",
        "is_transient": True,
        "retry_delay": 300,
        "max_retries": 1,
        "recovery_actions": [RecoveryAction.RETRY_WITH_DELAY, RecoveryAction.ESCALATE],
        "user_message": "System resource constraint. Will retry after resources free up.",
    },
    ErrorCategory.UNKNOWN: {
        "severity": "high",
        "is_transient": False,
        "retry_delay": 60,
        "max_retries": 1,
        "recovery_actions": [RecoveryAction.RETRY, RecoveryAction.MANUAL_REVIEW],
        "user_message": "An unexpected error occurred. Our team has been notified.",
    },
}


class ErrorHandler:
    """Handles error categorization, diagnosis, and recovery"""

    def categorize_error(self, error: str) -> ErrorCategory:
        """Categorize an error based on its message"""
        error_lower = error.lower()

        for category, patterns in ERROR_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, error_lower, re.IGNORECASE):
                    return category

        return ErrorCategory.UNKNOWN

    def diagnose_error(
        self,
        error: str,
        task_name: str = "",
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorDiagnosis:
        """Diagnose an error and provide recovery recommendations"""
        category = self.categorize_error(error)
        config = ERROR_CONFIG[category]

        # Adjust based on context
        retry_count = (context or {}).get("retry_count", 0)
        remaining_retries = max(0, config["max_retries"] - retry_count)

        if remaining_retries == 0:
            recovery_actions = [RecoveryAction.MANUAL_REVIEW, RecoveryAction.ABORT]
            recommended = RecoveryAction.MANUAL_REVIEW
        else:
            recovery_actions = config["recovery_actions"]
            recommended = recovery_actions[0] if recovery_actions else RecoveryAction.RETRY

        return ErrorDiagnosis(
            category=category,
            severity=config["severity"],
            is_transient=config["is_transient"],
            user_message=config["user_message"],
            technical_details=f"Task: {task_name}, Error: {error}",
            recovery_actions=recovery_actions,
            recommended_action=recommended,
            retry_delay_seconds=config["retry_delay"],
            max_retries=remaining_retries,
        )

    def create_error_entry(
        self,
        error: str,
        task_name: str,
        diagnosis: Optional[ErrorDiagnosis] = None
    ) -> Dict[str, Any]:
        """Create an error log entry"""
        if not diagnosis:
            diagnosis = self.diagnose_error(error, task_name)

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "task": task_name,
            "error": error,
            "category": diagnosis.category.value,
            "severity": diagnosis.severity,
            "is_transient": diagnosis.is_transient,
            "recommended_action": diagnosis.recommended_action.value,
        }

    def should_retry(
        self,
        error: str,
        retry_count: int,
        max_retries: int = 3
    ) -> Tuple[bool, int]:
        """Determine if operation should be retried and delay"""
        diagnosis = self.diagnose_error(error, context={"retry_count": retry_count})

        if not diagnosis.is_transient:
            return False, 0

        if retry_count >= max_retries or retry_count >= diagnosis.max_retries:
            return False, 0

        # Exponential backoff
        delay = diagnosis.retry_delay_seconds * (2 ** retry_count)
        return True, delay

    def get_recovery_suggestions(
        self,
        error_log: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Analyze error log and provide recovery suggestions"""
        if not error_log:
            return {"suggestions": [], "can_retry": True}

        # Count error categories
        category_counts: Dict[str, int] = {}
        for entry in error_log:
            cat = entry.get("category", "unknown")
            category_counts[cat] = category_counts.get(cat, 0) + 1

        # Find most common error
        most_common = max(category_counts.items(), key=lambda x: x[1])
        latest_error = error_log[-1] if error_log else None

        suggestions = []
        can_retry = True

        # Generate suggestions based on error patterns
        if most_common[0] == ErrorCategory.NETWORK.value:
            suggestions.append("Check network connectivity to county recorder websites")
            suggestions.append("The county website may be temporarily down")
            can_retry = True

        elif most_common[0] == ErrorCategory.RATE_LIMIT.value:
            suggestions.append("Wait a few minutes before retrying")
            suggestions.append("Consider running during off-peak hours")
            can_retry = True

        elif most_common[0] == ErrorCategory.SCRAPING.value:
            suggestions.append("The county website structure may have changed")
            suggestions.append("Try using manual document upload as an alternative")
            can_retry = False

        elif most_common[0] == ErrorCategory.AUTHENTICATION.value:
            suggestions.append("County website credentials may need to be updated")
            suggestions.append("Contact administrator to verify account access")
            can_retry = False

        elif most_common[0] == ErrorCategory.PARSING.value:
            suggestions.append("Some documents could not be processed automatically")
            suggestions.append("Consider uploading problematic documents manually")
            can_retry = True

        elif most_common[0] == ErrorCategory.TIMEOUT.value:
            suggestions.append("Operation taking longer than expected")
            suggestions.append("Try retrying during off-peak hours")
            can_retry = True

        else:
            suggestions.append("Review the error details for more information")
            suggestions.append("Contact support if the issue persists")
            can_retry = True

        # Count consecutive failures
        consecutive_failures = 0
        for entry in reversed(error_log):
            if entry.get("severity") in ["high", "critical"]:
                consecutive_failures += 1
            else:
                break

        if consecutive_failures >= 3:
            can_retry = False
            suggestions.insert(0, "Multiple consecutive failures detected - manual review recommended")

        return {
            "suggestions": suggestions,
            "can_retry": can_retry,
            "error_summary": {
                "total_errors": len(error_log),
                "by_category": category_counts,
                "most_common": most_common[0],
                "consecutive_failures": consecutive_failures,
            },
            "latest_error": latest_error,
        }


class SearchRecoveryManager:
    """Manages recovery of failed searches"""

    STEP_ORDER = [
        "orchestrate_search",
        "scrape_county_recorder",
        "scrape_court_records",
        "download_all_documents",
        "analyze_all_documents",
        "build_chain_of_title",
        "generate_report",
        "finalize_search",
    ]

    def __init__(self):
        self.error_handler = ErrorHandler()

    def get_last_successful_step(self, error_log: List[Dict[str, Any]]) -> Optional[str]:
        """Determine the last step that completed successfully"""
        if not error_log:
            return None

        failed_steps = {entry.get("task") for entry in error_log}

        # Find the first failed step
        for i, step in enumerate(self.STEP_ORDER):
            if step in failed_steps:
                if i == 0:
                    return None
                return self.STEP_ORDER[i - 1]

        return self.STEP_ORDER[-1]

    def get_resume_step(self, error_log: List[Dict[str, Any]]) -> Optional[str]:
        """Determine which step to resume from"""
        last_successful = self.get_last_successful_step(error_log)

        if last_successful is None:
            return self.STEP_ORDER[0]

        try:
            idx = self.STEP_ORDER.index(last_successful)
            if idx < len(self.STEP_ORDER) - 1:
                return self.STEP_ORDER[idx + 1]
        except ValueError:
            pass

        return None

    def can_resume(
        self,
        status: str,
        error_log: List[Dict[str, Any]],
        retry_count: int
    ) -> Tuple[bool, str]:
        """Check if a search can be resumed"""
        if status not in ["failed"]:
            return False, "Search is not in a failed state"

        recovery = self.error_handler.get_recovery_suggestions(error_log)

        if not recovery["can_retry"]:
            return False, "Too many failures or non-recoverable error"

        if retry_count >= 5:
            return False, "Maximum retry attempts exceeded"

        resume_step = self.get_resume_step(error_log)
        if not resume_step:
            return False, "No recoverable step found"

        return True, f"Can resume from step: {resume_step}"

    def get_recovery_options(
        self,
        status: str,
        error_log: List[Dict[str, Any]],
        retry_count: int,
        progress_percent: int
    ) -> Dict[str, Any]:
        """Get all available recovery options for a failed search"""
        can_resume, resume_reason = self.can_resume(status, error_log, retry_count)
        suggestions = self.error_handler.get_recovery_suggestions(error_log)

        options = {
            "can_retry": can_resume,
            "retry_reason": resume_reason,
            "resume_step": self.get_resume_step(error_log) if can_resume else None,
            "suggestions": suggestions["suggestions"],
            "error_summary": suggestions.get("error_summary", {}),
            "progress_saved": progress_percent,
        }

        # Add specific recovery actions
        recovery_actions = []

        if can_resume:
            recovery_actions.append({
                "action": "retry",
                "label": "Retry Search",
                "description": f"Resume from {options['resume_step'] or 'beginning'}",
            })

        if progress_percent >= 30:
            recovery_actions.append({
                "action": "partial_complete",
                "label": "Save Partial Results",
                "description": "Mark as complete with available data",
            })

        recovery_actions.append({
            "action": "manual_upload",
            "label": "Manual Document Upload",
            "description": "Upload documents manually instead of scraping",
        })

        recovery_actions.append({
            "action": "cancel",
            "label": "Cancel Search",
            "description": "Cancel and delete this search",
        })

        options["recovery_actions"] = recovery_actions

        return options


# Global instances
error_handler = ErrorHandler()
recovery_manager = SearchRecoveryManager()


def diagnose_and_log_error(
    search_id: int,
    task_name: str,
    error: Exception,
    db_session = None
) -> ErrorDiagnosis:
    """Convenience function to diagnose, log, and update search with error"""
    from app.models.search import TitleSearch

    error_str = str(error)
    diagnosis = error_handler.diagnose_error(error_str, task_name)
    entry = error_handler.create_error_entry(error_str, task_name, diagnosis)

    logger.error(
        f"Search {search_id} error in {task_name}: {error_str} "
        f"(category={diagnosis.category.value}, severity={diagnosis.severity})"
    )

    if db_session:
        try:
            search = db_session.query(TitleSearch).filter(
                TitleSearch.id == search_id
            ).first()
            if search:
                search.error_log = (search.error_log or []) + [entry]
                search.status_message = diagnosis.user_message
                db_session.commit()
        except Exception as e:
            logger.error(f"Failed to update error log: {e}")

    return diagnosis
