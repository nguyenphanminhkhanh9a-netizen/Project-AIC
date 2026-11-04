"""Integration and unit tests for FastAPI health check and security middleware."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.main import app

client = TestClient(app)


class TestHealthEndpoint:
    """Tests for GET /api/v1/health."""

    def test_health_returns_ok_without_auth(self) -> None:
        """Health probe must be accessible on loopback for Tauri launcher handshake."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["version"] == "0.5.0"
        assert data["environment"] == "development"
        assert data["uptime_seconds"] >= 0.0
        assert data["active_sessions"] >= 1

    def test_authenticated_health_requires_token(self) -> None:
        """Endpoint requiring session token fails with 401 if token is missing."""
        response = client.get("/api/v1/health/authenticated")
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "missing_session_token"

    def test_authenticated_health_fails_with_invalid_token(self) -> None:
        """Endpoint fails with 401 if token is incorrect."""
        response = client.get(
            "/api/v1/health/authenticated",
            headers={"X-AIC-Session-Token": "invalid_wrong_token_123"},
        )
        assert response.status_code == 401
        data = response.json()
        assert data["detail"]["error"] == "invalid_session_token"

    def test_authenticated_health_succeeds_with_valid_token(self) -> None:
        """Endpoint succeeds with 200 when matching session token is passed."""
        response = client.get(
            "/api/v1/health/authenticated",
            headers={"X-AIC-Session-Token": settings.session_token},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"


class TestNetworkSecurityRules:
    """Tests enforcing ADR-007 loopback only networking."""

    def test_loopback_host_allowed(self) -> None:
        s = Settings(host="127.0.0.1")
        assert s.host == "127.0.0.1"

    def test_non_loopback_host_strictly_rejected(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            Settings(host="0.0.0.0")
        assert "Security violation" in str(exc_info.value)

    def test_lan_ip_strictly_rejected(self) -> None:
        with pytest.raises(ValueError) as exc_info:
            Settings(host="192.168.1.100")
        assert "Security violation" in str(exc_info.value)
