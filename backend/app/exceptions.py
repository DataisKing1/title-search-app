"""Custom exceptions for the application"""
from typing import Optional, Dict, Any


class AppException(Exception):
    """Base exception for the application"""
    def __init__(
        self,
        message: str,
        code: str = "APP_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found"""
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="NOT_FOUND", status_code=404, details=details)


class AuthenticationError(AppException):
    """Authentication failed"""
    def __init__(self, message: str = "Authentication failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="AUTHENTICATION_FAILED", status_code=401, details=details)


class AuthorizationError(AppException):
    """Authorization failed"""
    def __init__(self, message: str = "Access denied", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="ACCESS_DENIED", status_code=403, details=details)


class ValidationError(AppException):
    """Validation error"""
    def __init__(self, message: str = "Validation failed", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="VALIDATION_ERROR", status_code=422, details=details)


class ConflictError(AppException):
    """Resource conflict"""
    def __init__(self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="CONFLICT", status_code=409, details=details)


class ServiceError(AppException):
    """External service error"""
    def __init__(self, message: str = "Service error", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="SERVICE_ERROR", status_code=503, details=details)


class RateLimitError(AppException):
    """Rate limit exceeded"""
    def __init__(self, message: str = "Rate limit exceeded", details: Optional[Dict[str, Any]] = None):
        super().__init__(message=message, code="RATE_LIMIT_EXCEEDED", status_code=429, details=details)
