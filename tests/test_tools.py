"""Tests for the Légifrance/Judilibre search tools.

Ported from the standalone legifrance-mcp project (jfenal/legifrance-mcp),
adapted to this template's dict-return tool convention.
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from legifrance_mcp.src.tools.get_text_history_tool import (
    _resolve_loda_text,
    get_text_history,
)
from legifrance_mcp.src.tools.rechercher_code_tool import rechercher_code
from legifrance_mcp.src.tools.rechercher_judilibre_tool import (
    rechercher_jurisprudence_judilibre,
)
from legifrance_mcp.src.tools.rechercher_jurisprudence_tool import (
    rechercher_jurisprudence_judiciaire,
)
from legifrance_mcp.src.tools.rechercher_texte_legal_tool import (
    rechercher_dans_texte_legal,
)


@pytest.fixture(autouse=True)
def piste_credentials(monkeypatch):
    """Settings is a singleton read at import time, so monkeypatch.setenv()
    alone wouldn't reach it -- patch the attribute on the specific object
    legifrance_client holds a reference to (not "the current
    legifrance_mcp.src.settings.settings", which test_basic.py's
    importlib.reload(settings_mod) can rebind to a disconnected instance)."""
    from legifrance_mcp.src import legifrance_client

    monkeypatch.setattr(legifrance_client.settings, "LEGIFRANCE_OAUTH_ID", "id")
    monkeypatch.setattr(legifrance_client.settings, "LEGIFRANCE_OAUTH_SECRET", "secret")


class TestRechercherCode:
    async def test_unknown_code_name_returns_clear_error(self):
        result = await rechercher_code(search="contrat", code_name="Pas un code")
        assert result["status"] == "error"
        assert "Pas un code" in result["error"]

    async def test_no_results_returns_explicit_message(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_code_tool.Code"
        ) as mock_code_cls:
            (
                mock_code_cls.return_value.search.return_value.in_code.return_value.with_formatter.return_value.with_legal_status.return_value.text.return_value.execute.return_value
            ) = []
            result = await rechercher_code(search="zzzzz", code_name="Code civil")
        assert result["status"] == "success"
        assert result["result"] == "Aucun résultat."

    async def test_returns_formatted_articles_on_success(self):
        article = MagicMock(
            code_name="Code civil",
            number="1240",
            title="De la responsabilité",
            legal_status="VIGUEUR",
            url="https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006438834",
            content="Tout fait quelconque de l'homme...",
            version_date=datetime(2020, 1, 1),
        )
        with patch(
            "legifrance_mcp.src.tools.rechercher_code_tool.Code"
        ) as mock_code_cls:
            (
                mock_code_cls.return_value.search.return_value.in_code.return_value.with_formatter.return_value.with_legal_status.return_value.text.return_value.execute.return_value
            ) = [article]
            result = await rechercher_code(
                search="responsabilité", code_name="Code civil", champ="ARTICLE"
            )
        assert result["status"] == "success"
        assert "1240" in result["result"]
        assert "01/01/2020" in result["result"]

    async def test_resolve_code_name_is_accent_tolerant(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_code_tool.Code"
        ) as mock_code_cls:
            (
                mock_code_cls.return_value.search.return_value.in_code.return_value.with_formatter.return_value.with_legal_status.return_value.text.return_value.execute.return_value
            ) = []
            result = await rechercher_code(search="x", code_name="Code penal")
        assert result["status"] == "success"

    async def test_proximite_is_forwarded_to_text_builder(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_code_tool.Code"
        ) as mock_code_cls:
            builder = mock_code_cls.return_value.search.return_value.in_code.return_value.with_formatter.return_value.with_legal_status.return_value
            builder.text.return_value.execute.return_value = []
            await rechercher_code(
                search="bail commercial", code_name="Code civil", proximite=3
            )
        assert builder.text.call_args.kwargs["proximity"] == 3

    async def test_num_article_champ_uses_article_number_builder(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_code_tool.Code"
        ) as mock_code_cls:
            builder = mock_code_cls.return_value.search.return_value.in_code.return_value.with_formatter.return_value.with_legal_status.return_value
            builder.article_number.return_value.execute.return_value = []
            await rechercher_code(
                search="1240", code_name="Code civil", champ="NUM_ARTICLE"
            )
        builder.article_number.assert_called_once_with("1240")

    async def test_fetch_all_uses_max_page_size(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_code_tool.Code"
        ) as mock_code_cls:
            builder = mock_code_cls.return_value.search.return_value.in_code.return_value.with_formatter.return_value.with_legal_status.return_value
            builder.text.return_value.execute.return_value = []
            await rechercher_code(search="x", code_name="Code civil", fetch_all=True)
        builder.text.return_value.paginate.assert_called_once_with(page_size=20)

    async def test_unexpected_exception_returns_error_dict(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_code_tool.Code",
            side_effect=RuntimeError("boom"),
        ):
            result = await rechercher_code(search="x", code_name="Code civil")
        assert result["status"] == "error"
        assert "boom" in result["error"]

    async def test_defaults_to_vigueur_only_results(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_code_tool.Code"
        ) as mock_code_cls:
            with_formatter = mock_code_cls.return_value.search.return_value.in_code.return_value.with_formatter.return_value
            builder = with_formatter.with_legal_status.return_value
            builder.text.return_value.execute.return_value = []
            await rechercher_code(search="x", code_name="Code civil")
        with_formatter.with_legal_status.assert_called_once()
        (statuses,) = with_formatter.with_legal_status.call_args.args
        assert [s.value for s in statuses] == ["VIGUEUR"]

    async def test_uniquement_en_vigueur_false_skips_the_filter(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_code_tool.Code"
        ) as mock_code_cls:
            with_formatter = mock_code_cls.return_value.search.return_value.in_code.return_value.with_formatter.return_value
            with_formatter.text.return_value.execute.return_value = []
            await rechercher_code(
                search="x", code_name="Code civil", uniquement_en_vigueur=False
            )
        with_formatter.with_legal_status.assert_not_called()


class TestRechercherTexteLegal:
    async def test_no_results_returns_explicit_message(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_texte_legal_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.search.return_value = []
            result = await rechercher_dans_texte_legal(search="zzzzz")
        assert result["result"] == "Aucun résultat."

    async def test_returns_formatted_texts_on_success(self):
        texte = MagicMock()
        texte.to_markdown.return_value = "## Loi 78-17\n\ncontenu"
        with patch(
            "legifrance_mcp.src.tools.rechercher_texte_legal_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.search.return_value = [texte]
            result = await rechercher_dans_texte_legal(
                search="informatique", type_recherche="EXPRESSION_EXACTE", page_size=500
            )
        assert "Loi 78-17" in result["result"]

    async def test_normalizes_type_recherche_before_building_query(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_texte_legal_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.search.return_value = []
            await rechercher_dans_texte_legal(
                search="x", type_recherche="EXPRESSION_EXACTE"
            )

        query = mock_loda_cls.return_value.search.call_args.args[0]
        assert query.type_recherche.value == "EXACTE"

    async def test_proximite_is_forwarded_as_proximity(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_texte_legal_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.search.return_value = []
            await rechercher_dans_texte_legal(search="dommages intérêts", proximite=3)

        query = mock_loda_cls.return_value.search.call_args.args[0]
        assert query.proximity == 3

    async def test_unexpected_exception_returns_error_dict(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_texte_legal_tool.Loda",
            side_effect=RuntimeError("boom"),
        ):
            result = await rechercher_dans_texte_legal(search="x")
        assert result["status"] == "error"
        assert "boom" in result["error"]

    async def test_text_id_and_champ_are_forwarded(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_texte_legal_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.search.return_value = []
            await rechercher_dans_texte_legal(
                text_id="78-17", search="7", champ="NUM_ARTICLE"
            )

        query = mock_loda_cls.return_value.search.call_args.args[0]
        assert query.text_id == "78-17"
        assert query.champ.value == "NUM_ARTICLE"


class TestRechercherJurisprudenceJudiciaire:
    async def test_no_results_returns_explicit_message(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_jurisprudence_tool.JuriAPI"
        ) as mock_juri_cls:
            mock_juri_cls.return_value.search.return_value = []
            result = await rechercher_jurisprudence_judiciaire(search="zzzzz")
        assert result["result"] == "Aucun résultat."

    async def test_returns_formatted_decisions_on_success(self):
        decision = MagicMock()
        decision.to_markdown.return_value = "## Cour de cassation\n\nRésumé"
        with patch(
            "legifrance_mcp.src.tools.rechercher_jurisprudence_tool.JuriAPI"
        ) as mock_juri_cls:
            mock_juri_cls.return_value.search.return_value = [decision]
            result = await rechercher_jurisprudence_judiciaire(
                search="licenciement",
                type_recherche="AU_MOINS_UN_MOT",
                page_size=500,
                champ="ALL",
                sort="DATE_DESC",
                publication_bulletin=["T"],
                fetch_all=True,
                juri_keys=["titre"],
                juridiction_judiciaire=["Cour de cassation"],
            )
        assert "Cour de cassation" in result["result"]

    async def test_fetch_all_uses_max_page_size(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_jurisprudence_tool.JuriAPI"
        ) as mock_juri_cls:
            mock_juri_cls.return_value.search.return_value = []
            await rechercher_jurisprudence_judiciaire(search="x", fetch_all=True)

        query = mock_juri_cls.return_value.search.call_args.args[0]
        assert query.page_size == 20

    async def test_proximite_is_forwarded_as_proximity(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_jurisprudence_tool.JuriAPI"
        ) as mock_juri_cls:
            mock_juri_cls.return_value.search.return_value = []
            await rechercher_jurisprudence_judiciaire(
                search="dommages intérêts", proximite=3
            )

        query = mock_juri_cls.return_value.search.call_args.args[0]
        assert query.proximity == 3

    async def test_unexpected_exception_returns_error_dict(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_jurisprudence_tool.JuriAPI",
            side_effect=RuntimeError("boom"),
        ):
            result = await rechercher_jurisprudence_judiciaire(search="x")
        assert result["status"] == "error"
        assert "boom" in result["error"]

    async def test_page_size_is_clamped_without_fetch_all(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_jurisprudence_tool.JuriAPI"
        ) as mock_juri_cls:
            mock_juri_cls.return_value.search.return_value = []
            await rechercher_jurisprudence_judiciaire(search="x", page_size=500)

        query = mock_juri_cls.return_value.search.call_args.args[0]
        assert query.page_size == 20


class TestRechercherJudilibre:
    async def test_missing_key_id_returns_clear_error(self):
        with patch(
            "legifrance_mcp.src.tools.rechercher_judilibre_tool.get_judilibre_client",
            side_effect=ValueError("JUDILIBRE_API_KEY doit être défini"),
        ):
            result = await rechercher_jurisprudence_judilibre(search="licenciement")
        assert result["status"] == "error"
        assert "JUDILIBRE_API_KEY" in result["error"]

    async def test_no_results_returns_explicit_message(self):
        with (
            patch(
                "legifrance_mcp.src.tools.rechercher_judilibre_tool.get_judilibre_client"
            ),
            patch(
                "legifrance_mcp.src.tools.rechercher_judilibre_tool.JudilibreAPI"
            ) as mock_judilibre_cls,
        ):
            mock_judilibre_cls.return_value.search.return_value = []
            result = await rechercher_jurisprudence_judilibre(search="zzzzz")
        assert result["result"] == "Aucun résultat."

    async def test_returns_formatted_decisions_on_success(self):
        decision = MagicMock()
        decision.to_markdown.return_value = "## Cour de cassation\n\nRésumé"
        with (
            patch(
                "legifrance_mcp.src.tools.rechercher_judilibre_tool.get_judilibre_client"
            ),
            patch(
                "legifrance_mcp.src.tools.rechercher_judilibre_tool.JudilibreAPI"
            ) as mock_judilibre_cls,
        ):
            mock_judilibre_cls.return_value.search.return_value = [decision]
            result = await rechercher_jurisprudence_judilibre(
                search="licenciement sans cause réelle et sérieuse"
            )
        assert "Cour de cassation" in result["result"]

    async def test_optional_filters_are_forwarded(self):
        with (
            patch(
                "legifrance_mcp.src.tools.rechercher_judilibre_tool.get_judilibre_client"
            ),
            patch(
                "legifrance_mcp.src.tools.rechercher_judilibre_tool.JudilibreAPI"
            ) as mock_judilibre_cls,
        ):
            mock_judilibre_cls.return_value.search.return_value = []
            await rechercher_jurisprudence_judilibre(
                search="x",
                jurisdiction=["Cour de cassation"],
                chamber=["Chambre sociale"],
                date_start="2020-01-01",
                date_end="2020-12-31",
                page_size=5,
            )
        kwargs = mock_judilibre_cls.return_value.search.call_args.kwargs
        assert kwargs["jurisdiction"] == ["Cour de cassation"]
        assert kwargs["chamber"] == ["Chambre sociale"]
        assert kwargs["date_start"] == "2020-01-01"
        assert kwargs["date_end"] == "2020-12-31"
        assert kwargs["page_size"] == 5

    async def test_unexpected_exception_returns_error_dict(self):
        with (
            patch(
                "legifrance_mcp.src.tools.rechercher_judilibre_tool.get_judilibre_client"
            ),
            patch(
                "legifrance_mcp.src.tools.rechercher_judilibre_tool.JudilibreAPI",
                side_effect=RuntimeError("boom"),
            ),
        ):
            result = await rechercher_jurisprudence_judilibre(search="x")
        assert result["status"] == "error"
        assert "boom" in result["error"]


class TestGetTextHistory:
    async def test_unknown_text_id_returns_explicit_message(self):
        with patch(
            "legifrance_mcp.src.tools.get_text_history_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.fetch.return_value = None
            mock_loda_cls.return_value.search.return_value = []
            result = await get_text_history(text_id="99-999")
        assert result["result"] == "Aucun résultat."

    async def test_resolves_law_number_via_search_before_fetching(self):
        resolved_texte = MagicMock()
        resolved_texte.format_modifications_report.return_value = (
            "## Loi 78-17\n\nImpact détaillé"
        )
        resolved_texte.versions.return_value = []

        match = MagicMock(id="LEGITEXT000006069095")

        def fake_fetch(text_id):
            if text_id == "LEGITEXT000006069095":
                return resolved_texte
            return None

        with patch(
            "legifrance_mcp.src.tools.get_text_history_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.fetch.side_effect = fake_fetch
            mock_loda_cls.return_value.search.return_value = [match]
            result = await get_text_history(text_id="78-17")

        assert "Impact détaillé" in result["result"]

    async def test_includes_version_history_section(self):
        version = MagicMock()
        version.date_debut.strftime.return_value = "01/01/2020"
        version.date_fin = None
        version.etat = "VIGUEUR"

        texte = MagicMock()
        texte.format_modifications_report.return_value = "Aucun impact disponible."
        texte.to_markdown.return_value = "## Texte\n\ncontenu"
        texte.versions.return_value = [version]

        with patch(
            "legifrance_mcp.src.tools.get_text_history_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.fetch.return_value = texte
            result = await get_text_history(text_id="78-17")

        assert "01/01/2020" in result["result"]
        assert "VIGUEUR" in result["result"]

    async def test_versions_failure_does_not_crash_the_tool(self):
        texte = MagicMock()
        texte.format_modifications_report.return_value = "Aucun impact disponible."
        texte.to_markdown.return_value = "## Loi 78-17\n\ncontenu"
        texte.versions.side_effect = Exception("API client error 403 - ...")

        with patch(
            "legifrance_mcp.src.tools.get_text_history_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.fetch.return_value = texte
            result = await get_text_history(text_id="78-17")

        assert "Loi 78-17" in result["result"]

    async def test_backend_failure_is_reported_distinctly_from_no_results(self):
        with patch(
            "legifrance_mcp.src.tools.get_text_history_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.fetch.return_value = None
            mock_loda_cls.return_value.search.side_effect = RuntimeError(
                "503 Service Unavailable"
            )
            result = await get_text_history(text_id="78-17")

        assert result["status"] == "error"
        assert "503" in result["error"]

    def test_resolve_loda_text_propagates_when_search_raises(self):
        loda = MagicMock()
        loda.fetch.return_value = None
        loda.search.side_effect = RuntimeError("boom")

        with pytest.raises(RuntimeError, match="boom"):
            _resolve_loda_text(loda, "78-17")

    def test_resolve_loda_text_returns_none_when_matched_id_is_none(self):
        loda = MagicMock()
        loda.fetch.return_value = None
        loda.search.return_value = [MagicMock(id=None)]

        assert _resolve_loda_text(loda, "78-17") is None

    def test_resolve_loda_text_falls_through_when_first_fetch_raises(self):
        """text_id not matching the LEGITEXT/JORFTEXT shape .fetch() expects
        (e.g. "78-17") is expected to raise -- falls through to search."""
        match = MagicMock(id="LEGITEXT000006069095")
        resolved = MagicMock()

        def fake_fetch(text_id):
            if text_id == "78-17":
                raise ValueError("bad format")
            return resolved

        loda = MagicMock()
        loda.fetch.side_effect = fake_fetch
        loda.search.return_value = [match]

        assert _resolve_loda_text(loda, "78-17") is resolved

    async def test_unexpected_exception_building_the_report_returns_error_dict(self):
        texte = MagicMock()
        texte.versions.return_value = []
        texte.format_modifications_report.side_effect = RuntimeError("boom")

        with patch(
            "legifrance_mcp.src.tools.get_text_history_tool.Loda"
        ) as mock_loda_cls:
            mock_loda_cls.return_value.fetch.return_value = texte
            result = await get_text_history(text_id="78-17")
        assert result["status"] == "error"
        assert "boom" in result["error"]
