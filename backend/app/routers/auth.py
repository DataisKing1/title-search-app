"""Authentication router"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from typing import Optional
from datetime import datetime
import logging

from app.database import get_db
from app.services.auth import AuthService
from app.services.email import get_email_service
from app.exceptions import AuthenticationError, ValidationError
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


# Request/Response Models
class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12)
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    is_active: bool
    is_admin: bool
    created_at: datetime
    last_login: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class PasswordChangeRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=12)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str = Field(..., min_length=12)


# Dependencies
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """Get current authenticated user from JWT token"""
    try:
        payload = AuthService.decode_token(token)
        user_id = int(payload.get("sub"))
        token_type = payload.get("type")

        if token_type != "access":
            raise AuthenticationError(message="Invalid token type")

    except (ValueError, KeyError):
        raise AuthenticationError(message="Invalid token")

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(user_id)

    if not user:
        raise AuthenticationError(message="User not found")

    if not user.is_active:
        raise AuthenticationError(message="Account is disabled")

    return user


async def get_current_admin(user: User = Depends(get_current_user)) -> User:
    """Require admin user"""
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user


# Endpoints
@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    """Register a new user"""
    auth_service = AuthService(db)
    try:
        user = await auth_service.create_user(
            email=request.email,
            password=request.password,
            full_name=request.full_name
        )
        return UserResponse.model_validate(user)
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message)


@router.post("/login", response_model=TokenResponse)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    """Login and get access token"""
    auth_service = AuthService(db)
    try:
        user = await auth_service.authenticate_user(form_data.username, form_data.password)

        access_token = AuthService.create_access_token(data={"sub": str(user.id)})
        refresh_token = AuthService.create_refresh_token(data={"sub": str(user.id)})

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            user=UserResponse.model_validate(user)
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message)


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
):
    """Refresh access token using refresh token"""
    try:
        payload = AuthService.decode_token(refresh_token)
        user_id = int(payload.get("sub"))
        token_type = payload.get("type")

        if token_type != "refresh":
            raise AuthenticationError(message="Invalid token type")

        auth_service = AuthService(db)
        user = await auth_service.get_user_by_id(user_id)

        if not user or not user.is_active:
            raise AuthenticationError(message="Invalid user")

        new_access_token = AuthService.create_access_token(data={"sub": str(user.id)})
        new_refresh_token = AuthService.create_refresh_token(data={"sub": str(user.id)})

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            user=UserResponse.model_validate(user)
        )
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=e.message)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    """Get current user profile"""
    return UserResponse.model_validate(current_user)


@router.post("/change-password")
async def change_password(
    request: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Change current user password"""
    auth_service = AuthService(db)
    try:
        await auth_service.change_password(
            user=current_user,
            old_password=request.old_password,
            new_password=request.new_password
        )
        return {"message": "Password changed successfully"}
    except (AuthenticationError, ValidationError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=e.message)


@router.post("/forgot-password")
async def forgot_password(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
):
    """Request password reset email"""
    auth_service = AuthService(db)
    token = await auth_service.generate_reset_token(request.email)

    # Always return success to prevent email enumeration
    if token:
        # Send password reset email
        email_service = get_email_service()
        if email_service.is_configured():
            email_sent = email_service.send_password_reset_email(
                to_email=request.email,
                reset_token=token
            )
            if not email_sent:
                logger.warning(f"Failed to send password reset email to {request.email}")
        else:
            # Log token in development when email is not configured
            logger.info(
                f"Email not configured. Password reset token for {request.email}: {token}"
            )

    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password")
async def reset_password(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
):
    """Reset password using token"""
    auth_service = AuthService(db)
    try:
        success = await auth_service.reset_password(request.token, request.new_password)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired reset token"
            )
        return {"message": "Password reset successfully"}
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=e.message)
