"""Tests for Studio Assignment 001 — Application Shell and Route Foundation."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class TestStudioRoutes:
    """Verify all core Studio routes render successfully."""

    @pytest.mark.parametrize(
        "path",
        [
            "/",
            "/cartridges",
            "/cartridges/new",
            "/interviews/test-session-123",
            "/drafts/test-session-123/review",
            "/cartridges/test-cartridge-456",
            "/how-it-works",
        ],
    )
    def test_core_routes_return_200(self, path: str):
        response = client.get(path)
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
        assert "CHIMERA" in response.text
        assert "STUDIO" in response.text


class TestStudioErrorPage:
    """Verify 404 and 500 error page handling."""

    def test_404_page_renders_custom_template(self):
        response = client.get("/non-existent-route-999")
        assert response.status_code == 404
        assert "Error 404" in response.text
        assert "Return to Studio Dashboard" in response.text


class TestStudioAccessibilityAndLandmarks:
    """Verify WCAG accessibility baseline, skip link, and landmarks."""

    def test_skip_link_present(self):
        response = client.get("/cartridges")
        assert response.status_code == 200
        html = response.text
        assert 'href="#main-content"' in html
        assert "Skip to main content" in html

    def test_semantic_landmarks_present(self):
        response = client.get("/cartridges")
        assert response.status_code == 200
        html = response.text
        assert 'role="banner"' in html
        assert 'role="navigation"' in html
        assert 'id="main-content"' in html
        assert 'role="contentinfo"' in html

    def test_mobile_toggle_aria_attributes(self):
        response = client.get("/cartridges")
        assert response.status_code == 200
        html = response.text
        assert 'id="mobile-menu-toggle"' in html
        assert 'aria-expanded="false"' in html
        assert 'aria-controls="primary-nav"' in html

    def test_global_loading_and_toast_elements(self):
        response = client.get("/cartridges")
        assert response.status_code == 200
        html = response.text
        assert 'id="global-loading"' in html
        assert 'id="toast-container"' in html

    def test_specification_badge_present(self):
        response = client.get("/cartridges")
        assert response.status_code == 200
        assert "v1.0.0" in response.text


class TestActiveRouteHighlighting:
    """Verify primary navigation highlights the current route active state."""

    def test_dashboard_active_highlight(self):
        response = client.get("/cartridges")
        assert response.status_code == 200
        assert 'class="nav-link active"' in response.text or 'aria-current="page"' in response.text

    def test_new_persona_active_highlight(self):
        response = client.get("/cartridges/new")
        assert response.status_code == 200
        assert 'class="nav-link nav-btn-primary active"' in response.text or 'aria-current="page"' in response.text
