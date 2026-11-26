# AGENTS.md

Quick reference for building this MCP server and wiring it into a client. For
what the server does and its tool catalog, see [README.md](README.md).

## Build

```bash
git clone <this-repo>
cd legifrance-mcp-next
uv sync          # installs dependencies and creates .venv
```

Requires Python >=3.12 (managed by `uv`).

## Credentials

You need PISTE (Légifrance/Judilibre) credentials — see README.md for how to
obtain them. Create a local `.env` file at the repo root (gitignored, never
commit it):

```bash
LEGIFRANCE_OAUTH_ID=...
LEGIFRANCE_OAUTH_SECRET=...
JUDILIBRE_API_KEY=...
PISTE_ENV=sandbox          # or "production" (default)
```

## Run locally (manual smoke test)

```bash
MCP_TRANSPORT_PROTOCOL=stdio uv run legifrance-mcp
```

This starts the server speaking MCP over stdio — useful for a quick manual
check before wiring it into a client below. `MCP_TRANSPORT_PROTOCOL` defaults
to `http` (the FastAPI-hosted transport used for the OpenShift deployment
path — see README.md); the three clients below all use `stdio` instead,
since they spawn the server as a local subprocess.

Other settings worth knowing (see `legifrance_mcp/src/settings.py` for the
full list and defaults): `PYTHON_LOG_LEVEL` (default `INFO`), `LOG_FILE_PATH`
(optional, unset by default — writes full DEBUG-level logs to a file in
addition to stderr), `ENABLE_AUTH` (default `True`; irrelevant under stdio).

## Wiring into clients

All three clients spawn the server the same way: `uv --directory
<path-to-repo> run legifrance-mcp`, with `MCP_TRANSPORT_PROTOCOL=stdio` set
in the server's environment. Replace `/path/to/legifrance-mcp-next` with
your actual clone path in every example below.

### Cursor

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "legifrance-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/legifrance-mcp-next", "run", "legifrance-mcp"],
      "env": {
        "MCP_TRANSPORT_PROTOCOL": "stdio"
      }
    }
  }
}
```

(Verified against this project's own working Cursor config.)

### Claude Desktop

Config file location:
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json` (unofficial — Claude
  Desktop's Linux support/packaging varies; confirm the path for your
  install if this doesn't exist)

```json
{
  "mcpServers": {
    "legifrance-mcp": {
      "command": "uv",
      "args": ["--directory", "/path/to/legifrance-mcp-next", "run", "legifrance-mcp"],
      "env": {
        "MCP_TRANSPORT_PROTOCOL": "stdio"
      }
    }
  }
}
```

Same shape as Cursor's config.

### Codex CLI

`~/.codex/config.toml` (shared with the ChatGPT desktop app and VS Code
extension; use `.codex/config.toml` in the project root instead for a
project-scoped server in a trusted project):

```toml
[mcp_servers.legifrance-mcp]
command = "uv"
args = ["--directory", "/path/to/legifrance-mcp-next", "run", "legifrance-mcp"]

[mcp_servers.legifrance-mcp.env]
MCP_TRANSPORT_PROTOCOL = "stdio"
```

Verified against OpenAI's current Codex CLI documentation (`[mcp_servers.<name>]`
table with `command`/`args`/`env`, env as its own sub-table). You can also
register it via `codex mcp add legifrance-mcp -- uv --directory
/path/to/legifrance-mcp-next run legifrance-mcp` instead of editing TOML by
hand, then set `MCP_TRANSPORT_PROTOCOL` in the resulting config entry.

## HTTP / hosted transport

For the FastAPI-hosted deployment (OpenShift), see README.md — it covers
`MCP_TRANSPORT_PROTOCOL=http`, `MCP_HOST`/`MCP_PORT`, auth, and CORS
settings not relevant to the stdio clients above.
