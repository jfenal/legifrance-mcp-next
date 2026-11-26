"""Agent feedback pipeline.

`legifrance_report_discovery` lets the calling agent report mechanical
tool/API friction (empty results, confusing param shapes, silent
clamping) to help improve this MCP server. This module never submits
anything to GitHub on its own -- it has no reliable way to know whether
the calling agent's environment even has the means to open an issue. It
sanitizes the report, logs it locally, and returns submission-ready
content plus an instruction for the agent to involve the user before
choosing whether and how to deliver it anywhere.

Modeled on google-workspace-mcp's workspace_report_discovery, adapted to
this template's Dict[str, Any]/status tool-return convention (see
legifrance_mcp/src/tools/README.md) instead of returning a raw JSON
string, and to the Légifrance/Judilibre domain instead of Workspace
object types.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

from legifrance_mcp.src.settings import settings
from legifrance_mcp.utils.log_paths import base_log_dir
from legifrance_mcp.utils.pylogger import get_python_logger
from legifrance_mcp.utils.redaction import redact

logger = get_python_logger()

LOG_DIR = base_log_dir()
FEEDBACK_LOG_PATH = LOG_DIR / "tool-discovery-feedback.jsonl"

# This project has a small, fixed set of real tool names (unlike
# google-workspace-mcp's larger, registry-based surface), so they're just
# listed directly here rather than read from a shared tool registry.
_KNOWN_TOOL_NAMES = frozenset(
    {
        "rechercher_code",
        "rechercher_dans_texte_legal",
        "rechercher_jurisprudence_judiciaire",
        "rechercher_jurisprudence_judilibre",
        "get_text_history",
        "legifrance_report_discovery",
    }
)

JsonDict = Dict[str, Any]


def sanitize_for_submission(entry: JsonDict) -> tuple[JsonDict, bool]:
    """Redact free-text fields (`action_sequence`, `outcome`) in a copy of `entry`.

    Returns the sanitized copy (with a `redacted` flag set on it) and a
    plain bool of the same flag for convenience at call sites. Never
    mutates the input. Only `action_sequence` and `outcome` carry free
    text that could embed an ID, email, or path -- every other field is
    a structured enum/list value. Real tool names (`_KNOWN_TOOL_NAMES`)
    are preserved so a report like "called rechercher_jurisprudence_judilibre
    with wrong page_size" isn't mangled into an unreadable [redacted-id].
    """
    sanitized = dict(entry)
    redacted = False

    action_sequence = cast(List[str], sanitized.get("action_sequence", []))
    clean_actions: List[str] = []
    for action in action_sequence:
        clean = redact(action, preserve=_KNOWN_TOOL_NAMES)
        if clean != action:
            redacted = True
        clean_actions.append(cast(str, clean))
    sanitized["action_sequence"] = clean_actions

    outcome = cast(Optional[str], sanitized.get("outcome"))
    if outcome is not None:
        clean_outcome = redact(outcome, preserve=_KNOWN_TOOL_NAMES)
        if clean_outcome != outcome:
            redacted = True
        sanitized["outcome"] = clean_outcome

    sanitized["redacted"] = redacted
    return sanitized, redacted


def _write_local_log(entry: JsonDict) -> None:
    """Append `entry` to the stable local feedback log, creating the dir if needed."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with FEEDBACK_LOG_PATH.open("a") as f:
        f.write(json.dumps(entry) + "\n")


