"""Unit tests for legifrance_client.py's pure helpers and client construction."""

from unittest.mock import patch

import pytest

from legifrance_mcp.src import legifrance_client as lc


@pytest.fixture(autouse=True)
def reset_cached_clients():
    lc._legifrance_client = None
    lc._judilibre_client = None
    yield
    lc._legifrance_client = None
    lc._judilibre_client = None


class TestApiConfig:
    def test_raises_when_credentials_missing(self, monkeypatch):
        monkeypatch.setattr(lc.settings, "LEGIFRANCE_OAUTH_ID", None)
        monkeypatch.setattr(lc.settings, "LEGIFRANCE_OAUTH_SECRET", None)

        with pytest.raises(ValueError, match="LEGIFRANCE_OAUTH_ID"):
            lc.get_legifrance_client()


class TestGetJudilibreClient:
    def test_raises_when_key_id_missing(self, monkeypatch):
        monkeypatch.setattr(lc.settings, "LEGIFRANCE_OAUTH_ID", "id")
        monkeypatch.setattr(lc.settings, "LEGIFRANCE_OAUTH_SECRET", "secret")
        monkeypatch.setattr(lc.settings, "JUDILIBRE_API_KEY", None)

        with pytest.raises(ValueError, match="JUDILIBRE_API_KEY"):
            lc.get_judilibre_client()

    def test_constructs_and_caches_client(self, monkeypatch):
        monkeypatch.setattr(lc.settings, "LEGIFRANCE_OAUTH_ID", "id")
        monkeypatch.setattr(lc.settings, "LEGIFRANCE_OAUTH_SECRET", "secret")
        monkeypatch.setattr(lc.settings, "JUDILIBRE_API_KEY", "key-id")

        with patch.object(lc, "JudilibreClient") as mock_cls:
            first = lc.get_judilibre_client()
            second = lc.get_judilibre_client()

        assert first is second
        mock_cls.assert_called_once()


class TestResolveCodeName:
    def test_unknown_code_returns_none(self):
        assert lc.resolve_code_name("not a real code") is None


class TestNormalizeTypeRecherche:
    def test_none_passthrough(self):
        assert lc.normalize_type_recherche(None) is None

    def test_maps_legacy_value(self):
        assert lc.normalize_type_recherche("EXPRESSION_EXACTE") == "EXACTE"

    def test_unknown_value_passthrough(self):
        assert lc.normalize_type_recherche("EXACTE") == "EXACTE"


class TestTruncate:
    def test_short_text_unchanged(self):
        assert lc.truncate("short", limit=100) == "short"

    def test_long_text_is_truncated(self):
        text = "x" * 50
        result = lc.truncate(text, limit=10)
        assert result.startswith("x" * 10)
        assert "tronqué" in result


class TestClampPageSize:
    def test_none_passthrough(self):
        assert lc.clamp_page_size(None) is None

    def test_clamps_to_max(self):
        assert lc.clamp_page_size(500) == lc.MAX_PAGE_SIZE


class TestFormatResults:
    def test_notes_remaining_results_beyond_the_cap(self):
        results = list(range(lc.MAX_RESULTS_PER_RESPONSE + 3))
        output = lc.format_results(results, lambda n: f"item-{n}")
        assert output.count("item-") == lc.MAX_RESULTS_PER_RESPONSE
        assert "3 résultat" in output

    def test_single_result_gets_the_larger_single_document_budget(self):
        text = "x" * (lc.MAX_CHARS_PER_RESULT + 500)
        output = lc.format_results([text], lambda t: t)
        assert "tronqué" not in output
        assert len(output) == len(text)

    def test_single_result_still_truncates_beyond_the_single_document_budget(self):
        text = "x" * (lc.MAX_CHARS_SINGLE_DOCUMENT + 500)
        output = lc.format_results([text], lambda t: t)
        assert "tronqué" in output

    def test_multiple_results_still_use_the_smaller_per_result_budget(self):
        text = "x" * (lc.MAX_CHARS_PER_RESULT + 500)
        output = lc.format_results([text, text], lambda t: t)
        assert output.count("tronqué") == 2
