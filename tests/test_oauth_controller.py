from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException
from fastapi.responses import JSONResponse, RedirectResponse

from legifrance_mcp.src.oauth import controller
from legifrance_mcp.src.oauth.service import OAuthService


def _detail(exc: HTTPException) -> dict:
    """Narrow HTTPException.detail (typed str | None by starlette's stubs) to the dict this controller always raises with."""
    assert isinstance(exc.detail, dict)
    return exc.detail


class TestOAuthControllerHandleCallback:
    """Test handle_callback function."""

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_handle_callback_success(self, mock_settings):
        """Test successful OAuth callback handling in production mode."""
        mock_settings.USE_EXTERNAL_BROWSER_AUTH = False

        mock_request = Mock()
        mock_request.query_params.get.side_effect = lambda key: {
            "code": "auth_code_123",
            "state": "state_123",
        }.get(key)

        mock_request.session = {
            "user_details": {
                "auth_code": "stored_code_123",
                "redirect_uri": "http://localhost:3000/callback",
            }
        }

        # Mock OAuth2Handler
        mock_token = {"access_token": "token123", "refresh_token": "refresh123"}

        with patch("legifrance_mcp.src.oauth.controller.OAuth2Handler") as mock_handler:
            mock_handler.get_access_token_from_authorization_code_flow.return_value = (
                mock_token
            )

            # Create mock OAuth service with dependency injection
            oauth_service = AsyncMock(spec=OAuthService)
            oauth_service.add_token_to_code = AsyncMock()

            result = await controller.handle_callback(mock_request, oauth_service)

            # Verify OAuth2Handler was called correctly
            mock_handler.get_access_token_from_authorization_code_flow.assert_called_once_with(
                "auth_code_123", "state_123"
            )

            # Verify service was called
            oauth_service.add_token_to_code.assert_called_once_with(
                "stored_code_123", mock_token
            )

            # Verify redirect response
            assert isinstance(result, RedirectResponse)
            assert result.status_code == 302
            assert "code=stored_code_123" in result.headers["location"]

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_handle_callback_missing_session_data(self, mock_settings):
        """Test callback handling with missing session data in production mode."""
        # Set production mode to test original flow
        mock_settings.USE_EXTERNAL_BROWSER_AUTH = False

        mock_request = Mock()
        mock_request.query_params.get.side_effect = lambda key: {
            "code": "auth_code_123",
            "state": "state_123",
        }.get(key)

        # Missing user_details in session
        mock_request.session = {}

        with patch("legifrance_mcp.src.oauth.controller.OAuth2Handler") as mock_handler:
            mock_handler.get_access_token_from_authorization_code_flow.return_value = {
                "access_token": "token"
            }

            # Create mock OAuth service
            oauth_service = AsyncMock(spec=OAuthService)

            # Should raise HTTPException when session data is missing
            with pytest.raises(HTTPException) as exc_info:
                await controller.handle_callback(mock_request, oauth_service)
            assert exc_info.value.status_code == 400
            assert _detail(exc_info.value)["error"] == "invalid_request"

    @pytest.mark.asyncio
    async def test_handle_callback_missing_code_param(self):
        """Test callback handling when code or state query param is missing."""
        mock_request = Mock()
        mock_request.query_params.get.side_effect = lambda key: {
            "code": None,
            "state": "state_123",
        }.get(key)

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_callback(mock_request, oauth_service)
        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_request"
        assert (
            "Missing code or state parameter"
            in _detail(exc_info.value)["error_description"]
        )

    @pytest.mark.asyncio
    async def test_handle_callback_missing_state_param(self):
        """Test callback handling when state query param is missing."""
        mock_request = Mock()
        mock_request.query_params.get.side_effect = lambda key: {
            "code": "auth_code_123",
            "state": None,
        }.get(key)

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_callback(mock_request, oauth_service)
        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_request"

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_handle_callback_local_development(self, mock_settings):
        """Test OAuth callback handling in local development mode."""
        # Set local development mode
        mock_settings.USE_EXTERNAL_BROWSER_AUTH = True

        # Mock request
        mock_request = Mock()
        mock_request.query_params.get.side_effect = lambda key: {
            "code": "auth_code_123",
            "state": "state_123",
        }.get(key)

        # Mock OAuth2Handler
        mock_token = {"access_token": "dev_token_123", "refresh_token": "refresh123"}

        with (
            patch("legifrance_mcp.src.oauth.controller.OAuth2Handler") as mock_handler,
            patch(
                "legifrance_mcp.src.oauth.controller.api_module", create=True
            ) as mock_api_module,
        ):
            mock_handler.get_access_token_from_authorization_code_flow.return_value = (
                mock_token
            )

            # Create mock OAuth service
            oauth_service = AsyncMock(spec=OAuthService)

            result = await controller.handle_callback(mock_request, oauth_service)

            # Verify OAuth2Handler was called correctly
            mock_handler.get_access_token_from_authorization_code_flow.assert_called_once_with(
                "auth_code_123", "state_123"
            )

            # Verify token was stored in local development mode
            assert mock_api_module._local_development_token == "dev_token_123"

            # Verify JSON response returned
            assert isinstance(result, JSONResponse)
            assert result.status_code == 200


