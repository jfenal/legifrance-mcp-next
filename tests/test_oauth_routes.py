"""Tests for the OAuth routes module (legifrance_mcp/src/oauth/routes.py).

Each endpoint is a thin wrapper: guard against an uninitialized
get_oauth_service, then delegate to the matching controller.handle_*
function. Mirrors the existing patching pattern used in
tests/test_api.py::TestRegisterEndpointRoute.
"""

from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.testclient import TestClient
from starlette.routing import Route

from legifrance_mcp.src.api import app
from legifrance_mcp.src.oauth import routes as routes_module


class TestCallbackEndpointRoute:
    """Test the /auth/callback/oidc route."""

    def test_callback_endpoint_delegates_to_controller(self):
        """Test that the callback route calls controller.handle_callback."""
        mock_oauth_service = AsyncMock()
        mock_response = RedirectResponse(
            url="http://localhost:3000/callback", status_code=302
        )

        with (
            patch(
                "legifrance_mcp.src.oauth.routes.get_oauth_service",
                return_value=mock_oauth_service,
            ),
            patch(
                "legifrance_mcp.src.oauth.controller.handle_callback",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_handle_callback,
        ):
            client = TestClient(app, follow_redirects=False)
            response = client.get("/auth/callback/oidc?code=abc&state=xyz")

            assert response.status_code == 302
            mock_handle_callback.assert_called_once()

    def test_callback_endpoint_raises_when_service_not_initialized(self):
        """Test that the callback route raises RuntimeError if get_oauth_service is None."""
        with patch("legifrance_mcp.src.oauth.routes.get_oauth_service", None):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/auth/callback/oidc")

            assert response.status_code == 500


class TestAuthorizeEndpointRoute:
    """Test the /auth/authorize route."""

    def test_authorize_endpoint_delegates_to_controller(self):
        """Test that the authorize route calls controller.handle_authorize."""
        mock_oauth_service = AsyncMock()
        mock_response = RedirectResponse(
            url="https://idp.example.com/authorize", status_code=302
        )

        with (
            patch(
                "legifrance_mcp.src.oauth.routes.get_oauth_service",
                return_value=mock_oauth_service,
            ),
            patch(
                "legifrance_mcp.src.oauth.controller.handle_authorize",
                new_callable=AsyncMock,
                return_value=mock_response,
            ) as mock_handle_authorize,
        ):
            client = TestClient(app, follow_redirects=False)
            response = client.get("/auth/authorize?response_type=code&client_id=c")

            assert response.status_code == 302
            mock_handle_authorize.assert_called_once()

    def test_authorize_endpoint_raises_when_service_not_initialized(self):
        """Test that the authorize route raises RuntimeError if get_oauth_service is None."""
        with patch("legifrance_mcp.src.oauth.routes.get_oauth_service", None):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.get("/auth/authorize")

            assert response.status_code == 500


class TestTokenEndpointRoute:
    """Test the /auth/token route."""

    def test_token_endpoint_delegates_to_controller(self):
        """Test that the token route calls controller.handle_token."""
        mock_oauth_service = AsyncMock()
        mock_result = {"access_token": "tok123", "token_type": "Bearer"}

        with (
            patch(
                "legifrance_mcp.src.oauth.routes.get_oauth_service",
                return_value=mock_oauth_service,
            ),
            patch(
                "legifrance_mcp.src.oauth.controller.handle_token",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_handle_token,
        ):
            client = TestClient(app)
            response = client.post(
                "/auth/token", data={"grant_type": "client_credentials"}
            )

            assert response.status_code == 200
            assert response.json() == mock_result
            mock_handle_token.assert_called_once()

    def test_token_endpoint_raises_when_service_not_initialized(self):
        """Test that the token route raises RuntimeError if get_oauth_service is None."""
        with patch("legifrance_mcp.src.oauth.routes.get_oauth_service", None):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/auth/token", data={"grant_type": "client_credentials"}
            )

            assert response.status_code == 500


class TestRegisterEndpointRouteNotInitialized:
    """Test the /auth/register route's uninitialized-service branch."""

    def test_register_endpoint_raises_when_service_not_initialized(self):
        """Test that the register route raises RuntimeError if get_oauth_service is None."""
        with patch("legifrance_mcp.src.oauth.routes.get_oauth_service", None):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post(
                "/auth/register",
                json={
                    "client_name": "Test Client",
                    "redirect_uris": ["http://x/callback"],
                },
            )

            assert response.status_code == 500


class TestIntrospectEndpointRoute:
    """Test the /auth/introspect route."""

    def test_introspect_endpoint_delegates_to_controller(self):
        """Test that the introspect route calls controller.handle_introspect."""
        mock_oauth_service = AsyncMock()
        mock_result = {"active": True, "sub": "user123"}

        with (
            patch(
                "legifrance_mcp.src.oauth.routes.get_oauth_service",
                return_value=mock_oauth_service,
            ),
            patch(
                "legifrance_mcp.src.oauth.controller.handle_introspect",
                new_callable=AsyncMock,
                return_value=mock_result,
            ) as mock_handle_introspect,
        ):
            client = TestClient(app)
            response = client.post("/auth/introspect", data={"token": "tok123"})

            assert response.status_code == 200
            assert response.json() == mock_result
            mock_handle_introspect.assert_called_once()

    def test_introspect_endpoint_raises_when_service_not_initialized(self):
        """Test that the introspect route raises RuntimeError if get_oauth_service is None."""
        with patch("legifrance_mcp.src.oauth.routes.get_oauth_service", None):
            client = TestClient(app, raise_server_exceptions=False)
            response = client.post("/auth/introspect", data={"token": "tok123"})

            assert response.status_code == 500


class TestRegisterOauthRoutes:
    """Test register_oauth_routes wiring."""

    def test_register_oauth_routes_sets_provider_and_includes_router(self):
        """Test that register_oauth_routes stores the provider and registers the router."""
        test_app = FastAPI()

        def provider():
            return AsyncMock()

        previous_provider = routes_module.get_oauth_service
        try:
            routes_module.register_oauth_routes(test_app, provider)

            assert routes_module.get_oauth_service is provider
            route_paths = {
                route.path for route in test_app.routes if isinstance(route, Route)
            }
            assert "/auth/token" in route_paths
        finally:
            routes_module.get_oauth_service = previous_provider
