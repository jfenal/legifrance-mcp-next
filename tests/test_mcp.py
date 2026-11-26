"""Tests for the MCP server module."""

from unittest.mock import Mock, patch

import pytest

from legifrance_mcp.src.mcp import LegifranceMCPServer


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
        # it again explicitly, so the 5 tools are registered twice over.
        assert mock_mcp.tool.call_count >= 5

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
