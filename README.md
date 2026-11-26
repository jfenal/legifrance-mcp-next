# legifrance-mcp

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

Serveur [Model Context Protocol](https://modelcontextprotocol.io/introduction) permettant d'interroger les bases juridiques françaises (Légifrance, Judilibre) depuis des LLMs compatibles comme Claude.

## Description

Ce projet implémente un serveur MCP qui donne accès aux ressources juridiques françaises (textes légaux, codes, jurisprudence) directement depuis un LLM, en authentifiant directement auprès de [PISTE](https://piste.gouv.fr/) (le portail officiel DILA), sans proxy tiers.

Il repose sur [FastMCP](https://gofastmcp.com/) et l'architecture "tools-first" du [template-mcp-server](https://github.com/redhat-data-and-ai/template-mcp-server) de Red Hat Data & AI, ce qui lui permet de fonctionner aussi bien en **stdio** (Claude Desktop, Cursor) qu'en **HTTP/SSE** (déploiement hébergé, par ex. sur OpenShift).

## Outils disponibles

| Outil | Description |
| --- | --- |
| `rechercher_code` | Recherche dans les codes juridiques français (ex: Code civil, Code du travail) |
| `rechercher_dans_texte_legal` | Recherche d'articles dans les textes légaux (lois, ordonnances, décrets, arrêtés) |
| `rechercher_jurisprudence_judiciaire` | Recherche dans la jurisprudence judiciaire (fonds JURI de Légifrance : Cour de cassation, cours d'appel) |
| `rechercher_jurisprudence_administrative` | Recherche dans la jurisprudence administrative (fonds CETAT de Légifrance : Conseil d'État, cours administratives d'appel, tribunaux administratifs) |
| `rechercher_jurisprudence_judilibre` | Recherche de décisions de justice via l'API Judilibre (Cour de cassation, juridictions du fond) |
| `get_text_history` | Historique des modifications (créations, modifications, abrogations d'articles) d'un texte légal |
| `legifrance_feedback` | Signalement de friction mécanique dans l'usage des outils (journalisation locale uniquement, jamais soumis automatiquement) |

## Prérequis

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Un compte [PISTE](https://piste.gouv.fr/registration) avec une application souscrite aux API **Légifrance** et **Judilibre** (CGU acceptées pour les deux, en sandbox comme en production) — voir la [FAQ officielle de l'API Légifrance](https://www.legifrance.gouv.fr/contenu/pied-de-page/foire-aux-questions-api) pour la procédure complète
- Un client compatible MCP (Claude Desktop, Cursor, ou tout client parlant stdio/HTTP)

## Installation

```bash
git clone https://github.com/jfenal/legifrance-mcp-next.git
cd legifrance-mcp-next
uv sync
cp .env.example .env
```

Éditez `.env` avec vos identifiants PISTE. PISTE affiche deux panneaux de clés sur la même page d'application — ne les confondez pas :

```bash
# Panneau "Identifiants Oauth"
LEGIFRANCE_OAUTH_ID=votre_oauth_client_id
LEGIFRANCE_OAUTH_SECRET=votre_oauth_client_secret
PISTE_ENV=sandbox  # ou "production" (défaut: "production")

# Panneau "API Keys" -- requis pour rechercher_jurisprudence_judilibre
JUDILIBRE_API_KEY=votre_api_key
```

## Utilisation

### Transport stdio (Claude Desktop, Cursor)

Pour un client local qui lance le serveur en sous-processus, configurez `MCP_TRANSPORT_PROTOCOL=stdio` :

```json
{
  "mcpServers": {
    "legifrance-mcp": {
      "command": "uv",
      "args": ["--directory", "/chemin/vers/legifrance-mcp-next", "run", "legifrance-mcp"],
      "env": { "MCP_TRANSPORT_PROTOCOL": "stdio" }
    }
  }
}
```

`uv run` gère l'environnement virtuel ; les identifiants PISTE sont chargés depuis le `.env` du dépôt. Sous stdio, stdout est réservé au protocole JSON-RPC : les logs sont systématiquement écrits sur stderr (jamais sur stdout), avec en option un fichier de log complet via `LOG_FILE_PATH`.

### Transport HTTP (déploiement hébergé)

```bash
MCP_TRANSPORT_PROTOCOL=http uv run legifrance-mcp
curl http://localhost:5001/health
```

Voir le [template-mcp-server](https://github.com/redhat-data-and-ai/template-mcp-server) pour la documentation complète du déploiement OpenShift, de l'authentification OAuth optionnelle (`ENABLE_AUTH`) et des autres variables de configuration héritées du template.

### Exemple

```
> Recherche les conditions de validité du PACS dans le Code civil

[appel de l'outil rechercher_code: search="pacte civil de solidarité", code_name="Code civil"]

## Code civil — art. 515-1
**État**: VIGUEUR
**URL**: https://www.legifrance.gouv.fr/codes/article_lc/LEGIARTI000006428463

Un pacte civil de solidarité est un contrat conclu par deux personnes
physiques majeures, de sexe différent ou de même sexe, pour organiser
leur vie commune.
```

## Limitation de débit

Les outils Légifrance et Judilibre sont soumis à une limitation de débit proactive alignée sur les quotas publiés par PISTE : 2 req/s et 25 000 req/jour par point d'accès (plafond compte de 20 req/s et 1 000 000 req/jour) pour les outils adossés à Légifrance, et 20 req/s / 1 000 000 req/jour pour Judilibre.

## Origine

Ce dépôt descend de [jfenal/legifrance-mcp](https://github.com/jfenal/legifrance-mcp) (lui-même issu d'un fork de [pylegifrance/mcp-server-legifrance](https://github.com/pylegifrance/mcp-server-legifrance)), porté sur l'architecture FastMCP/tools-first du [template-mcp-server](https://github.com/redhat-data-and-ai/template-mcp-server) pour permettre un hébergement OpenShift tout en conservant le support stdio. Il s'appuie sur [un fork de pylegifrance](https://github.com/jfenal/pylegifrance) tant que les correctifs correspondants ne sont pas fusionnés dans le dépôt officiel.

## Contribution

Les contributions sont les bienvenues ! Voir la structure des outils dans [`legifrance_mcp/src/tools/README.md`](legifrance_mcp/src/tools/README.md). Ouvrez une issue ou une pull request pour toute amélioration ou correction.

## Licence

[Apache 2.0](LICENSE)
