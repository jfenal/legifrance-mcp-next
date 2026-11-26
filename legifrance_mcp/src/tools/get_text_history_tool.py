"""Legal text history tool for the Legifrance MCP Server.

Reports the modification history (articles created, modified, repealed) of
a legal text via pylegifrance.fonds.loda.Loda.
"""

from typing import Any, Dict

from pylegifrance.fonds.loda import Loda
from pylegifrance.models.loda.search import SearchRequest as LodaSearchRequest

from legifrance_mcp.src.legifrance_client import (
    MAX_CHARS_SINGLE_DOCUMENT,
    get_legifrance_client,
    truncate,
)
from legifrance_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()

_NO_IMPACT_SENTINEL = "Aucun impact disponible."


def _resolve_loda_text(loda: Loda, text_id: str):
    """Résout text_id vers le TexteLoda complet correspondant.

    Accepte aussi bien un identifiant LEGITEXT/JORFTEXT direct (passé tel
    quel à .fetch()) qu'un numéro "AAAA-NUMERO" (ex: "78-17"), qui doit
    d'abord être résolu via une recherche -- .fetch() seul ne l'accepte pas.
    """
    try:
        texte = loda.fetch(text_id)
        if texte is not None:
            return texte
    except Exception:
        # text_id not matching the LEGITEXT/JORFTEXT shape .fetch() expects
        # (e.g. "78-17") is an expected outcome here, not a real failure --
        # fall through to resolving it via search instead.
        pass

    # From here on, a failure is a real backend problem (auth, network,
    # 5xx), not "this text doesn't exist" -- let it propagate so the caller
    # can report it distinctly from an actual empty result.
    matches = loda.search(LodaSearchRequest(text_id=text_id))
    if not matches:
        return None

    matched_id = matches[0].id
    if matched_id is None:
        return None

    return loda.fetch(matched_id)


async def get_text_history(text_id: str) -> Dict[str, Any]:
    """Retourne l'historique des modifications apportées par un texte légal.

    TOOL_NAME=get_text_history
    DISPLAY_NAME=Historique d'un texte légal
    USECASE=Connaître les versions successives d'un texte et les articles qu'il a créés/modifiés/abrogés
    INSTRUCTIONS=1. Fournir le numéro du texte (ex "78-17" ou un identifiant LEGITEXT)
    INPUT_DESCRIPTION=text_id (numéro du texte, ex: "78-17")
    OUTPUT_DESCRIPTION=Dictionnaire avec status, rapport Markdown (versions + articles créés/modifiés/abrogés), et message
    EXAMPLES=get_text_history("78-17")
    PREREQUISITES=None
    RELATED_TOOLS=rechercher_dans_texte_legal (pour retrouver le texte initialement)

    I/O-bound operation - uses async def for the underlying Légifrance API call.

    Returns:
        Dict[str, Any]: status, rapport formaté en Markdown, et message.
    """
    loda = Loda(get_legifrance_client())
    try:
        texte = _resolve_loda_text(loda, text_id)
    except Exception as exc:
        return {
            "status": "error",
            "operation": "get_text_history",
            "error": str(exc),
            "message": "Erreur lors de la consultation du texte.",
        }

    if texte is None:
        return {
            "status": "success",
            "operation": "get_text_history",
            "result": "Aucun résultat.",
            "message": "Aucun texte trouvé pour cet identifiant.",
        }

    try:
        sections = []

        try:
            versions = texte.versions()
        except Exception:
            # consult/loda/versions is a separate API call from the text
            # fetch itself and can fail independently (observed live: a 403
            # even when the text fetches fine) -- the rest of the report
            # still stands on its own, so this degrades instead of failing
            # the tool.
            versions = []
        if versions:
            lines = ["## Versions"]
            for version in versions:
                start = (
                    version.date_debut.strftime("%d/%m/%Y")
                    if version.date_debut
                    else "?"
                )
                end = (
                    version.date_fin.strftime("%d/%m/%Y")
                    if version.date_fin
                    else "en cours"
                )
                lines.append(f"- {start} → {end} ({version.etat or '?'})")
            sections.append("\n".join(lines))

        report = texte.format_modifications_report()
        if report.strip() == _NO_IMPACT_SENTINEL:
            report = texte.to_markdown()
        sections.append(report)

        return {
            "status": "success",
            "operation": "get_text_history",
            "result": truncate("\n\n---\n\n".join(sections), MAX_CHARS_SINGLE_DOCUMENT),
            "message": "Historique récupéré avec succès.",
        }

    except Exception as e:
        logger.error(f"Error in get_text_history tool: {e}")
        return {
            "status": "error",
            "operation": "get_text_history",
            "error": str(e),
            "message": "Échec de la récupération de l'historique.",
        }
