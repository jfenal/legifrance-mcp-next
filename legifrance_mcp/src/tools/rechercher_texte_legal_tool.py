"""Legal text search tool for the Legifrance MCP Server.

Searches articles within legal texts (lois, ordonnances, décrets, arrêtés)
via pylegifrance.fonds.loda.Loda.
"""

from typing import Any, Dict, Optional

from pylegifrance.fonds.loda import Loda
from pylegifrance.models.loda.search import SearchRequest as LodaSearchRequest

from legifrance_mcp.src.legifrance_client import (
    clamp_page_size,
    format_results,
    get_legifrance_client,
    normalize_type_recherche,
)
from legifrance_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


async def rechercher_dans_texte_legal(
    search: Optional[str] = None,
    text_id: Optional[str] = None,
    champ: Optional[str] = None,
    type_recherche: Optional[str] = None,
    proximite: Optional[int] = None,
    page_size: Optional[int] = None,
) -> Dict[str, Any]:
    """Recherche un article dans un texte légal (loi, ordonnance, décret, arrêté).

    TOOL_NAME=rechercher_dans_texte_legal
    DISPLAY_NAME=Recherche dans les textes légaux
    USECASE=Trouver un article précis ou des mots-clés dans une loi, ordonnance, décret ou arrêté
    INSTRUCTIONS=1. Fournir text_id (numéro de texte, ex "78-17") et/ou search (mots-clés), 2. Affiner avec champ/type_recherche/proximite si besoin
    INPUT_DESCRIPTION=text_id (numéro du texte, format AAAA-NUMERO), search (mots-clés ou numéro d'article), champ ("ALL"/"TITLE"/"TABLE"/"NUM_ARTICLE"/"ARTICLE"), type_recherche ("TOUS_LES_MOTS_DANS_UN_CHAMP"/"EXPRESSION_EXACTE"/"AU_MOINS_UN_MOT"), proximite (distance max en mots), page_size (max 20)
    OUTPUT_DESCRIPTION=Dictionnaire avec status, résultats formatés en Markdown, et message
    EXAMPLES=rechercher_dans_texte_legal(text_id="78-17", search="7", champ="NUM_ARTICLE"), rechercher_dans_texte_legal(search="signature électronique validité conditions")
    PREREQUISITES=None
    RELATED_TOOLS=rechercher_code (pour les codes), get_text_history (historique des modifications d'un texte)

    I/O-bound operation - uses async def for the underlying Légifrance API call.

    Args:
        search: Mots-clés de recherche ou numéro d'article.
        text_id: Le numéro du texte (format AAAA-NUMERO, ex: "78-17").
        champ: Champ de recherche.
        type_recherche: Type de recherche.
        proximite: Distance maximale en mots entre les termes recherchés.
        page_size: Nombre de résultats (max 20).

    Returns:
        Dict[str, Any]: status, résultats formatés en Markdown, et message.
    """
    try:
        kwargs: Dict[str, Any] = {}
        if search is not None:
            kwargs["search"] = search
        if text_id is not None:
            kwargs["text_id"] = text_id
        if champ is not None:
            kwargs["champ"] = champ
        if type_recherche is not None:
            kwargs["type_recherche"] = normalize_type_recherche(type_recherche)
        if page_size is not None:
            kwargs["page_size"] = clamp_page_size(page_size)
        if proximite is not None:
            kwargs["proximity"] = proximite

        query = LodaSearchRequest(**kwargs)
        results = Loda(get_legifrance_client()).search(query)

        if not results:
            return {
                "status": "success",
                "operation": "rechercher_dans_texte_legal",
                "result": "Aucun résultat.",
                "message": "Aucun texte trouvé pour cette recherche.",
            }

        return {
            "status": "success",
            "operation": "rechercher_dans_texte_legal",
            "result": format_results(results, lambda t: t.to_markdown()),
            "message": f"{len(results)} résultat(s) trouvé(s).",
        }

    except Exception as e:
        logger.error(f"Error in rechercher_dans_texte_legal tool: {e}")
        return {
            "status": "error",
            "operation": "rechercher_dans_texte_legal",
            "error": str(e),
            "message": "Échec de la recherche dans le texte légal.",
        }
