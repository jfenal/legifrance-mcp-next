"""Tests for the shared text-redaction helper."""

from legifrance_mcp.utils.redaction import redact


class TestRedact:
    def test_none_passthrough(self):
        assert redact(None) is None

    def test_empty_string_passthrough(self):
        assert redact("") == ""

    def test_redacts_email(self):
        assert redact("contact jane.doe@example.com") == "contact [redacted-email]"

    def test_redacts_path(self):
        assert redact("file at /home/user/secret/doc.txt") == "file at [redacted-path]"

    def test_redacts_long_token(self):
        assert redact("id 1a2B3c4D5e6F7g8H9i0J1k2L3m4N") == "id [redacted-id]"

    def test_preserve_keeps_known_tokens_unredacted(self):
        text = "called rechercher_jurisprudence_judilibre with bad params"
        result = redact(
            text, preserve=frozenset({"rechercher_jurisprudence_judilibre"})
        )
        assert result is not None
        assert "rechercher_jurisprudence_judilibre" in result
        assert "[redacted-id]" not in result

    def test_clean_text_unchanged(self):
        text = "tool returned an empty result"
        assert redact(text) == text
