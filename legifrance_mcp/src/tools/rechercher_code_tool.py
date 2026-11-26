"""Code search tool for the Legifrance MCP Server.

Searches articles in French legal codes (Code civil, Code du travail, ...)
via pylegifrance.fonds.code.Code.
"""

from typing import Any, Dict, Optional

from pylegifrance.fonds.code import Code
from pylegifrance.models.code.enum import NomCode, TypeChampCode
from pylegifrance.models.constants import EtatJuridique

from legifrance_mcp.src.legifrance_client import (
    CHAMP_TO_TYPE_CHAMP_CODE,
    clamp_page_size,
    format_results,
    get_legifrance_client,
    resolve_code_name,
)
from legifrance_mcp.utils.pylogger import get_python_logger

logger = get_python_logger()


def _format_article(article: Any) -> str:
    lines = [f"## {article.code_name or ''} — art. {article.number}".strip()]
    if article.title:
        lines.append(f"**Titre**: {article.title}")
    if article.legal_status:
        lines.append(f"**État**: {article.legal_status}")
    if article.version_date:
        lines.append(f"**Version du**: {article.version_date.strftime('%d/%m/%Y')}")
    if article.url:
        lines.append(f"**URL**: {article.url}")
    lines.append("")
    if article.content:
        lines.append(article.content)
    return "\n".join(lines)


async def rechercher_code(
    search: str,
    code_name: str,
    champ: Optional[str] = None,
    sort: Optional[str] = None,
    type_recherche: Optional[str] = None,
    proximite: Optional[int] = None,
    page_size: Optional[int] = None,
    fetch_all: bool = False,
    uniquement_en_vigueur: bool = True,
) -> Dict[str, Any]:
    """Recherche des articles juridiques dans les codes de loi français.

    TOOL_NAME=rechercher_code
    DISPLAY_NAME=Recherche dans les codes juridiques
    USECASE=Trouver des articles dans un code juridique français (Code civil, Code du travail, etc.)
    INSTRUCTIONS=1. Fournir les termes de recherche, 2. Indiquer le nom du code, 3. Affiner avec champ/type_recherche/proximite si besoin
    INPUT_DESCRIPTION=search (termes de recherche), code_name (ex: "Code civil"), champ ("ALL"/"TITLE"/"TABLE"/"NUM_ARTICLE"/"ARTICLE"), sort, type_recherche, proximite (distance max en mots), page_size (max 20), fetch_all (utiliser la taille de page maximale), uniquement_en_vigueur (défaut: true, ne renvoie que la version actuellement en vigueur ; mettre à false pour voir aussi les versions historiques/abrogées)
    OUTPUT_DESCRIPTION=Dictionnaire avec status, résultats formatés en Markdown (un article par résultat, URL Légifrance incluse), et message
    EXAMPLES=rechercher_code("pacte civil de solidarité", "Code civil"), rechercher_code("1240", "Code civil", champ="NUM_ARTICLE")
    PREREQUISITES=Connaître le nom du code à interroger
    RELATED_TOOLS=rechercher_dans_texte_legal (pour les lois/décrets hors codes), get_text_history (historique des modifications)

    I/O-bound operation - uses async def for the underlying Légifrance API call.

    Args:
        search: Termes de recherche ou numéro d'article.
        code_name: Nom du code juridique (ex: "Code civil", "Code du travail").
        champ: Zone de recherche ("ALL", "TITLE", "TABLE", "NUM_ARTICLE", "ARTICLE").
        sort: Tri des résultats ("PERTINENCE", "DATE_ASC", "DATE_DESC").
        type_recherche: Type de recherche.
        proximite: Distance maximale en mots entre les termes recherchés.
        page_size: Nombre de résultats (max 20).
        fetch_all: Utiliser la taille de page maximale (20) plutôt que la valeur par défaut.
        uniquement_en_vigueur: Ne renvoyer que la version actuellement en vigueur de
            chaque article (par défaut), plutôt que toutes les versions historiques.

    Returns:
        Dict[str, Any]: status, résultats formatés en Markdown, et message.
    """
    try:
        resolved = resolve_code_name(code_name)
        if resolved is None:
            examples = ", ".join(member.value for member in list(NomCode)[:5])
            return {
                "status": "error",
                "operation": "rechercher_code",
                "error": f"Code juridique inconnu: {code_name!r}",
                "message": f"Exemples de codes valides: {examples}, ...",
            }

        builder = (
            Code(get_legifrance_client()).search().in_code(resolved).with_formatter()
        )
        if uniquement_en_vigueur:
            builder = builder.with_legal_status([EtatJuridique.VIGUEUR])

        if champ == "NUM_ARTICLE" and search:
            builder = builder.article_number(search)
        elif search:
            field = (
                CHAMP_TO_TYPE_CHAMP_CODE.get(champ, TypeChampCode.ALL)
                if champ
                else TypeChampCode.ALL
            )
            builder = builder.text(search, in_field=field, proximity=proximite)

        effective_page_size = clamp_page_size(20 if fetch_all else page_size)
        if effective_page_size:
            builder = builder.paginate(page_size=effective_page_size)

        results = builder.execute()

        if not results:
            return {
                "status": "success",
                "operation": "rechercher_code",
                "result": "Aucun résultat.",
                "message": "Aucun article trouvé pour cette recherche.",
            }

        return {
            "status": "success",
            "operation": "rechercher_code",
            "result": format_results(results, _format_article),
            "message": f"{len(results)} résultat(s) trouvé(s).",
        }

    except Exception as e:
        logger.error(f"Error in rechercher_code tool: {e}")
        return {
            "status": "error",
            "operation": "rechercher_code",
            "error": str(e),
            "message": "Échec de la recherche dans le code juridique.",
        }
