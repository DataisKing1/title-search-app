"""
Seed script to create a test user for development.

Run with: python -m scripts.seed_user
"""
import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.services.auth import get_password_hash


# Test user credentials
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "TestPassword123!"
TEST_FULL_NAME = "Test User"


async def create_test_user():
    """Create a test user for development"""

    # Create async engine
    engine = create_async_engine(settings.DATABASE_URL, echo=True)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Check if user already exists
        result = await session.execute(
            select(User).where(User.email == TEST_EMAIL.lower())
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            print(f"\n{'='*50}")
            print("Test user already exists!")
            print(f"{'='*50}")
            print(f"Email: {TEST_EMAIL}")
            print(f"Password: {TEST_PASSWORD}")
            print(f"{'='*50}\n")
            return existing_user

        # Create user
        user = User(
            email=TEST_EMAIL.lower(),
            hashed_password=get_password_hash(TEST_PASSWORD),
            full_name=TEST_FULL_NAME,
            is_admin=True,  # Make test user an admin
            is_active=True
        )

        session.add(user)
        await session.commit()
        await session.refresh(user)

        print(f"\n{'='*50}")
        print("Test user created successfully!")
        print(f"{'='*50}")
        print(f"Email: {TEST_EMAIL}")
        print(f"Password: {TEST_PASSWORD}")
        print(f"Admin: Yes")
        print(f"{'='*50}\n")

        return user


if __name__ == "__main__":
    asyncio.run(create_test_user())
