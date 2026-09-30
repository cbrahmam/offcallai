# backend/tests/conftest.py
"""
Pytest configuration and fixtures for OffCall AI backend tests.
"""

import os

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime, timedelta
import uuid

from fastapi.testclient import TestClient
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool

from app.main import app
from app.database import Base, get_async_session
from app.models.user import User
from app.models.organization import Organization
from app.core.security import create_access_token, get_password_hash


# The models use PostgreSQL-specific types (JSONB, UUID), so the integration
# fixtures need a real PostgreSQL database rather than SQLite. Point
# TEST_DATABASE_URL at a throwaway database; tests that need it are skipped when
# it is unreachable.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://postgres@localhost:5432/offcall_test",
)


@pytest.fixture(scope="session")
def event_loop() -> Generator:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def async_engine():
    """Create async engine for tests against a throwaway PostgreSQL database."""
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:
        await engine.dispose()
        pytest.skip(
            f"PostgreSQL not reachable at TEST_DATABASE_URL ({exc.__class__.__name__}). "
            "Start PostgreSQL and create the test database to run integration tests."
        )

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await engine.dispose()


@pytest.fixture(scope="function")
async def db_session(async_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create async session for tests."""
    async_session_maker = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session


@pytest.fixture(scope="function")
async def test_organization(db_session: AsyncSession) -> Organization:
    """Create a test organization."""
    org = Organization(
        id=uuid.uuid4(),
        name="Test Organization",
        slug="test-org",
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(org)
    await db_session.commit()
    await db_session.refresh(org)
    return org


@pytest.fixture(scope="function")
async def test_user(db_session: AsyncSession, test_organization: Organization) -> User:
    """Create a test user."""
    user = User(
        id=uuid.uuid4(),
        organization_id=test_organization.id,
        email="test@example.com",
        password_hash=get_password_hash("TestPassword123!"),
        full_name="Test User",
        role="admin",
        is_active=True,
        is_verified=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture(scope="function")
def test_user_token(test_user: User) -> str:
    """Create a valid access token for test user."""
    token_data = {
        "sub": str(test_user.id),
        "org_id": str(test_user.organization_id)
    }
    return create_access_token(data=token_data)


@pytest.fixture(scope="function")
def auth_headers(test_user_token: str) -> dict:
    """Create authorization headers with test user token."""
    return {"Authorization": f"Bearer {test_user_token}"}


@pytest.fixture(scope="function")
def client() -> Generator:
    """Create a synchronous test client."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="function")
async def async_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Create an async test client with database session override."""

    async def override_get_async_session():
        yield db_session

    app.dependency_overrides[get_async_session] = override_get_async_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://localhost") as ac:
        yield ac

    app.dependency_overrides.clear()


# Mock fixtures for external services

@pytest.fixture
def mock_redis():
    """Mock Redis client."""
    redis_mock = MagicMock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.setex = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def mock_email_service():
    """Mock email service."""
    email_mock = MagicMock()
    email_mock.send_email = AsyncMock(return_value=True)
    return email_mock


@pytest.fixture
def mock_ai_service():
    """Mock AI service."""
    ai_mock = MagicMock()
    ai_mock.analyze = AsyncMock(return_value={
        "analysis": "Test analysis",
        "recommendations": ["Test recommendation"]
    })
    return ai_mock


# Test data factories

class TestDataFactory:
    """Factory for creating test data."""

    @staticmethod
    def create_user_data(
        email: str = "user@example.com",
        password: str = "SecurePass123!",
        full_name: str = "Test User",
        organization_name: str = "Test Org"
    ) -> dict:
        """Create user registration data."""
        return {
            "email": email,
            "password": password,
            "full_name": full_name,
            "organization_name": organization_name
        }

    @staticmethod
    def create_login_data(
        email: str = "user@example.com",
        password: str = "SecurePass123!"
    ) -> dict:
        """Create login data."""
        return {
            "email": email,
            "password": password
        }

    @staticmethod
    def create_incident_data(
        title: str = "Test Incident",
        description: str = "Test description",
        severity: str = "high"
    ) -> dict:
        """Create incident data."""
        return {
            "title": title,
            "description": description,
            "severity": severity
        }


@pytest.fixture
def test_data_factory():
    """Provide test data factory."""
    return TestDataFactory()