class TestOAuthControllerHandleAuthorize:
    """Test handle_authorize function."""

    @pytest.mark.asyncio
    async def test_handle_authorize_invalid_client(self):
        """Test authorization with invalid client."""
        mock_request = Mock()
        mock_request.query_params = {
            "response_type": "code",
            "client_id": "invalid_client",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "challenge123",
            "code_challenge_method": "S256",
            "state": "state_123",
        }

        # Create mock OAuth service
        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorize(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert "invalid_client" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_handle_authorize_missing_pkce(self):
        """Test authorization without PKCE parameters."""
        mock_request = Mock()
        mock_request.query_params = {
            "response_type": "code",
            "client_id": "client123",
            "redirect_uri": "http://localhost:3000/callback",
            # Missing code_challenge and code_challenge_method
        }

        # Create mock OAuth service
        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorize(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert "invalid_request" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_handle_authorize_unsupported_response_type(self):
        """Test authorization with unsupported response type."""
        mock_request = Mock()
        mock_request.query_params = {
            "response_type": "token",  # Unsupported
            "client_id": "client123",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "challenge123",
            "code_challenge_method": "S256",
        }

        # Create mock OAuth service
        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorize(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert "unsupported_response_type" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_handle_authorize_missing_required_parameters(self):
        """Test authorization without response_type/client_id/redirect_uri."""
        mock_request = Mock()
        mock_request.query_params = {
            "code_challenge": "challenge123",
            "code_challenge_method": "S256",
        }

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorize(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_request"
        assert (
            "Missing required parameters"
            in _detail(exc_info.value)["error_description"]
        )

    @pytest.mark.asyncio
    async def test_handle_authorize_redirect_uri_mismatch(self):
        """Test authorization when redirect_uri isn't registered for the client."""
        mock_request = Mock()
        mock_request.query_params = {
            "response_type": "code",
            "client_id": "client123",
            "redirect_uri": "http://evil.example.com/callback",
            "code_challenge": "challenge123",
            "code_challenge_method": "S256",
        }

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(
            return_value={"redirect_uris": ["http://localhost:3000/callback"]}
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorize(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_request"
        assert "Invalid redirect_uri" in _detail(exc_info.value)["error_description"]

    @pytest.mark.asyncio
    async def test_handle_authorize_success(self):
        """Test the full successful authorization flow redirects to the IdP."""
        mock_request = Mock()
        mock_request.query_params = {
            "response_type": "code",
            "client_id": "client123",
            "redirect_uri": "http://localhost:3000/callback",
            "scope": "read",
            "code_challenge": "challenge123",
            "code_challenge_method": "S256",
            "state": "state_123",
        }
        mock_request.session = {}

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(
            return_value={"redirect_uris": ["http://localhost:3000/callback"]}
        )
        oauth_service.create_authorization_code = AsyncMock(
            return_value="auth_code_123"
        )

        with patch("legifrance_mcp.src.oauth.controller.OAuth2Handler") as mock_handler:
            mock_handler.get_authorization_url.return_value = (
                "https://idp.example.com/authorize",
                "idp_state",
            )

            result = await controller.handle_authorize(mock_request, oauth_service)

        assert isinstance(result, RedirectResponse)
        assert result.status_code == 302
        assert result.headers["location"] == "https://idp.example.com/authorize"
        assert mock_request.session["user_details"]["auth_code"] == "auth_code_123"
        oauth_service.create_authorization_code.assert_called_once_with(
            "client123",
            "http://localhost:3000/callback",
            "read",
            "challenge123",
            "S256",
            "state_123",
        )

    @pytest.mark.asyncio
    async def test_handle_authorize_unexpected_error_returns_server_error(self):
        """Test that an unexpected exception is converted to a 500 server_error."""
        mock_request = Mock()
        mock_request.query_params = {
            "response_type": "code",
            "client_id": "client123",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "challenge123",
            "code_challenge_method": "S256",
        }

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(
            side_effect=RuntimeError("storage down")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorize(mock_request, oauth_service)

        assert exc_info.value.status_code == 500
        assert _detail(exc_info.value)["error"] == "server_error"


class TestOAuthControllerHandleToken:
    """Test handle_token function."""

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_handle_token_authorization_code_grant(self, mock_settings):
        """Test token endpoint with authorization code grant."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        # Mock form data
        form_data = {
            "grant_type": "authorization_code",
            "code": "code123",
            "redirect_uri": "http://localhost:3000/callback",
            "client_id": "client123",
            "client_secret": "secret123",
            "code_verifier": "verifier123",
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        # Mock code data
        code_data = {
            "client_id": "client123",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "challenge123",
            "snowflake_token": {
                "access_token": "snowflake_access",
                "refresh_token": "snowflake_refresh",
            },
        }

        # Create mock OAuth service
        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code = AsyncMock(return_value=code_data)
        oauth_service.validate_client = AsyncMock(return_value={"id": "client123"})
        oauth_service.mark_code_as_used = AsyncMock()

        with patch(
            "legifrance_mcp.src.oauth.controller.verify_code_challenge",
            return_value=True,
        ):
            result = await controller.handle_token(mock_request, oauth_service)

            # Verify service calls
            oauth_service.validate_authorization_code.assert_called_once_with("code123")
            oauth_service.validate_client.assert_called_once_with(
                "client123", "secret123"
            )
            oauth_service.mark_code_as_used.assert_called_once_with("code123")

            # Verify response
            assert result["access_token"] == "snowflake_access"
            assert result["refresh_token"] == "snowflake_refresh"
            assert result["token_type"] == "Bearer"

    @pytest.mark.asyncio
    async def test_handle_token_invalid_grant_type(self):
        """Test token endpoint with invalid grant type."""
        form_data = {"grant_type": "invalid_grant"}

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_token(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert "unsupported_grant_type" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_handle_token_missing_grant_type(self):
        """Test token endpoint with no grant_type at all."""
        form_data = {"code": "code123"}

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_token(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_request"
        assert "Missing grant_type" in _detail(exc_info.value)["error_description"]

    @pytest.mark.asyncio
    async def test_handle_token_refresh_token_validation_error(self):
        """Test token endpoint with an invalid refresh_token request payload."""
        form_data = {"grant_type": "refresh_token"}  # missing required refresh_token

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_token(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert (
            "Invalid refresh_token request"
            in _detail(exc_info.value)["error_description"]
        )

    @pytest.mark.asyncio
    async def test_handle_token_client_credentials_validation_error(self):
        """Test token endpoint with an invalid client_credentials request payload."""
        form_data = {"grant_type": "client_credentials", "scope": 123}  # wrong type

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_token(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert (
            "Invalid client_credentials request"
            in _detail(exc_info.value)["error_description"]
        )

    @pytest.mark.asyncio
    async def test_handle_token_unexpected_error_returns_server_error(self):
        """Test that an unexpected exception during token handling is a 500 server_error."""
        form_data = {
            "grant_type": "authorization_code",
            "code": "code123",
            "redirect_uri": "http://localhost:3000/callback",
            "client_id": "client123",
            "client_secret": "secret123",
            "code_verifier": "verifier123",
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code = AsyncMock(
            side_effect=RuntimeError("storage down")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_token(mock_request, oauth_service)

        assert exc_info.value.status_code == 500
        assert _detail(exc_info.value)["error"] == "server_error"

    @pytest.mark.asyncio
    async def test_handle_token_missing_parameters(self):
        """Test token endpoint with missing required parameters."""
        form_data = {
            "grant_type": "authorization_code"
            # Missing code, redirect_uri, client_id, code_verifier
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_token(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert "invalid_request" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_handle_token_invalid_code(self):
        """Test token endpoint with invalid authorization code."""
        form_data = {
            "grant_type": "authorization_code",
            "code": "invalid_code",
            "redirect_uri": "http://localhost:3000/callback",
            "client_id": "client123",
            "code_verifier": "verifier123",
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_token(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert "invalid_grant" in str(exc_info.value.detail)

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_handle_token_pkce_verification_failure(self, mock_settings):
        """Test token endpoint with PKCE verification failure."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        form_data = {
            "grant_type": "authorization_code",
            "code": "code123",
            "redirect_uri": "http://localhost:3000/callback",
            "client_id": "client123",
            "client_secret": "secret123",
            "code_verifier": "wrong_verifier",
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        code_data = {
            "client_id": "client123",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "challenge123",
        }

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code = AsyncMock(return_value=code_data)
        oauth_service.validate_client = AsyncMock(return_value={"id": "client123"})

        with patch(
            "legifrance_mcp.src.oauth.controller.verify_code_challenge",
            return_value=False,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await controller.handle_token(mock_request, oauth_service)

            assert exc_info.value.status_code == 400
            assert "invalid_grant" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_handle_token_refresh_token_grant(self):
        """Test token endpoint with refresh_token grant type via handle_token."""
        form_data = {
            "grant_type": "refresh_token",
            "refresh_token": "valid_refresh_token",
            "client_id": "test_client",
            "client_secret": "test_secret",
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_refresh_token = AsyncMock(
            return_value={
                "client_id": "test_client",
                "scope": "read",
            }
        )
        oauth_service.validate_client = AsyncMock(return_value={"id": "test_client"})

        result = await controller.handle_token(mock_request, oauth_service)

        assert result["access_token"] == "refreshed_access_token_placeholder"
        assert result["token_type"] == "Bearer"

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_handle_token_client_credentials_grant(self, mock_settings):
        """Test token endpoint with client_credentials grant type via handle_token."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        form_data = {
            "grant_type": "client_credentials",
            "client_id": "test_client",
            "client_secret": "test_secret",
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.body = AsyncMock(return_value=b"")

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(return_value={"id": "test_client"})

        result = await controller.handle_token(mock_request, oauth_service)

        assert result["access_token"] == "client_credentials_access_token_placeholder"
        assert result["token_type"] == "Bearer"


class TestOAuthControllerHandleRegister:
    """Test handle_register function."""

    @pytest.mark.asyncio
    async def test_handle_register_success(self):
        """Test successful client registration."""
        registration_data = {
            "client_name": "Test Client",
            "redirect_uris": ["http://localhost:3000/callback"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "scope": "read write",
        }

        mock_request = Mock()
        mock_request.json = AsyncMock(return_value=registration_data)

        client_response = {
            "client_id": "client123",
            "client_secret": "secret123",
            "client_name": "Test Client",
            "redirect_uris": ["http://localhost:3000/callback"],
            "grant_types": ["authorization_code"],
            "response_types": ["code"],
            "scope": "read write",
            "client_id_issued_at": 1234567890,
        }

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.register_client = AsyncMock(return_value=client_response)

        result = await controller.handle_register(mock_request, oauth_service)

        oauth_service.register_client.assert_called_once_with(
            "Test Client",
            ["http://localhost:3000/callback"],
            ["authorization_code"],
            ["code"],
            "read write",
        )

        # Convert Pydantic model to dict for comparison
        result_dict = result.model_dump() if hasattr(result, "model_dump") else result
        assert result_dict == client_response

    @pytest.mark.asyncio
    async def test_handle_register_minimal_data(self):
        """Test client registration with minimal required data."""
        registration_data = {
            "client_name": "Minimal Client",
            "redirect_uris": ["http://localhost:3000/callback"],
        }

        mock_request = Mock()
        mock_request.json = AsyncMock(return_value=registration_data)

        oauth_service = AsyncMock(spec=OAuthService)
        # Mock a complete client response for Pydantic validation
        complete_client_response = {
            "client_id": "client123",
            "client_secret": "secret123",
            "client_name": "Minimal Client",
            "redirect_uris": ["http://localhost:3000/callback"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "scope": "read write",
            "client_id_issued_at": 1234567890,
        }
        oauth_service.register_client = AsyncMock(return_value=complete_client_response)

        result = await controller.handle_register(mock_request, oauth_service)

        oauth_service.register_client.assert_called_once_with(
            "Minimal Client",
            ["http://localhost:3000/callback"],
            [
                "authorization_code",
                "refresh_token",
            ],  # Default grant types from Pydantic model
            ["code"],  # Default response types from Pydantic model
            "read write",  # Default scope from Pydantic model
        )

        # handle_register's return type is always ClientRegistrationResponse.
        result_dict = result.model_dump()
        assert result_dict["client_id"] == "client123"

    @pytest.mark.asyncio
    async def test_handle_register_invalid_request_data(self):
        """Test registration with invalid request data raises a 400 ValidationError."""
        mock_request = Mock()
        mock_request.json = AsyncMock(return_value={"redirect_uris": "not-a-list"})

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_register(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_request"

    @pytest.mark.asyncio
    async def test_handle_register_unexpected_error_returns_server_error(self):
        """Test that an unexpected exception during registration is a 500 server_error."""
        registration_data = {
            "client_name": "Test Client",
            "redirect_uris": ["http://localhost:3000/callback"],
        }

        mock_request = Mock()
        mock_request.json = AsyncMock(return_value=registration_data)

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.register_client = AsyncMock(
            side_effect=RuntimeError("storage down")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_register(mock_request, oauth_service)

        assert exc_info.value.status_code == 500
        assert _detail(exc_info.value)["error"] == "server_error"


class TestOAuthControllerHandleIntrospect:
    """Test handle_introspect function."""

    @pytest.mark.asyncio
    async def test_handle_introspect_active_token(self):
        """Test token introspection with active token."""
        form_data = {
            "token": "token123",
            "client_id": "client123",
            "client_secret": "secret123",
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.query_params = {}

        token_data = {
            "client_id": "client123",
            "scope": "read write",
            "expires_at": 9999999999,  # Far future
        }

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(return_value={"id": "client123"})
        oauth_service.retrieve_access_token = AsyncMock(return_value=token_data)

        with patch(
            "legifrance_mcp.src.oauth.controller.OAuth2Handler.introspect_token"
        ) as mock_introspect:
            mock_introspect.return_value = {
                "active": True,
                "client_id": "client123",
                "scope": "read write",
            }

            result = await controller.handle_introspect(mock_request, oauth_service)

            oauth_service.validate_client.assert_called_once_with(
                "client123", "secret123"
            )
            mock_introspect.assert_called_once_with("token123")

            assert result["active"] is True
            assert result["client_id"] == "client123"
            assert result["scope"] == "read write"

    @pytest.mark.asyncio
    async def test_handle_introspect_inactive_token(self):
        """Test token introspection with inactive token."""
        form_data = {
            "token": "invalid_token",
            "client_id": "client123",
            "client_secret": "secret123",
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.query_params = {}

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(return_value={"id": "client123"})
        oauth_service.retrieve_access_token = AsyncMock(return_value=None)

        with patch(
            "legifrance_mcp.src.oauth.controller.OAuth2Handler.introspect_token"
        ) as mock_introspect:
            mock_introspect.return_value = {"active": False}

            result = await controller.handle_introspect(mock_request, oauth_service)

            assert result["active"] is False

    @pytest.mark.asyncio
    async def test_handle_introspect_unauthorized_client(self):
        """Test token introspection with unauthorized client."""
        form_data = {
            "token": "token123",
            "client_id": "invalid_client",
            "client_secret": "wrong_secret",
        }

        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value=form_data)
        mock_request.json = AsyncMock()
        mock_request.query_params = {}

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_introspect(mock_request, oauth_service)

        assert exc_info.value.status_code == 401
        assert "invalid_client" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_handle_introspect_json_content_type(self):
        """Test token introspection parses a JSON request body."""
        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/json"}
        mock_request.json = AsyncMock(
            return_value={
                "token": "token123",
                "client_id": "client123",
                "client_secret": "secret123",
            }
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(return_value={"id": "client123"})

        with patch(
            "legifrance_mcp.src.oauth.controller.OAuth2Handler.introspect_token"
        ) as mock_introspect:
            mock_introspect.return_value = {"active": True}

            result = await controller.handle_introspect(mock_request, oauth_service)

        assert result["active"] is True

    @pytest.mark.asyncio
    async def test_handle_introspect_form_parsing_falls_back_to_query_params(self):
        """Test that a form-parsing failure falls back to query params."""
        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(side_effect=RuntimeError("bad form"))
        mock_request.json = AsyncMock()
        mock_request.query_params = {
            "token": "token123",
            "client_id": "client123",
            "client_secret": "secret123",
        }

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(return_value={"id": "client123"})

        with patch(
            "legifrance_mcp.src.oauth.controller.OAuth2Handler.introspect_token"
        ) as mock_introspect:
            mock_introspect.return_value = {"active": True}

            result = await controller.handle_introspect(mock_request, oauth_service)

        assert result["active"] is True

    @pytest.mark.asyncio
    async def test_handle_introspect_missing_token(self):
        """Test token introspection without a token parameter raises 400."""
        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value={"client_id": "client123"})
        mock_request.json = AsyncMock()
        mock_request.query_params = {}

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_introspect(mock_request, oauth_service)

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_request"

    @pytest.mark.asyncio
    async def test_handle_introspect_basic_auth_header(self):
        """Test token introspection authenticating via a Basic auth header."""
        import base64

        credentials = base64.b64encode(b"client123:secret123").decode("utf-8")

        mock_request = AsyncMock()
        mock_request.headers = {
            "content-type": "application/x-www-form-urlencoded",
            "authorization": f"Basic {credentials}",
        }
        mock_request.form = AsyncMock(return_value={"token": "token123"})
        mock_request.json = AsyncMock()
        mock_request.query_params = {}

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(return_value={"id": "client123"})

        with patch(
            "legifrance_mcp.src.oauth.controller.OAuth2Handler.introspect_token"
        ) as mock_introspect:
            mock_introspect.return_value = {"active": True}

            result = await controller.handle_introspect(mock_request, oauth_service)

        oauth_service.validate_client.assert_called_once_with("client123", "secret123")
        assert result["active"] is True

    @pytest.mark.asyncio
    async def test_handle_introspect_malformed_basic_auth_header(self):
        """Test token introspection with an undecodable Basic auth header."""
        mock_request = AsyncMock()
        mock_request.headers = {
            "content-type": "application/x-www-form-urlencoded",
            "authorization": "Basic not-valid-base64!!!",
        }
        mock_request.form = AsyncMock(return_value={"token": "token123"})
        mock_request.json = AsyncMock()
        mock_request.query_params = {}

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_introspect(mock_request, oauth_service)

        assert exc_info.value.status_code == 401
        assert _detail(exc_info.value)["error"] == "invalid_client"

    @pytest.mark.asyncio
    async def test_handle_introspect_missing_client_id(self):
        """Test token introspection with no client_id anywhere raises 401."""
        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(return_value={"token": "token123"})
        mock_request.json = AsyncMock()
        mock_request.query_params = {}

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_introspect(mock_request, oauth_service)

        assert exc_info.value.status_code == 401
        assert _detail(exc_info.value)["error"] == "invalid_client"

    @pytest.mark.asyncio
    async def test_handle_introspect_unexpected_error_returns_server_error(self):
        """Test that an unexpected exception during introspection is a 500 server_error."""
        mock_request = AsyncMock()
        mock_request.headers = {"content-type": "application/x-www-form-urlencoded"}
        mock_request.form = AsyncMock(
            return_value={
                "token": "token123",
                "client_id": "client123",
                "client_secret": "secret123",
            }
        )
        mock_request.json = AsyncMock()
        mock_request.query_params = {}

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client = AsyncMock(
            side_effect=RuntimeError("storage down")
        )

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_introspect(mock_request, oauth_service)

        assert exc_info.value.status_code == 500
        assert _detail(exc_info.value)["error"] == "server_error"


class TestOAuthControllerIntegration:
    """Integration tests for OAuth controller."""

    @pytest.mark.asyncio
    async def test_complete_oauth_flow(self):
        """Test a complete OAuth authorization code flow."""
        # This would test the integration between authorize, callback, and token endpoints
        # For now, just a placeholder that passes
        oauth_service = AsyncMock(spec=OAuthService)
        assert oauth_service is not None


class TestParseTokenRequest:
    """Test parse_token_request function edge cases."""

    @pytest.mark.asyncio
    async def test_parse_json_request(self):
        """Test parsing valid JSON request."""
        mock_request = Mock()
        mock_request.headers.get.return_value = "application/json"
        mock_request.json = AsyncMock(
            return_value={
                "grant_type": "authorization_code",
                "code": "test_code",
                "client_id": "test_client",
            }
        )

        result = await controller.parse_token_request(mock_request)

        assert result["grant_type"] == "authorization_code"
        assert result["code"] == "test_code"
        assert result["client_id"] == "test_client"
        mock_request.json.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_form_request(self):
        """Test parsing valid form data request."""
        mock_request = Mock()
        mock_request.headers.get.return_value = "application/x-www-form-urlencoded"
        mock_form_data = {
            "grant_type": "authorization_code",
            "code": "test_code",
            "client_id": "test_client",
        }
        mock_request.form = AsyncMock(return_value=mock_form_data)

        result = await controller.parse_token_request(mock_request)

        assert result["grant_type"] == "authorization_code"
        assert result["code"] == "test_code"
        assert result["client_id"] == "test_client"
        mock_request.form.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_request_no_content_type(self):
        """Test parsing request with no content-type header."""
        mock_request = Mock()
        mock_request.headers.get.return_value = None
        mock_form_data = {"grant_type": "authorization_code"}
        mock_request.form = AsyncMock(return_value=mock_form_data)

        result = await controller.parse_token_request(mock_request)

        assert result["grant_type"] == "authorization_code"
        mock_request.form.assert_called_once()

    @pytest.mark.asyncio
    async def test_parse_request_malformed_json(self):
        """Test parsing request with malformed JSON."""
        mock_request = Mock()
        mock_request.headers.get.return_value = "application/json"
        mock_request.json = AsyncMock(side_effect=ValueError("Invalid JSON"))

        with pytest.raises(HTTPException) as exc_info:
            await controller.parse_token_request(mock_request)

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_request"
        assert "Invalid request format" in _detail(exc_info.value)["error_description"]

    @pytest.mark.asyncio
    async def test_parse_request_form_data_error(self):
        """Test parsing request with form data error."""
        mock_request = Mock()
        mock_request.headers.get.return_value = "application/x-www-form-urlencoded"
        mock_request.form = AsyncMock(side_effect=RuntimeError("Form parsing error"))

        with pytest.raises(HTTPException) as exc_info:
            await controller.parse_token_request(mock_request)

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_request"
        assert "Invalid request format" in _detail(exc_info.value)["error_description"]

    @pytest.mark.asyncio
    async def test_parse_request_empty_json(self):
        """Test parsing request with empty JSON."""
        mock_request = Mock()
        mock_request.headers.get.return_value = "application/json"
        mock_request.json = AsyncMock(return_value={})

        result = await controller.parse_token_request(mock_request)

        assert result == {}

    @pytest.mark.asyncio
    async def test_parse_request_empty_form(self):
        """Test parsing request with empty form data."""
        mock_request = Mock()
        mock_request.headers.get.return_value = "application/x-www-form-urlencoded"
        mock_request.form = AsyncMock(return_value={})

        result = await controller.parse_token_request(mock_request)

        assert result == {}


class TestAuthorizationCodeGrantEdgeCases:
    """Test handle_authorization_code_grant edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_authorization_code(self):
        """Test with invalid authorization code."""
        from legifrance_mcp.src.oauth.models import (
            AuthorizationCodeTokenRequest,
        )

        token_request = AuthorizationCodeTokenRequest(
            grant_type="authorization_code",
            code="invalid_code",
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="http://localhost:3000/callback",
            code_verifier="test_verifier",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorization_code_grant(
                token_request, oauth_service
            )

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_grant"
        assert (
            "Invalid or expired authorization code"
            in _detail(exc_info.value)["error_description"]
        )
        oauth_service.validate_authorization_code.assert_called_once_with(
            "invalid_code"
        )

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_invalid_client_credentials(self, mock_settings):
        """Test with invalid client credentials."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        from legifrance_mcp.src.oauth.models import (
            AuthorizationCodeTokenRequest,
        )

        token_request = AuthorizationCodeTokenRequest(
            grant_type="authorization_code",
            code="valid_code",
            client_id="invalid_client",
            client_secret="invalid_secret",
            redirect_uri="http://localhost:3000/callback",
            code_verifier="test_verifier",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code.return_value = {
            "client_id": "test_client",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test_challenge",
            "scope": "read",
        }
        oauth_service.validate_client.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorization_code_grant(
                token_request, oauth_service
            )

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_client"
        assert (
            "Invalid client credentials" in _detail(exc_info.value)["error_description"]
        )

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_missing_client_id(self, mock_settings):
        """Test with client_id explicitly None and Cursor compatibility disabled."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        from legifrance_mcp.src.oauth.models import (
            AuthorizationCodeTokenRequest,
        )

        token_request = AuthorizationCodeTokenRequest(
            grant_type="authorization_code",
            code="valid_code",
            client_id=None,
            client_secret=None,
            redirect_uri="http://localhost:3000/callback",
            code_verifier="test_verifier",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code.return_value = {
            "client_id": "test_client",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test_challenge",
            "scope": "read",
        }

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorization_code_grant(
                token_request, oauth_service
            )

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_client"
        assert "Client ID is required" in _detail(exc_info.value)["error_description"]

    @pytest.mark.asyncio
    async def test_redirect_uri_mismatch(self):
        """Test with mismatched redirect URI."""
        from legifrance_mcp.src.oauth.models import (
            AuthorizationCodeTokenRequest,
        )

        token_request = AuthorizationCodeTokenRequest(
            grant_type="authorization_code",
            code="valid_code",
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="http://localhost:3000/different",
            code_verifier="test_verifier",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code.return_value = {
            "client_id": "test_client",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test_challenge",
            "scope": "read",
        }
        oauth_service.validate_client.return_value = {"id": "test_client"}

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_authorization_code_grant(
                token_request, oauth_service
            )

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_grant"
        assert "Redirect URI mismatch" in _detail(exc_info.value)["error_description"]

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_pkce_verification_failure(self, mock_settings):
        """Test with PKCE verification failure."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        from legifrance_mcp.src.oauth.models import (
            AuthorizationCodeTokenRequest,
        )

        token_request = AuthorizationCodeTokenRequest(
            grant_type="authorization_code",
            code="valid_code",
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="http://localhost:3000/callback",
            code_verifier="wrong_verifier",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code.return_value = {
            "client_id": "test_client",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test_challenge",
            "scope": "read",
        }
        oauth_service.validate_client.return_value = {"id": "test_client"}

        with patch(
            "legifrance_mcp.src.oauth.controller.verify_code_challenge"
        ) as mock_verify:
            mock_verify.return_value = False

            with pytest.raises(HTTPException) as exc_info:
                await controller.handle_authorization_code_grant(
                    token_request, oauth_service
                )

            assert exc_info.value.status_code == 400
            assert _detail(exc_info.value)["error"] == "invalid_grant"
            assert (
                "Invalid code verifier" in _detail(exc_info.value)["error_description"]
            )
            mock_verify.assert_called_once_with("wrong_verifier", "test_challenge")

    @pytest.mark.asyncio
    async def test_successful_grant_with_snowflake_tokens(self):
        """Test successful authorization code grant with Snowflake tokens."""
        from legifrance_mcp.src.oauth.models import (
            AuthorizationCodeTokenRequest,
        )

        token_request = AuthorizationCodeTokenRequest(
            grant_type="authorization_code",
            code="valid_code",
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="http://localhost:3000/callback",
            code_verifier="test_verifier",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code.return_value = {
            "client_id": "test_client",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test_challenge",
            "scope": "read write",
            "snowflake_token": {
                "access_token": "snowflake_access_token",
                "refresh_token": "snowflake_refresh_token",
            },
        }
        oauth_service.validate_client.return_value = {"id": "test_client"}
        oauth_service.mark_code_as_used = AsyncMock()

        with patch(
            "legifrance_mcp.src.oauth.controller.verify_code_challenge"
        ) as mock_verify:
            mock_verify.return_value = True

            result = await controller.handle_authorization_code_grant(
                token_request, oauth_service
            )

            assert result["access_token"] == "snowflake_access_token"
            assert result["refresh_token"] == "snowflake_refresh_token"
            assert result["token_type"] == "Bearer"
            assert result["expires_in"] == 3600
            assert result["scope"] == "read write"

            oauth_service.mark_code_as_used.assert_called_once_with("valid_code")

    @pytest.mark.asyncio
    async def test_successful_grant_without_snowflake_tokens(self):
        """Test successful authorization code grant without Snowflake tokens."""
        from legifrance_mcp.src.oauth.models import (
            AuthorizationCodeTokenRequest,
        )

        token_request = AuthorizationCodeTokenRequest(
            grant_type="authorization_code",
            code="valid_code",
            client_id="test_client",
            client_secret="test_secret",
            redirect_uri="http://localhost:3000/callback",
            code_verifier="test_verifier",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_authorization_code.return_value = {
            "client_id": "test_client",
            "redirect_uri": "http://localhost:3000/callback",
            "code_challenge": "test_challenge",
            "scope": "read",
        }
        oauth_service.validate_client.return_value = {"id": "test_client"}
        oauth_service.mark_code_as_used = AsyncMock()

        with patch(
            "legifrance_mcp.src.oauth.controller.verify_code_challenge"
        ) as mock_verify:
            mock_verify.return_value = True

            result = await controller.handle_authorization_code_grant(
                token_request, oauth_service
            )

            assert result["access_token"] == "oauth_access_token_placeholder"
            assert result["token_type"] == "Bearer"
            assert result["expires_in"] == 3600
            assert result["scope"] == "read"
            assert "refresh_token" not in result

            oauth_service.mark_code_as_used.assert_called_once_with("valid_code")


class TestRefreshTokenGrantEdgeCases:
    """Test handle_refresh_token_grant_pydantic edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_refresh_token(self):
        """Test with invalid refresh token."""
        from legifrance_mcp.src.oauth.models import RefreshTokenRequest

        token_request = RefreshTokenRequest(
            grant_type="refresh_token",
            refresh_token="invalid_refresh_token",
            client_id="test_client",
            client_secret="test_secret",
            scope=None,
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_refresh_token.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_refresh_token_grant_pydantic(
                token_request, oauth_service
            )

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_grant"
        assert (
            "Invalid or expired refresh token"
            in _detail(exc_info.value)["error_description"]
        )
        oauth_service.validate_refresh_token.assert_called_once_with(
            "invalid_refresh_token"
        )

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_invalid_client_credentials_refresh(self, mock_settings):
        """Test refresh token grant with invalid client credentials."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        from legifrance_mcp.src.oauth.models import RefreshTokenRequest

        token_request = RefreshTokenRequest(
            grant_type="refresh_token",
            refresh_token="valid_refresh_token",
            client_id="invalid_client",
            client_secret="invalid_secret",
            scope=None,
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_refresh_token.return_value = {
            "client_id": "test_client",
            "scope": "read",
        }
        oauth_service.validate_client.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_refresh_token_grant_pydantic(
                token_request, oauth_service
            )

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_client"
        assert (
            "Invalid client credentials" in _detail(exc_info.value)["error_description"]
        )

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_missing_client_id_refresh(self, mock_settings):
        """Test refresh token grant with client_id explicitly None."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        from legifrance_mcp.src.oauth.models import RefreshTokenRequest

        token_request = RefreshTokenRequest(
            grant_type="refresh_token",
            refresh_token="valid_refresh_token",
            client_id=None,
            client_secret=None,
            scope=None,
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_refresh_token.return_value = {
            "client_id": "test_client",
            "scope": "read",
        }

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_refresh_token_grant_pydantic(
                token_request, oauth_service
            )

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_client"
        assert "Client ID is required" in _detail(exc_info.value)["error_description"]

    @pytest.mark.asyncio
    async def test_successful_refresh_with_snowflake_token(self):
        """Test successful refresh token grant with Snowflake token."""
        from legifrance_mcp.src.oauth.models import RefreshTokenRequest

        token_request = RefreshTokenRequest(
            grant_type="refresh_token",
            refresh_token="valid_refresh_token",
            client_id="test_client",
            client_secret="test_secret",
            scope="read write",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_refresh_token.return_value = {
            "client_id": "test_client",
            "scope": "read",
            "snowflake_refresh_token": "snowflake_refresh_token",
        }
        oauth_service.validate_client.return_value = {"id": "test_client"}

        with patch("legifrance_mcp.src.oauth.controller.OAuth2Handler") as mock_handler:
            mock_handler.get_access_token_from_refresh_token.return_value = {
                "access_token": "new_snowflake_access_token",
                "refresh_token": "new_snowflake_refresh_token",
                "expires_in": 7200,
            }

            result = await controller.handle_refresh_token_grant_pydantic(
                token_request, oauth_service
            )

            assert result["access_token"] == "new_snowflake_access_token"
            assert result["refresh_token"] == "new_snowflake_refresh_token"
            assert result["token_type"] == "Bearer"
            assert result["expires_in"] == 7200
            assert result["scope"] == "read write"

            mock_handler.get_access_token_from_refresh_token.assert_called_once_with(
                "snowflake_refresh_token"
            )

    @pytest.mark.asyncio
    async def test_snowflake_refresh_failure_fallback(self):
        """Test fallback when Snowflake token refresh fails."""
        from legifrance_mcp.src.oauth.models import RefreshTokenRequest

        token_request = RefreshTokenRequest(
            grant_type="refresh_token",
            refresh_token="valid_refresh_token",
            client_id="test_client",
            client_secret="test_secret",
            scope=None,
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_refresh_token.return_value = {
            "client_id": "test_client",
            "scope": "read",
            "snowflake_refresh_token": "invalid_snowflake_refresh_token",
        }
        oauth_service.validate_client.return_value = {"id": "test_client"}

        with patch("legifrance_mcp.src.oauth.controller.OAuth2Handler") as mock_handler:
            mock_handler.get_access_token_from_refresh_token.side_effect = Exception(
                "Snowflake error"
            )

            result = await controller.handle_refresh_token_grant_pydantic(
                token_request, oauth_service
            )

            assert result["access_token"] == "refreshed_access_token_placeholder"
            assert result["token_type"] == "Bearer"
            assert result["expires_in"] == 3600
            assert result["scope"] == "read"

    @pytest.mark.asyncio
    async def test_successful_refresh_without_snowflake_token(self):
        """Test successful refresh token grant without Snowflake token."""
        from legifrance_mcp.src.oauth.models import RefreshTokenRequest

        token_request = RefreshTokenRequest(
            grant_type="refresh_token",
            refresh_token="valid_refresh_token",
            client_id="test_client",
            client_secret="test_secret",
            scope="write",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_refresh_token.return_value = {
            "client_id": "test_client",
            "scope": "read",
        }
        oauth_service.validate_client.return_value = {"id": "test_client"}

        result = await controller.handle_refresh_token_grant_pydantic(
            token_request, oauth_service
        )

        assert result["access_token"] == "refreshed_access_token_placeholder"
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] == 3600
        assert result["scope"] == "write"


class TestClientCredentialsGrantEdgeCases:
    """Test handle_client_credentials_grant_pydantic edge cases."""

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_invalid_client_credentials(self, mock_settings):
        """Test client credentials grant with invalid credentials."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        from legifrance_mcp.src.oauth.models import (
            ClientCredentialsTokenRequest,
        )

        token_request = ClientCredentialsTokenRequest(
            grant_type="client_credentials",
            client_id="invalid_client",
            client_secret="invalid_secret",
            scope=None,
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client.return_value = None

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_client_credentials_grant_pydantic(
                token_request, oauth_service
            )

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_client"
        assert (
            "Invalid client credentials" in _detail(exc_info.value)["error_description"]
        )
        oauth_service.validate_client.assert_called_once_with(
            "invalid_client", "invalid_secret"
        )

    @patch("legifrance_mcp.src.oauth.controller.settings")
    @pytest.mark.asyncio
    async def test_missing_client_id(self, mock_settings):
        """Test client credentials grant with client_id explicitly None."""
        mock_settings.COMPATIBLE_WITH_CURSOR = False

        from legifrance_mcp.src.oauth.models import (
            ClientCredentialsTokenRequest,
        )

        token_request = ClientCredentialsTokenRequest(
            grant_type="client_credentials",
            client_id=None,
            client_secret=None,
            scope=None,
        )

        oauth_service = AsyncMock(spec=OAuthService)

        with pytest.raises(HTTPException) as exc_info:
            await controller.handle_client_credentials_grant_pydantic(
                token_request, oauth_service
            )

        assert exc_info.value.status_code == 400
        assert _detail(exc_info.value)["error"] == "invalid_client"
        assert "Client ID is required" in _detail(exc_info.value)["error_description"]

    @pytest.mark.asyncio
    async def test_successful_client_credentials_grant(self):
        """Test successful client credentials grant."""
        from legifrance_mcp.src.oauth.models import (
            ClientCredentialsTokenRequest,
        )

        token_request = ClientCredentialsTokenRequest(
            grant_type="client_credentials",
            client_id="test_client",
            client_secret="test_secret",
            scope="admin",
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client.return_value = {"id": "test_client"}

        result = await controller.handle_client_credentials_grant_pydantic(
            token_request, oauth_service
        )

        assert result["access_token"] == "client_credentials_access_token_placeholder"
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] == 3600
        assert result["scope"] == "admin"

    @pytest.mark.asyncio
    async def test_successful_client_credentials_grant_default_scope(self):
        """Test successful client credentials grant with default scope."""
        from legifrance_mcp.src.oauth.models import (
            ClientCredentialsTokenRequest,
        )

        token_request = ClientCredentialsTokenRequest(
            grant_type="client_credentials",
            client_id="test_client",
            client_secret="test_secret",
            scope=None,
        )

        oauth_service = AsyncMock(spec=OAuthService)
        oauth_service.validate_client.return_value = {"id": "test_client"}

        result = await controller.handle_client_credentials_grant_pydantic(
            token_request, oauth_service
        )

        assert result["access_token"] == "client_credentials_access_token_placeholder"
        assert result["token_type"] == "Bearer"
        assert result["expires_in"] == 3600
        assert result["scope"] == "client"
