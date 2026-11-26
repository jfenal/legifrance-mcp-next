"""Judicial case-law search tool for the Legifrance MCP Server.

Searches the JURI database (Cour de cassation and other judicial courts)
via pylegifrance.fonds.juri.JuriAPI.
"""

from typing import Any, Dict, List, Optional

from pylegifrance.fonds.juri import JuriAPI
from pylegifrance.models.juri.search import SearchRequest as JuriSearchRequest

from legifrance_mcp.src.legifrance_client import (
    MAX_PAGE_SIZE,
    clamp_page_size,
    format_results,
    get_legifrance_client,
    normalize_type_recherche,
)
from legifrance_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()

# Historical tool parameter names differ from pylegifrance's own
# JuriSearchRequest field names.
_JURI_ARG_MAP = {
    "search": "search",
    "publication_bulletin": "publication_bulletin",
    "sort": "sort",
    "champ": "field",
    "type_recherche": "search_type",
    "proximite": "proximity",
    "juridiction_judiciaire": "juridiction_judiciaire",
    "page_size": "page_size",
    "juri_keys": "keys",
}


async def rechercher_jurisprudence_judiciaire(
    search: str,
    publication_bulletin: Optional[List[str]] = None,
    sort: Optional[str] = None,
    champ: Optional[str] = None,
    type_recherche: Optional[str] = None,
    proximite: Optional[int] = None,
    page_size: Optional[int] = None,
    fetch_all: bool = False,
    juri_keys: Optional[List[str]] = None,
    juridiction_judiciaire: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Recherche des jurisprudences judiciaires dans la base JURI de Légifrance.

    TOOL_NAME=rechercher_jurisprudence_judiciaire
    DISPLAY_NAME=Recherche de jurisprudence judiciaire
    USECASE=Trouver des décisions de justice judiciaires (Cour de cassation, cours d'appel) par mots-clés ou numéro d'affaire. Ne couvre PAS le contentieux administratif/fiscal (Conseil d'État) : utiliser rechercher_jurisprudence_administrative pour cela
    INSTRUCTIONS=1. Fournir les termes ou numéro d'affaire, 2. Affiner avec champ/type_recherche/juridiction_judiciaire/sort si besoin
    INPUT_DESCRIPTION=search (termes ou numéro d'affaire), publication_bulletin (['T'] ou ['F']), sort ("PERTINENCE"/"DATE_DESC"/"DATE_ASC"), champ, type_recherche, proximite, page_size (max 20), fetch_all, juri_keys (champs à extraire), juridiction_judiciaire (liste de juridictions)
    OUTPUT_DESCRIPTION=Dictionnaire avec status, décisions formatées en Markdown, et message
    EXAMPLES=rechercher_jurisprudence_judiciaire("rupture brutale des relations commerciales établies", sort="DATE_DESC")
    PREREQUISITES=None
    RELATED_TOOLS=rechercher_jurisprudence_administrative (pour le Conseil d'État/contentieux administratif et fiscal), rechercher_jurisprudence_judilibre (source complémentaire), rechercher_code/rechercher_dans_texte_legal (pour retrouver les textes visés)

    I/O-bound operation - uses async def for the underlying Légifrance API call.

    Returns:
        Dict[str, Any]: status, décisions formatées en Markdown, et message.
    """
    try:
        arguments: Dict[str, Any] = {
            "search": search,
            "publication_bulletin": publication_bulletin,
            "sort": sort,
            "champ": champ,
            "type_recherche": type_recherche,
            "proximite": proximite,
            "juridiction_judiciaire": juridiction_judiciaire,
            "page_size": page_size,
            "juri_keys": juri_keys,
        }
        kwargs: Dict[str, Any] = {
            new_key: arguments[old_key]
            for old_key, new_key in _JURI_ARG_MAP.items()
            if arguments.get(old_key) is not None
        }
        if "search_type" in kwargs:
            kwargs["search_type"] = normalize_type_recherche(kwargs["search_type"])
        # JuriSearchRequest.fetch_all is never read by JuriAPI.search(); request
        # the largest single page instead.
        if fetch_all:
            kwargs["page_size"] = MAX_PAGE_SIZE
        elif "page_size" in kwargs:
            kwargs["page_size"] = clamp_page_size(kwargs["page_size"])

        query = JuriSearchRequest(**kwargs)
        results = JuriAPI(get_legifrance_client()).search(query)

        if not results:
            return {
                "status": "success",
                "operation": "rechercher_jurisprudence_judiciaire",
                "result": "Aucun résultat.",
                "message": "Aucune décision trouvée pour cette recherche.",
            }

        return {
            "status": "success",
            "operation": "rechercher_jurisprudence_judiciaire",
            "result": format_results(results, lambda d: d.to_markdown()),
            "message": f"{len(results)} résultat(s) trouvé(s).",
        }

    except Exception as e:
        logger.error(f"Error in rechercher_jurisprudence_judiciaire tool: {e}")
        return {
            "status": "error",
            "operation": "rechercher_jurisprudence_judiciaire",
            "error": str(e),
            "message": "Échec de la recherche de jurisprudence.",
        }
