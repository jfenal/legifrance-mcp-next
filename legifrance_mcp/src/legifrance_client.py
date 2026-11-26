"""Shared pylegifrance client construction and response-shaping helpers.

Ported from the standalone legifrance-mcp project (jfenal/legifrance-mcp),
rewritten to read configuration from this template's Settings instead of
os.getenv() directly.
"""

import unicodedata

from pylegifrance import ApiConfig, LegifranceClient
from pylegifrance.config import (
    PROD_API_URL,
    PROD_TOKEN_URL,
    SANDBOX_API_URL,
    SANDBOX_TOKEN_URL,
)
from pylegifrance.fonds.judilibre import (
    JUDILIBRE_PROD_URL,
    JUDILIBRE_SANDBOX_URL,
    JudilibreClient,
)
from pylegifrance.models.code.enum import NomCode, TypeChampCode

from legifrance_mcp.src.settings import settings

_legifrance_client: LegifranceClient | None = None
_judilibre_client: JudilibreClient | None = None

_JUDILIBRE_URLS = {"sandbox": JUDILIBRE_SANDBOX_URL, "production": JUDILIBRE_PROD_URL}


def _api_config() -> ApiConfig:
    if not settings.LEGIFRANCE_CLIENT_ID or not settings.LEGIFRANCE_CLIENT_SECRET:
        raise ValueError(
            "LEGIFRANCE_CLIENT_ID et LEGIFRANCE_CLIENT_SECRET doivent être définis"
        )
    token_url, api_url = (
        (SANDBOX_TOKEN_URL, SANDBOX_API_URL)
        if settings.PISTE_ENV == "sandbox"
        else (PROD_TOKEN_URL, PROD_API_URL)
    )
    return ApiConfig(
        client_id=settings.LEGIFRANCE_CLIENT_ID,
        client_secret=settings.LEGIFRANCE_CLIENT_SECRET,
        token_url=token_url,
        api_url=api_url,
    )


def get_legifrance_client() -> LegifranceClient:
    """Construit le client Légifrance authentifié directement via PISTE.

    Le client est mis en cache (une seule fois par process) pour que le
    jeton OAuth sous-jacent soit réellement réutilisé d'un appel d'outil à
    l'autre, plutôt que renouvelé à chaque appel.
    """
    global _legifrance_client
    if _legifrance_client is None:
        _legifrance_client = LegifranceClient(_api_config())
    return _legifrance_client


def get_judilibre_client() -> JudilibreClient:
    """Construit le client Judilibre authentifié via PISTE.

    Mis en cache une seule fois par process. Réutilise les identifiants
    PISTE de LEGIFRANCE_CLIENT_ID/SECRET, et dérive l'URL Judilibre
    sandbox/production du même PISTE_ENV que le client Légifrance plutôt
    que de rester figée en sandbox.
    """
    global _judilibre_client
    if _judilibre_client is None:
        if not settings.JUDILIBRE_KEY_ID:
            raise ValueError("JUDILIBRE_KEY_ID doit être défini")
        api_url = _JUDILIBRE_URLS.get(settings.PISTE_ENV, JUDILIBRE_SANDBOX_URL)
        _judilibre_client = JudilibreClient(
            _api_config(), key_id=settings.JUDILIBRE_KEY_ID, api_url=api_url
        )
    return _judilibre_client


def _fold(value: str) -> str:
    """Case- and accent-insensitive normalization.

    E.g. "Code pénal" and "code penal" both fold to "code penal".
    """
    decomposed = unicodedata.normalize("NFKD", value.strip().casefold())
    return "".join(c for c in decomposed if not unicodedata.combining(c))


def resolve_code_name(raw: str) -> NomCode | None:
    """Résout un nom de code saisi par l'appelant vers un membre de NomCode.

    Comparaison insensible à la casse et aux accents sur la valeur
    officielle (ex: "code civil" ou "Code penal" -> NomCode.CC / NomCode.CPD).
    Retourne None si aucun code ne correspond.
    """
    normalized = _fold(raw)
    for member in NomCode:
        if _fold(member.value) == normalized:
            return member
    return None


MAX_RESULTS_PER_RESPONSE = 10
MAX_PAGE_SIZE = 20
MAX_CHARS_PER_RESULT = 4000
MAX_CHARS_SINGLE_DOCUMENT = 8000

_TYPE_RECHERCHE_MAP = {
    # Legacy values from the old dassignies.law proxy that the underlying
    # pylegifrance TypeRecherche enum doesn't accept.
    "EXPRESSION_EXACTE": "EXACTE",
    "AU_MOINS_UN_MOT": "UN_DES_MOTS",
}


def normalize_type_recherche(value: str | None) -> str | None:
    """Maps legacy type_recherche values to pylegifrance's canonical ones."""
    if value is None:
        return None
    return _TYPE_RECHERCHE_MAP.get(value, value)


def truncate(text: str, limit: int = MAX_CHARS_PER_RESULT) -> str:
    """Caps a single result's length to stay within an LLM caller's context budget.

    Rather than inlining arbitrarily large content (full rulings, whole
    laws) unbounded.
    """
    if len(text) <= limit:
        return text
    return (
        text[:limit]
        + "\n\n*(contenu tronqué — affinez votre recherche pour un résultat plus précis)*"
    )


def format_results(results: list, to_text) -> str:
    """Formats a list of results as Markdown, bounded in count and size.

    Caps both the number of results and each result's length so a broad
    search doesn't flood the calling LLM's context budget.
    """
    limited = results[:MAX_RESULTS_PER_RESPONSE]
    parts = [truncate(to_text(item)) for item in limited]
    output = "\n\n---\n\n".join(parts)
    remaining = len(results) - len(limited)
    if remaining > 0:
        output += (
            f"\n\n*({remaining} résultat(s) supplémentaire(s) non affiché(s) "
            "— affinez votre recherche pour réduire le nombre de résultats)*"
        )
    return output


def clamp_page_size(value: int | None) -> int | None:
    """Caps a caller-requested page_size to avoid unbounded upstream fan-out.

    A single tool call can't request more than MAX_PAGE_SIZE results.
    """
    if value is None:
        return None
    return min(value, MAX_PAGE_SIZE)


CHAMP_TO_TYPE_CHAMP_CODE = {
    "ALL": TypeChampCode.ALL,
    "TITLE": TypeChampCode.TITLE,
    "TABLE": TypeChampCode.TABLE,
    "ARTICLE": TypeChampCode.ARTICLE,
}
