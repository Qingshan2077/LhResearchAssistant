"""Shared fixtures for unit and API tests."""

import asyncio
from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.llm import ChatMessage, LLMConfig, LLMProvider
from app.main import app


@pytest.fixture(scope="session")
def test_engine():
    """Create one in-memory SQLite database shared across test threads."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def db_session(test_engine) -> Generator[Session, None, None]:
    """Run each test inside an outer transaction that is rolled back."""
    connection = test_engine.connect()
    transaction = connection.begin()
    session = sessionmaker(bind=connection, expire_on_commit=False)()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def override_get_db(db_session: Session):
    """Replace the production database dependency with the test session."""
    def _override():
        yield db_session

    return _override


@pytest.fixture
def test_app(override_get_db) -> Generator[FastAPI, None, None]:
    app.dependency_overrides[get_db] = override_get_db
    try:
        yield app
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(test_app) as test_client:
        yield test_client


@pytest_asyncio.fixture
async def async_client(test_app: FastAPI) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


class MockLLMProvider(LLMProvider):
    """Deterministic provider that never performs network requests."""

    def __init__(self, response: str = "Mock response"):
        self.response = response
        self.last_messages: list[ChatMessage] = []
        self.last_config: LLMConfig | None = None

    async def chat(self, messages: list[ChatMessage], config: LLMConfig) -> str:
        self.last_messages = messages
        self.last_config = config
        return self.response

    async def chat_stream(
        self,
        messages: list[ChatMessage],
        config: LLMConfig,
    ) -> AsyncGenerator[str, None]:
        self.last_messages = messages
        self.last_config = config
        for word in self.response.split():
            yield f"{word} "
            await asyncio.sleep(0)

    async def test_connection(self, config: LLMConfig) -> dict:
        return {"success": True, "latency_ms": 10, "model": "mock-model"}


@pytest.fixture
def mock_llm_provider() -> MockLLMProvider:
    return MockLLMProvider()


@pytest.fixture
def mock_llm_config() -> LLMConfig:
    return LLMConfig(api_key="mock-key", model="mock-model")


@pytest.fixture
def mock_httpx_client():
    """Patch external async HTTP calls and expose the client instance."""
    with patch("httpx.AsyncClient") as client_class:
        client_instance = AsyncMock()
        client_class.return_value.__aenter__.return_value = client_instance
        client_class.return_value.__aexit__.return_value = None
        client_instance.get = AsyncMock()
        client_instance.post = AsyncMock()
        yield client_instance


@pytest.fixture
def mock_chroma():
    """Provide an empty Chroma query result without opening a real collection."""
    with patch("app.database.chroma_client.collection") as mock_collection:
        mock_collection.query = MagicMock(
            return_value={"documents": [[]], "metadatas": [[]], "distances": [[]]}
        )
        yield mock_collection