async def legifrance_report_discovery(
    fond_types: List[str],
    tools_used: List[str],
    action_sequence: List[str],
    outcome: str,
    difficulty: str = "easy",
    friction_category: Optional[str] = None,
    tools_tried_but_wrong: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Report a mechanical tool/API friction point to help improve this MCP server.

    TOOL_NAME=legifrance_report_discovery
    DISPLAY_NAME=Rapporter un problème d'utilisation des outils
    USECASE=Signaler un problème mécanique (résultat vide inattendu, paramètre confus, erreur API) après avoir utilisé un ou plusieurs outils de ce serveur
    INSTRUCTIONS=1. Décrire la séquence d'actions et le résultat obtenu, 2. Ne jamais citer le contenu des textes/décisions consultés, 3. Présenter le résultat à l'utilisateur avant tout envoi
    INPUT_DESCRIPTION=fond_types (ex: "code_article", "loda_text", "juri_decision", "judilibre_decision"), tools_used, action_sequence, outcome, difficulty ("easy"/"moderate"/"hard"), friction_category ("tool_returned_empty"/"param_shape_confusion"/"index_mapping_error"/"missing_capability"/"api_error"/"other"), tools_tried_but_wrong
    OUTPUT_DESCRIPTION=Dictionnaire avec status, chemin du journal local, indicateur de rédaction, et un titre/corps suggérés pour une issue GitHub -- rien n'est jamais soumis automatiquement
    EXAMPLES=legifrance_report_discovery(["code_article"], ["rechercher_code"], ["appel avec search=bail commercial"], "0 résultat alors qu'il existe des articles correspondants")
    PREREQUISITES=Avoir terminé une tâche utilisant un ou plusieurs outils de ce serveur
    RELATED_TOOLS=Aucun -- ce n'est pas un outil de recherche juridique

    I/O-bound operation - uses async def for the local log write.

    Never quote or paraphrase article/decision content, titles, or case
    numbers beyond what's needed to name which tool misbehaved. Describe
    only the mechanical sequence of tool calls and the technical
    error/unexpected result. This module never submits anything
    anywhere on its own: it logs locally and returns suggested content
    for the agent to review with the user first.

    Args:
        fond_types: Which Légifrance/Judilibre fonds were touched, e.g.
            "code_article", "loda_text", "juri_decision",
            "judilibre_decision". Categories only.
        tools_used: Names of the tools actually called.
        action_sequence: The mechanical sequence of tool calls and their
            results, in order.
        outcome: What went wrong, in technical terms.
        difficulty: "easy", "moderate", or "hard".
        friction_category: One of "tool_returned_empty",
            "param_shape_confusion", "index_mapping_error",
            "missing_capability", "api_error", "other".
        tools_tried_but_wrong: Tools tried before finding the right one,
            if any.

    Returns:
        Dict[str, Any]: status, local log path, redaction flag, and a
        suggested GitHub issue title/body for the agent to review with
        the user.
    """
    try:
        entry: JsonDict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "fond_types": fond_types,
            "tools_used": tools_used,
            "difficulty": difficulty,
            "action_sequence": action_sequence,
            "outcome": outcome,
        }
        if friction_category:
            entry["friction_category"] = friction_category
        if tools_tried_but_wrong:
            entry["wrong_tools"] = tools_tried_but_wrong

        sanitized_entry, redacted = sanitize_for_submission(entry)
        _write_local_log(sanitized_entry)

        logger.info(
            "discovery_feedback",
            difficulty=difficulty,
            friction_category=friction_category,
        )

        fond_types_label = ", ".join(fond_types) if fond_types else "fond non précisé"
        title = (
            f"MCP friction: {friction_category or 'unspecified'} ({fond_types_label})"
        )

        body_lines = [
            f"**Difficulty:** {difficulty}",
            f"**Tools used:** {', '.join(tools_used)}",
        ]
        if tools_tried_but_wrong:
            body_lines.append(
                f"**Tried but wrong:** {', '.join(tools_tried_but_wrong)}"
            )
        body_lines.append("**Action sequence:**")
        body_lines.extend(
            f"- {step}" for step in cast(List[str], sanitized_entry["action_sequence"])
        )
        body_lines.append(f"**Outcome:** {sanitized_entry['outcome']}")

        return {
            "status": "logged_locally",
            "operation": "legifrance_report_discovery",
            "local_log_path": str(FEEDBACK_LOG_PATH),
            "redacted": redacted,
            "suggested_repo": settings.FEEDBACK_REPO,
            "suggested_title": title,
            "suggested_body": "\n".join(body_lines),
            "message": (
                "This has been logged locally only -- nothing has been sent "
                "anywhere. Tell the user this feedback exists to improve "
                "this MCP server's tools (descriptions, bugs, missing "
                "capabilities) -- it is not a report about their legal "
                "research task. Ask whether and how they would like to "
                "submit it: a GitHub issue against "
                f"{settings.FEEDBACK_REPO} (only if you already have the "
                "means to open one and the user approves), or not at all. "
                "Do not submit this anywhere without the user's explicit "
                "go-ahead."
            ),
        }

    except Exception as e:
        logger.error(f"Error in legifrance_report_discovery tool: {e}")
        return {
            "status": "error",
            "operation": "legifrance_report_discovery",
            "error": str(e),
            "message": "Échec de l'enregistrement du retour d'utilisation.",
        }
