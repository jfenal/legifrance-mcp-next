"""Judilibre case-law search tool for the Legifrance MCP Server.

Searches decisions via the Judilibre API (Cour de cassation and lower
courts), complementing rechercher_jurisprudence_judiciaire.
"""

from typing import Any, Dict, List, Optional

from pylegifrance.fonds.judilibre import JudilibreAPI

from legifrance_mcp.src.legifrance_client import (
    clamp_page_size,
    format_results,
    get_judilibre_client,
)
from legifrance_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


async def rechercher_jurisprudence_judilibre(
    search: str = "",
    jurisdiction: Optional[List[str]] = None,
    chamber: Optional[List[str]] = None,
    date_start: Optional[str] = None,
    date_end: Optional[str] = None,
    page_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Recherche des décisions de justice via l'API Judilibre.

    TOOL_NAME=rechercher_jurisprudence_judilibre
    DISPLAY_NAME=Recherche de jurisprudence (Judilibre)
    USECASE=Trouver des décisions de justice via Judilibre (Cour de cassation et juridictions du fond), en complément de rechercher_jurisprudence_judiciaire
    INSTRUCTIONS=1. Fournir les termes de recherche, 2. Filtrer par juridiction/chambre/dates si besoin
    INPUT_DESCRIPTION=search (termes), jurisdiction (liste de juridictions), chamber (liste de chambres), date_start/date_end (YYYY-MM-DD), page_size (max 20)
    OUTPUT_DESCRIPTION=Dictionnaire avec status, décisions formatées en Markdown, et message
    EXAMPLES=rechercher_jurisprudence_judilibre("licenciement sans cause réelle et sérieuse")
    PREREQUISITES=La variable d'environnement JUDILIBRE_KEY_ID doit être configurée
    RELATED_TOOLS=rechercher_jurisprudence_judiciaire (source complémentaire)

    I/O-bound operation - uses async def for the underlying Judilibre API call.

    Returns:
        Dict[str, Any]: status, décisions formatées en Markdown, et message.
    """
    try:
        client = get_judilibre_client()
    except ValueError as e:
        return {
            "status": "error",
            "operation": "rechercher_jurisprudence_judilibre",
            "error": str(e),
            "message": "Configuration Judilibre manquante.",
        }

    try:
        kwargs: Dict[str, Any] = {}
        if jurisdiction is not None:
            kwargs["jurisdiction"] = jurisdiction
        if chamber is not None:
            kwargs["chamber"] = chamber
        if date_start is not None:
            kwargs["date_start"] = date_start
        if date_end is not None:
            kwargs["date_end"] = date_end
        if page_size is not None:
            kwargs["page_size"] = clamp_page_size(page_size)

        results = JudilibreAPI(client).search(search, **kwargs)

        if not results:
            return {
                "status": "success",
                "operation": "rechercher_jurisprudence_judilibre",
                "result": "Aucun résultat.",
                "message": "Aucune décision trouvée pour cette recherche.",
            }

        return {
            "status": "success",
            "operation": "rechercher_jurisprudence_judilibre",
            "result": format_results(results, lambda d: d.to_markdown()),
            "message": f"{len(results)} résultat(s) trouvé(s).",
        }

    except Exception as e:
        logger.error(f"Error in rechercher_jurisprudence_judilibre tool: {e}")
        return {
            "status": "error",
            "operation": "rechercher_jurisprudence_judilibre",
            "error": str(e),
            "message": "Échec de la recherche de jurisprudence Judilibre.",
        }
