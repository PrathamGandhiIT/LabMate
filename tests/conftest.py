"""
Pytest configuration and shared fixtures.
"""

import pytest
from fastapi.testclient import TestClient


from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.database import Base


@pytest.fixture(autouse=True)
def setup_test_db(monkeypatch):
    """Use an isolated in-memory SQLite database for all tests."""
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    test_session_factory = sessionmaker(bind=test_engine)

    import app.main
    monkeypatch.setattr(app.main, "create_db_engine", lambda: test_engine)
    monkeypatch.setattr(app.main, "get_session_factory", lambda eng: test_session_factory)

    from app.main import app
    app.state.db_engine = test_engine
    app.state.db_session_factory = test_session_factory
    yield
    test_engine.dispose()


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    from app.main import app
    with TestClient(app) as c:
        yield c


@pytest.fixture
def mock_gemini_success(monkeypatch):
    """
    Mock the Gemini service to return a successful response.
    Use this in unit tests so they don't require a real API key.
    """
    from app.config import settings

    async def mock_health_check(self):
        return {
            "api_reachable": True,
            "model_available": True,
            "model_name": settings.gemini_model,
            "error": None,
        }

    async def mock_is_reachable(self):
        return True

    async def mock_chat(self, messages, **kwargs):
        return "This is a mock AI response for testing."

    from app.services.gemini_service import GeminiService
    monkeypatch.setattr(GeminiService, "health_check", mock_health_check)
    monkeypatch.setattr(GeminiService, "is_reachable", mock_is_reachable)
    monkeypatch.setattr(GeminiService, "chat", mock_chat)


@pytest.fixture
def mock_gemini_down(monkeypatch):
    """Mock the Gemini service as unreachable."""
    from app.config import settings

    async def mock_health_check(self):
        return {
            "api_reachable": False,
            "model_available": False,
            "model_name": settings.gemini_model,
            "error": "Cannot connect to Gemini API.",
        }

    async def mock_is_reachable(self):
        return False

    from app.services.gemini_service import GeminiService
    monkeypatch.setattr(GeminiService, "health_check", mock_health_check)
    monkeypatch.setattr(GeminiService, "is_reachable", mock_is_reachable)
