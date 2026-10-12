"""Shared pytest fixtures, database lifecycle management, and test HTTP client."""

from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.main import create_app

# In-memory SQLite async engine for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


def get_test_settings() -> Settings:
    """Settings override for tests."""
    return Settings(
        APP_ENV="test",
        APP_DEBUG=True,
        DATABASE_URL=TEST_DATABASE_URL,
        SECRET_KEY="test-secret-key-minimum-32-characters-long",
        STORAGE_BACKEND="local",
        STORAGE_LOCAL_ROOT="./test_storage",
        LLM_PROVIDER="mock",
        VECTOR_STORE_TYPE="memory",
    )


@pytest.fixture(scope="session", autouse=True)
def override_settings():
    """Apply test settings globally."""
    from app.core import config

    config.get_settings = get_test_settings  # type: ignore[assignment]
    yield
    config.get_settings = get_settings  # type: ignore[assignment]


@pytest.fixture(autouse=True)
async def setup_test_db() -> AsyncGenerator[None, None]:
    """Create all database tables before each test and drop them afterwards."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides an isolated database session for tests."""
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Test HTTP client hooked to the FastAPI application with mocked DB dependency."""
    app = create_app()

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
