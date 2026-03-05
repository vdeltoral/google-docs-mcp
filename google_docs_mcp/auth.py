"""Google OAuth2 authentication for the Docs MCP server."""

import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
]

DEFAULT_TOKEN_PATH = Path.home() / ".config" / "google-docs-mcp" / "token.json"
DEFAULT_CREDENTIALS_PATH = (
    Path.home() / ".config" / "google-docs-mcp" / "credentials.json"
)


def get_credentials(
    credentials_path: str | None = None,
    token_path: str | None = None,
) -> Credentials:
    """Get valid Google OAuth2 credentials, refreshing or re-authenticating as needed."""
    creds_file = Path(credentials_path or os.environ.get("GOOGLE_DOCS_MCP_CREDENTIALS", DEFAULT_CREDENTIALS_PATH))
    tok_file = Path(token_path or os.environ.get("GOOGLE_DOCS_MCP_TOKEN", DEFAULT_TOKEN_PATH))

    tok_file.parent.mkdir(parents=True, exist_ok=True)

    creds = None
    if tok_file.exists():
        creds = Credentials.from_authorized_user_file(str(tok_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not creds_file.exists():
                raise FileNotFoundError(
                    f"OAuth credentials file not found at {creds_file}. "
                    "Download your OAuth client credentials from the Google Cloud Console "
                    "and place them at this path, or set GOOGLE_DOCS_MCP_CREDENTIALS."
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(creds_file), SCOPES)
            creds = flow.run_local_server(port=0)

        tok_file.write_text(creds.to_json())

    return creds
