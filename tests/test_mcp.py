"""Tests for the MCP server module."""

from unittest.mock import Mock, patch

import pytest

from legifrance_mcp.src.mcp import LegifranceMCPServer
from legifrance_mcp.src.tools.get_text_history_tool import get_text_history
from legifrance_mcp.src.tools.rechercher_code_tool import rechercher_code
from legifrance_mcp.src.tools.rechercher_judilibre_tool import (
    rechercher_jurisprudence_judilibre,
)
from legifrance_mcp.src.tools.rechercher_jurisprudence_tool import (
    rechercher_jurisprudence_judiciaire,
)
from legifrance_mcp.src.tools.rechercher_texte_legal_tool import (
    rechercher_dans_texte_legal,
)


class TestLegifranceMCPServer:
    """Test the LegifranceMCPServer class."""

    @patch("legifrance_mcp.src.mcp.force_reconfigure_all_loggers")
    @patch("legifrance_mcp.src.mcp.settings")
    @patch("legifrance_mcp.src.mcp.FastMCP")
    @patch("legifrance_mcp.src.mcp.logger")
    def test_init_success(
        self, mock_logger, mock_fastmcp, mock_settings, mock_force_reconfigure
    ):
        """Test successful initialization of LegifranceMCPServer."""
        # Arrange
        mock_mcp = Mock()
        mock_fastmcp.return_value = mock_mcp
        mock_settings.PYTHON_LOG_LEVEL = "INFO"

        # Act
        server = LegifranceMCPServer()

        # Assert
        assert server.mcp == mock_mcp
        mock_logger.info.assert_called_with(
            "Legifrance MCP Server initialized successfully"
        )
        # In tools-first architecture, we only register tools
        mock_mcp.tool.assert_called()

    @patch("legifrance_mcp.src.mcp.force_reconfigure_all_loggers")
    @patch("legifrance_mcp.src.mcp.settings")
    @patch("legifrance_mcp.src.mcp.FastMCP")
    @patch("legifrance_mcp.src.mcp.logger")
    def test_init_failure(
        self, mock_logger, mock_fastmcp, mock_settings, mock_force_reconfigure
    ):
        """Test initialization failure handling."""
        # Arrange
        mock_fastmcp.side_effect = Exception("Test error")
        mock_settings.PYTHON_LOG_LEVEL = "INFO"

        # Act & Assert
        with pytest.raises(Exception, match="Test error"):
            LegifranceMCPServer()

        mock_logger.error.assert_called_with(
            "Failed to initialize Legifrance MCP Server: Test error"
        )

    @patch("legifrance_mcp.src.mcp.force_reconfigure_all_loggers")
    @patch("legifrance_mcp.src.mcp.settings")
    @patch("legifrance_mcp.src.mcp.FastMCP")
    def test_register_mcp_tools(
        self, mock_fastmcp, mock_settings, mock_force_reconfigure
    ):
        """Test MCP tools registration."""
        # Arrange
        mock_mcp = Mock()
        mock_fastmcp.return_value = mock_mcp
        mock_settings.PYTHON_LOG_LEVEL = "INFO"
        server = LegifranceMCPServer()

        # Act
        server._register_mcp_tools()

        # Assert
        mock_mcp.tool.assert_called()

    @patch("legifrance_mcp.src.mcp.force_reconfigure_all_loggers")
    @patch("legifrance_mcp.src.mcp.settings")
    @patch("legifrance_mcp.src.mcp.FastMCP")
    def test_register_mcp_tools_functionality(
        self, mock_fastmcp, mock_settings, mock_force_reconfigure
    ):
        """Test that MCP tools registration includes all expected tools."""
        # Arrange
        mock_mcp = Mock()
        mock_fastmcp.return_value = mock_mcp
        mock_settings.PYTHON_LOG_LEVEL = "INFO"
        server = LegifranceMCPServer()

        # Act
        server._register_mcp_tools()

        # Assert
        # Verify that tool() was called multiple times (once for each tool)
        # __init__ already called _register_mcp_tools() once; this test calls
        # it again explicitly, so the 6 tools are registered twice over.
        assert mock_mcp.tool.call_count >= 6

    def test_server_attributes(self):
        """Test that server has required attributes for tools-first architecture."""
        # Arrange & Act
        with (
            patch("legifrance_mcp.src.mcp.settings") as mock_settings,
            patch("legifrance_mcp.src.mcp.FastMCP"),
            patch("legifrance_mcp.src.mcp.force_reconfigure_all_loggers"),
        ):
            mock_settings.PYTHON_LOG_LEVEL = "INFO"
            server = LegifranceMCPServer()

        # Assert
        assert hasattr(server, "mcp")
        assert hasattr(server, "_register_mcp_tools")

    @patch("legifrance_mcp.src.mcp.force_reconfigure_all_loggers")
    @patch("legifrance_mcp.src.mcp.settings")
    @patch("legifrance_mcp.src.mcp.FastMCP")
    def test_legifrance_tools_are_rate_limited_to_piste_quota(
        self, mock_fastmcp, mock_settings, mock_force_reconfigure
    ):
        """Each tool backed by the Légifrance API must be registered through
        legifrance_rate_limit (PISTE's published 2 req/s quota), not the
        bare function."""
        mock_mcp = Mock()
        mock_fastmcp.return_value = mock_mcp
        mock_settings.PYTHON_LOG_LEVEL = "INFO"

        LegifranceMCPServer()

        registered_fns = [c.args[0] for c in mock_mcp.tool.return_value.call_args_list]
        for original in [
            rechercher_code,
            rechercher_dans_texte_legal,
            rechercher_jurisprudence_judiciaire,
            get_text_history,
        ]:
            assert original not in registered_fns, (
                f"{original.__name__} is not rate-limited"
            )
            wrapped = next(
                fn
                for fn in registered_fns
                if getattr(fn, "__wrapped__", None) is original
            )
            assert wrapped is not None

    @patch("legifrance_mcp.src.mcp.force_reconfigure_all_loggers")
    @patch("legifrance_mcp.src.mcp.settings")
    @patch("legifrance_mcp.src.mcp.FastMCP")
    def test_judilibre_tool_is_rate_limited_to_piste_quota(
        self, mock_fastmcp, mock_settings, mock_force_reconfigure
    ):
        mock_mcp = Mock()
        mock_fastmcp.return_value = mock_mcp
        mock_settings.PYTHON_LOG_LEVEL = "INFO"

        LegifranceMCPServer()

        registered_fns = [c.args[0] for c in mock_mcp.tool.return_value.call_args_list]
        assert rechercher_jurisprudence_judilibre not in registered_fns
        wrapped = next(
            fn
            for fn in registered_fns
            if getattr(fn, "__wrapped__", None) is rechercher_jurisprudence_judilibre
        )
        assert wrapped is not None

    def test_tools_first_architecture_compliance(self):
        """Test that server adheres to tools-first architecture by not having resource/prompt methods."""
        # Arrange & Act
        with (
            patch("legifrance_mcp.src.mcp.settings") as mock_settings,
            patch("legifrance_mcp.src.mcp.FastMCP"),
            patch("legifrance_mcp.src.mcp.force_reconfigure_all_loggers"),
        ):
            mock_settings.PYTHON_LOG_LEVEL = "INFO"
            server = LegifranceMCPServer()

        # Assert - These methods should NOT exist in tools-first architecture
        assert not hasattr(server, "_register_mcp_resources"), (
            "_register_mcp_resources should not exist in tools-first architecture"
        )
        assert not hasattr(server, "_register_mcp_prompts"), (
            "_register_mcp_prompts should not exist in tools-first architecture"
        )
