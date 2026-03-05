# Google Docs MCP

An MCP (Model Context Protocol) server that gives AI assistants full CRUD access to Google Docs.

## Tools

| Tool | Description |
|------|-------------|
| `create_document` | Create a new Google Doc with title and optional body text |
| `get_document` | Get a doc by ID — returns title, full text, and metadata |
| `search_documents` | Search docs by name or content (supports Drive query syntax) |
| `update_document` | Apply batch updates (insert, delete, format, etc.) via raw Docs API requests |
| `append_text` | Append text to the end of a document |
| `replace_text` | Find and replace text in a document |
| `delete_document` | Move a document to trash (recoverable for 30 days) |

## Setup

### 1. Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select an existing one)
3. Enable the **Google Docs API** and **Google Drive API**:
   - APIs & Services > Library > search "Google Docs API" > Enable
   - APIs & Services > Library > search "Google Drive API" > Enable
4. Create OAuth credentials:
   - APIs & Services > Credentials > Create Credentials > OAuth client ID
   - Application type: **Desktop app**
   - Download the JSON file

### 2. Place Credentials

```bash
mkdir -p ~/.config/google-docs-mcp
cp ~/Downloads/client_secret_*.json ~/.config/google-docs-mcp/credentials.json
```

Or set the environment variable:
```bash
export GOOGLE_DOCS_MCP_CREDENTIALS=/path/to/your/credentials.json
```

### 3. Install

```bash
git clone https://github.com/YOUR_USERNAME/google-docs-mcp.git
cd google-docs-mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

### 4. Authenticate

Run once to trigger the OAuth flow:
```bash
python -c "from google_docs_mcp.auth import get_credentials; get_credentials()"
```

This opens a browser for Google OAuth consent. After authorizing, a token is cached at `~/.config/google-docs-mcp/token.json`.

### 5. Add to Claude Code

Run `/mcp` in Claude Code, or add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "google-docs": {
      "command": "/path/to/google-docs-mcp/.venv/bin/python",
      "args": ["-m", "google_docs_mcp.server"]
    }
  }
}
```

Replace `/path/to/google-docs-mcp` with wherever you cloned the repo.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_DOCS_MCP_CREDENTIALS` | `~/.config/google-docs-mcp/credentials.json` | Path to OAuth client credentials |
| `GOOGLE_DOCS_MCP_TOKEN` | `~/.config/google-docs-mcp/token.json` | Path to cached auth token |

## License

MIT
