"""
Tests for application health, pages, and AI status.
"""


class TestPages:
    """All navigation pages should return 200."""

    def test_dashboard_loads(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "AI LabMate" in resp.text

    def test_practical_studio_loads(self, client):
        resp = client.get("/practical-studio")
        assert resp.status_code == 200
        assert "Practical Studio" in resp.text

    def test_code_lab_loads(self, client):
        resp = client.get("/code-lab")
        assert resp.status_code == 200
        assert "Code Lab" in resp.text

    def test_viva_arena_loads(self, client):
        resp = client.get("/viva-arena")
        assert resp.status_code == 200
        assert "Viva Arena" in resp.text

    def test_my_practicals_loads(self, client):
        resp = client.get("/my-practicals")
        assert resp.status_code == 200
        assert "My Practicals" in resp.text

    def test_static_css_accessible(self, client):
        resp = client.get("/static/css/style.css")
        assert resp.status_code == 200
        assert "bg-main" in resp.text

    def test_static_js_accessible(self, client):
        resp = client.get("/static/js/app.js")
        assert resp.status_code == 200
        assert "AIStatus" in resp.text


class TestHealthEndpoint:
    """Tests for /api/health with mocked Gemini."""

    def test_health_when_gemini_up(self, client, mock_gemini_success):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_reachable"] is True
        assert data["model_available"] is True
        from app.config import settings

        assert data["model_name"] == settings.gemini_model
        assert data["error"] is None

    def test_health_when_gemini_down(self, client, mock_gemini_down):
        resp = client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["api_reachable"] is False
        assert data["model_available"] is False
        assert data["error"] is not None

    def test_health_returns_valid_schema(self, client, mock_gemini_success):
        resp = client.get("/api/health")
        data = resp.json()
        # All expected fields present
        assert "status" in data
        assert "api_reachable" in data
        assert "model_available" in data
        assert "model_name" in data


class TestDashboardContent:
    """Dashboard shows real data, not fakes."""

    def test_dashboard_has_welcome(self, client):
        resp = client.get("/")
        assert "Welcome to AI LabMate" in resp.text

    def test_dashboard_has_quick_actions(self, client):
        resp = client.get("/")
        assert "Generate Practical" in resp.text
        assert "Explain Code" in resp.text
        assert "Viva Prep" in resp.text

    def test_dashboard_has_empty_state_when_no_practicals(self, client):
        resp = client.get("/")
        assert "No practicals yet" in resp.text

    def test_dashboard_has_ai_status(self, client):
        resp = client.get("/")
        assert "ai-status-dot" in resp.text
