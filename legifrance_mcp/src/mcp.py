"""Legifrance MCP Server implementation.

This module contains the main Legifrance MCP Server class that provides
tools for querying French legal databases (Légifrance, Judilibre) for MCP
clients. It uses FastMCP to register and manage MCP capabilities.
"""

from fastmcp import FastMCP

from legifrance_mcp.src.rate_limit import judilibre_rate_limit, legifrance_rate_limit
from legifrance_mcp.src.settings import settings

# Import tools from the tools package
from legifrance_mcp.src.tools.feedback_tool import legifrance_feedback
from legifrance_mcp.src.tools.get_text_history_tool import get_text_history
from legifrance_mcp.src.tools.rechercher_code_tool import rechercher_code
from legifrance_mcp.src.tools.rechercher_judilibre_tool import (
    rechercher_jurisprudence_judilibre,
)
from legifrance_mcp.src.tools.rechercher_jurisprudence_administrative_tool import (
    rechercher_jurisprudence_administrative,
)
from legifrance_mcp.src.tools.rechercher_jurisprudence_tool import (
    rechercher_jurisprudence_judiciaire,
)
from legifrance_mcp.src.tools.rechercher_texte_legal_tool import (
    rechercher_dans_texte_legal,
)
from legifrance_mcp.utils.pylogger import (
    force_reconfigure_all_loggers,
    get_python_logger,
)

logger = get_python_logger()


class LegifranceMCPServer:
    """Main Legifrance MCP Server implementation following tools-first architecture.

    This server provides only tools, not resources or prompts, adhering to
    the tools-first architectural pattern for MCP servers.
    """

    def __init__(self):
        """Initialize the MCP server with the Légifrance/Judilibre search tools."""
        try:
            # Initialize FastMCP server
            self.mcp = FastMCP("legifrance")

            # Force reconfigure all loggers after FastMCP initialization to ensure structured logging
            force_reconfigure_all_loggers(
                settings.PYTHON_LOG_LEVEL, log_file=settings.LOG_FILE_PATH
            )

            self._register_mcp_tools()

            logger.info("Legifrance MCP Server initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize Legifrance MCP Server: {e}")
            raise

    def _register_mcp_tools(self) -> None:
        """Register MCP tools for Légifrance/Judilibre operations (tools-first architecture).

        Registers all available tools with the FastMCP server instance.
        In tools-first architecture, the server only provides tools.
        Currently includes:
        - rechercher_code: Recherche dans les codes juridiques
        - rechercher_dans_texte_legal: Recherche dans les textes légaux
        - rechercher_jurisprudence_judiciaire: Recherche de jurisprudence judiciaire (JURI)
        - rechercher_jurisprudence_administrative: Recherche de jurisprudence administrative (CETAT)
        - rechercher_jurisprudence_judilibre: Recherche de jurisprudence (Judilibre)
        - get_text_history: Historique des modifications d'un texte légal
        - legifrance_feedback: Retour d'utilisation (friction mécanique des outils)
        """
        # Rate-limited at registration time (not by decorating the tool
        # functions directly) to PISTE's real published per-second quotas --
        # 2 req/s for Légifrance-backed tools, 20 req/s for Judilibre -- so
        # unit tests calling these functions directly never hit the limiter.
        self.mcp.tool()(legifrance_rate_limit(rechercher_code))
        self.mcp.tool()(legifrance_rate_limit(rechercher_dans_texte_legal))
        self.mcp.tool()(legifrance_rate_limit(rechercher_jurisprudence_judiciaire))
        self.mcp.tool()(legifrance_rate_limit(rechercher_jurisprudence_administrative))
        self.mcp.tool()(judilibre_rate_limit(rechercher_jurisprudence_judilibre))
        self.mcp.tool()(legifrance_rate_limit(get_text_history))
        # Not rate-limited: writes to a local log file only, no PISTE call.
        self.mcp.tool()(legifrance_feedback)
