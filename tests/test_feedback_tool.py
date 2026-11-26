"""Tests for the agent feedback pipeline (legifrance_feedback).

Modeled on google-workspace-mcp's workspace_report_discovery, adapted to
this template's Dict[str, Any]/status tool-return convention (the
upstream one returns a raw JSON string, which wouldn't follow this
project's own tools-first contract) and to the Légifrance/Judilibre
domain instead of Workspace object types.
"""

import json
from unittest.mock import patch

from legifrance_mcp.src.tools.feedback_tool import (
    legifrance_feedback,
    sanitize_for_submission,
)


class TestSanitizeForSubmission:
    def test_clean_entry_unchanged_and_not_flagged(self):
        entry = {
            "action_sequence": [
                "called rechercher_code with search=pacte civil de solidarité",
                "0 results",
            ],
            "outcome": "expected at least one article from Code civil",
        }
        sanitized, redacted = sanitize_for_submission(entry)
        assert sanitized["action_sequence"] == entry["action_sequence"]
        assert sanitized["outcome"] == entry["outcome"]
        assert redacted is False
        assert sanitized["redacted"] is False

    def test_redacts_id_like_token_in_action_sequence(self):
        entry = {
            "action_sequence": [
                "fetched LEGITEXT00000607072112345678901234 via get_text_history"
            ],
            "outcome": "got a 403 instead of the text",
        }
        sanitized, redacted = sanitize_for_submission(entry)
        assert (
            "LEGITEXT00000607072112345678901234" not in sanitized["action_sequence"][0]
        )
        assert "[redacted-id]" in sanitized["action_sequence"][0]
        assert redacted is True

    def test_redacts_email_in_outcome(self):
        entry = {
            "action_sequence": ["called rechercher_jurisprudence_judiciaire"],
            "outcome": "search for jane.doe@example.com returned nothing",
        }
        sanitized, redacted = sanitize_for_submission(entry)
        assert "jane.doe@example.com" not in sanitized["outcome"]
        assert redacted is True

    def test_preserves_real_tool_names_unredacted(self):
        entry = {
            "action_sequence": [
                "called rechercher_jurisprudence_judilibre with wrong page_size"
            ],
            "outcome": "param was silently clamped with no warning",
        }
        sanitized, redacted = sanitize_for_submission(entry)
        assert "rechercher_jurisprudence_judilibre" in sanitized["action_sequence"][0]
        assert redacted is False


class TestLegifranceReportDiscovery:
    async def test_logs_locally_and_returns_success(self, tmp_path):
        with patch(
            "legifrance_mcp.src.tools.feedback_tool.FEEDBACK_LOG_PATH",
            tmp_path / "feedback.jsonl",
        ):
            result = await legifrance_feedback(
                fond_types=["code_article"],
                tools_used=["rechercher_code"],
                action_sequence=["called rechercher_code with search=bail commercial"],
                outcome="0 results for a term that clearly has matches on legifrance.gouv.fr",
            )

        assert result["status"] == "logged_locally"
        log_path = tmp_path / "feedback.jsonl"
        assert log_path.exists()
        lines = log_path.read_text().strip().splitlines()
        assert len(lines) == 1
        entry = json.loads(lines[0])
        assert entry["fond_types"] == ["code_article"]
        assert entry["outcome"].startswith("0 results")

    async def test_never_submits_anywhere_only_suggests(self, tmp_path):
        with patch(
            "legifrance_mcp.src.tools.feedback_tool.FEEDBACK_LOG_PATH",
            tmp_path / "feedback.jsonl",
        ):
            result = await legifrance_feedback(
                fond_types=["judilibre_decision"],
                tools_used=["rechercher_jurisprudence_judilibre"],
                action_sequence=["called it twice with different page_size"],
                outcome="second call silently clamped page_size with no indication",
                friction_category="param_shape_confusion",
            )

        assert "message" in result
        assert "go-ahead" in result["message"]
        assert result["suggested_repo"] == "jfenal/legifrance-mcp"
        assert (
            "page_size" in result["suggested_title"]
            or "param_shape_confusion" in result["suggested_title"]
        )

    async def test_redacted_entries_are_flagged_in_the_response(self, tmp_path):
        with patch(
            "legifrance_mcp.src.tools.feedback_tool.FEEDBACK_LOG_PATH",
            tmp_path / "feedback.jsonl",
        ):
            result = await legifrance_feedback(
                fond_types=["loda_text"],
                tools_used=["get_text_history"],
                action_sequence=["contacted jane.doe@example.com about the bug"],
                outcome="n/a",
            )

        assert result["redacted"] is True

    async def test_tools_tried_but_wrong_is_recorded_and_included_in_body(
        self, tmp_path
    ):
        with patch(
            "legifrance_mcp.src.tools.feedback_tool.FEEDBACK_LOG_PATH",
            tmp_path / "feedback.jsonl",
        ):
            result = await legifrance_feedback(
                fond_types=["code_article"],
                tools_used=["rechercher_code"],
                action_sequence=["x"],
                outcome="y",
                tools_tried_but_wrong=["rechercher_dans_texte_legal"],
            )

        assert "rechercher_dans_texte_legal" in result["suggested_body"]
        entry = json.loads((tmp_path / "feedback.jsonl").read_text().strip())
        assert entry["wrong_tools"] == ["rechercher_dans_texte_legal"]

    async def test_unexpected_exception_returns_error_dict(self):
        with patch(
            "legifrance_mcp.src.tools.feedback_tool._write_local_log",
            side_effect=OSError("disk full"),
        ):
            result = await legifrance_feedback(
                fond_types=["code_article"],
                tools_used=["rechercher_code"],
                action_sequence=["x"],
                outcome="y",
            )

        assert result["status"] == "error"
        assert "disk full" in result["error"]
