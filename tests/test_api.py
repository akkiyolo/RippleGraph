"""Unit tests for the API layer."""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client without live HydraDB/LLM."""
    from ripplegraph.api.main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health(self, client):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestLandingPage:
    def test_landing(self, client):
        response = client.get("/")
        assert response.status_code == 200


class TestChatPage:
    def test_chat(self, client):
        response = client.get("/chat")
        assert response.status_code == 200
