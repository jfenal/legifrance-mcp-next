"""Direct current-article lookup tool for the Legifrance MCP Server.

Fetches the currently in-force version of a single article by code name and
number via pylegifrance.fonds.code.Code.get_article, instead of sampling and
filtering historical versions from rechercher_code's full-text search.
"""

from typing import Any, Dict

from pylegifrance.fonds.code import Code
from pylegifrance.models.code.enum import NomCode

from legifrance_mcp.src.legifrance_client import (
    get_legifrance_client,
    resolve_code_name,
)
from legifrance_mcp.src.tools.rechercher_code_tool import _format_article
from legifrance_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


async def get_article(code_name: str, num: str) -> Dict[str, Any]:
    """Récupère la version actuellement en vigueur d'un article, sans ambiguïté.

    TOOL_NAME=get_article
    DISPLAY_NAME=Article en vigueur
    USECASE=Obtenir directement le texte actuellement en vigueur d'un article dont le code et le numéro sont déjà connus
    INSTRUCTIONS=1. Fournir le nom du code (ex: "Code civil"), 2. Fournir le numéro de l'article (ex: "1134", "787 B", "L. 1121-1")
    INPUT_DESCRIPTION=code_name (ex: "Code civil"), num (numéro de l'article)
    OUTPUT_DESCRIPTION=Dictionnaire avec status, article formaté en Markdown (URL Légifrance incluse), et message
    EXAMPLES=get_article("Code civil", "1134"), get_article("Code général des impôts", "787 B")
    PREREQUISITES=Connaître déjà le code et le numéro de l'article visé
    RELATED_TOOLS=rechercher_code (pour trouver un article par mots-clés quand le numéro exact n'est pas connu)

    I/O-bound operation - uses async def for the underlying Légifrance API calls.

    Contrairement à rechercher_code (recherche plein texte, qui doit
    échantillonner puis filtrer les versions historiques d'un article par
    état juridique), cet outil appelle directement /consult/getArticleWithIdAndNum
    : un seul article est renvoyé, et c'est toujours la version actuellement
    en vigueur. Limitation (documentée par l'API Légifrance) : ne trouve pas
    un article dont la version actuelle a une entrée en vigueur différée
    (future).

    Args:
        code_name: Nom du code juridique (ex: "Code civil", "Code du travail").
        num: Numéro de l'article (ex: "1134", "787 B", "L. 1121-1").

    Returns:
        Dict[str, Any]: status, article formaté en Markdown, et message.
    """
    try:
        resolved = resolve_code_name(code_name)
        if resolved is None:
            examples = ", ".join(member.value for member in list(NomCode)[:5])
            return {
                "status": "error",
                "operation": "get_article",
                "error": f"Code juridique inconnu: {code_name!r}",
                "message": f"Exemples de codes valides: {examples}, ...",
            }

        article = Code(get_legifrance_client()).get_article(resolved.value, num)

        return {
            "status": "success",
            "operation": "get_article",
            "result": _format_article(article),
            "message": "Article récupéré avec succès.",
        }

    except ValueError as e:
        return {
            "status": "success",
            "operation": "get_article",
            "result": "Aucun résultat.",
            "message": str(e),
        }

    except Exception as e:
        logger.error(f"Error in get_article tool: {e}")
        return {
            "status": "error",
            "operation": "get_article",
            "error": str(e),
            "message": "Échec de la récupération de l'article.",
        }
