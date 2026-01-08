"""Authentication service"""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets

from app.config import settings
from app.models.user import User
from app.exceptions import AuthenticationError, ValidationError


# Password hashing context - use argon2 (more secure than bcrypt and no 72-byte limit)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    # Encode to handle unicode properly
    return pwd_context.verify(plain_password.encode('utf-8').decode('utf-8'), hashed_password)


def get_password_hash(password: str) -> str:
    """Generate password hash"""
    # Encode to handle unicode properly and truncate for bcrypt compatibility
    encoded_password = password.encode('utf-8').decode('utf-8')
    return pwd_context.hash(encoded_password)


def validate_password_strength(password: str) -> None:
    """Validate password meets requirements"""
    errors = []

    if len(password) < settings.PASSWORD_MIN_LENGTH:
        errors.append(f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters")

    if settings.PASSWORD_REQUIRE_UPPERCASE and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if settings.PASSWORD_REQUIRE_LOWERCASE and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if settings.PASSWORD_REQUIRE_DIGIT and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    if settings.PASSWORD_REQUIRE_SPECIAL:
        special_chars = "!@#$%^&*()_+-=[]{}|;':\",./<>?"
        if not any(c in special_chars for c in password):
            errors.append("Password must contain at least one special character")

    if errors:
        raise ValidationError(message="Password does not meet requirements", details={"errors": errors})


class AuthService:
    """Authentication service for user management"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def authenticate_user(self, email: str, password: str) -> User:
        """Authenticate a user by email and password"""
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        user = result.scalar_one_or_none()

        if not user:
            raise AuthenticationError(message="Invalid email or password")

        if not verify_password(password, user.hashed_password):
            raise AuthenticationError(message="Invalid email or password")

        if not user.is_active:
            raise AuthenticationError(message="Account is disabled")

        # Update last login
        user.last_login = datetime.utcnow()
        await self.db.commit()

        return user

    async def create_user(
        self,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        is_admin: bool = False
    ) -> User:
        """Create a new user"""
        # Validate password
        validate_password_strength(password)

        # Check if user exists
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        if result.scalar_one_or_none():
            raise ValidationError(message="Email already registered")

        # Create user
        user = User(
            email=email.lower(),
            hashed_password=get_password_hash(password),
            full_name=full_name,
            is_admin=is_admin
        )

        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)

        return user

    async def get_user_by_id(self, user_id: int) -> Optional[User]:
        """Get user by ID"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email"""
        result = await self.db.execute(
            select(User).where(User.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def change_password(self, user: User, old_password: str, new_password: str) -> None:
        """Change user password"""
        if not verify_password(old_password, user.hashed_password):
            raise AuthenticationError(message="Current password is incorrect")

        validate_password_strength(new_password)

        user.hashed_password = get_password_hash(new_password)
        await self.db.commit()

    async def generate_reset_token(self, email: str) -> Optional[str]:
        """Generate password reset token"""
        user = await self.get_user_by_email(email)
        if not user:
            return None

        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.utcnow() + timedelta(hours=24)
        await self.db.commit()

        return token

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Reset password using token"""
        result = await self.db.execute(
            select(User).where(
                User.reset_token == token,
                User.reset_token_expires > datetime.utcnow()
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            return False

        validate_password_strength(new_password)

        user.hashed_password = get_password_hash(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        await self.db.commit()

        return True

    @staticmethod
    def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
        to_encode.update({"exp": expire, "type": "access"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def create_refresh_token(data: dict) -> str:
        """Create JWT refresh token"""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        to_encode.update({"exp": expire, "type": "refresh"})
        return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

    @staticmethod
    def decode_token(token: str) -> dict:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            return payload
        except JWTError:
            raise AuthenticationError(message="Invalid or expired token")
