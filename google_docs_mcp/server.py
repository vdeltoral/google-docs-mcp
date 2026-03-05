"""MCP server for Google Docs CRUD operations."""

import json
import logging

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

from google_docs_mcp.auth import get_credentials

logger = logging.getLogger(__name__)

mcp = FastMCP("Google Docs")

# Lazy-initialized API services
_docs_service = None
_drive_service = None


def _get_docs_service():
    global _docs_service
    if _docs_service is None:
        creds = get_credentials()
        _docs_service = build("docs", "v1", credentials=creds)
    return _docs_service


def _get_drive_service():
    global _drive_service
    if _drive_service is None:
        creds = get_credentials()
        _drive_service = build("drive", "v3", credentials=creds)
    return _drive_service


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------


@mcp.tool()
def create_document(title: str, body_text: str = "") -> str:
    """Create a new Google Doc with the given title and optional initial body text.

    Returns the document ID, title, and URL.
    """
    try:
        docs = _get_docs_service()
        doc = docs.documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        if body_text:
            docs.documents().batchUpdate(
                documentId=doc_id,
                body={
                    "requests": [
                        {
                            "insertText": {
                                "location": {"index": 1},
                                "text": body_text,
                            }
                        }
                    ]
                },
            ).execute()

        return json.dumps(
            {
                "documentId": doc_id,
                "title": title,
                "url": f"https://docs.google.com/document/d/{doc_id}/edit",
            },
            indent=2,
        )
    except HttpError as e:
        return f"Error creating document: {e}"


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------


@mcp.tool()
def get_document(document_id: str) -> str:
    """Get a Google Doc by its ID. Returns the title, full plain-text body, and metadata."""
    try:
        docs = _get_docs_service()
        doc = docs.documents().get(documentId=document_id).execute()

        # Extract plain text from the document body
        text = _extract_text(doc)

        return json.dumps(
            {
                "documentId": doc["documentId"],
                "title": doc.get("title", ""),
                "url": f"https://docs.google.com/document/d/{doc['documentId']}/edit",
                "revisionId": doc.get("revisionId", ""),
                "body_text": text,
            },
            indent=2,
        )
    except HttpError as e:
        return f"Error getting document: {e}"


@mcp.tool()
def search_documents(query: str, max_results: int = 10) -> str:
    """Search for Google Docs by name or content query.

    Uses Google Drive search. The query supports Drive search syntax,
    e.g. "name contains 'meeting'" or "fullText contains 'budget'".
    A plain string will be treated as a name search.
    """
    try:
        drive = _get_drive_service()

        # If the query doesn't look like Drive query syntax, wrap it as a name search
        drive_operators = [
            "name contains",
            "name =",
            "fullText contains",
            "mimeType",
            "modifiedTime",
            "createdTime",
            "trashed",
        ]
        if not any(op in query for op in drive_operators):
            query = f"name contains '{query}'"

        # Always restrict to Google Docs
        full_query = f"{query} and mimeType = 'application/vnd.google-apps.document'"

        results = (
            drive.files()
            .list(
                q=full_query,
                pageSize=max_results,
                fields="files(id, name, modifiedTime, createdTime, owners)",
                orderBy="modifiedTime desc",
            )
            .execute()
        )

        files = results.get("files", [])
        docs = []
        for f in files:
            owners = [o.get("displayName", "") for o in f.get("owners", [])]
            docs.append(
                {
                    "documentId": f["id"],
                    "title": f["name"],
                    "url": f"https://docs.google.com/document/d/{f['id']}/edit",
                    "modifiedTime": f.get("modifiedTime", ""),
                    "createdTime": f.get("createdTime", ""),
                    "owners": owners,
                }
            )

        return json.dumps(
            {"query": query, "resultCount": len(docs), "documents": docs},
            indent=2,
        )
    except HttpError as e:
        return f"Error searching documents: {e}"


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------


@mcp.tool()
def update_document(document_id: str, requests_json: str) -> str:
    """Apply batch updates to a Google Doc using the Docs API batchUpdate format.

    requests_json should be a JSON array of request objects, e.g.:
    [
      {"insertText": {"location": {"index": 1}, "text": "Hello world"}},
      {"deleteContentRange": {"range": {"startIndex": 1, "endIndex": 10}}}
    ]

    Common request types:
    - insertText: Insert text at an index
    - deleteContentRange: Delete a range of content
    - replaceAllText: Find and replace text
    - updateTextStyle: Change formatting (bold, italic, etc.)
    - insertInlineImage: Insert an image
    - createNamedRange: Create a named range
    """
    try:
        docs = _get_docs_service()
        requests = json.loads(requests_json)

        result = (
            docs.documents()
            .batchUpdate(documentId=document_id, body={"requests": requests})
            .execute()
        )

        return json.dumps(
            {
                "documentId": document_id,
                "appliedRequests": len(requests),
                "writeControl": result.get("writeControl", {}),
                "replies": [str(r) for r in result.get("replies", [])],
            },
            indent=2,
        )
    except json.JSONDecodeError as e:
        return f"Invalid JSON in requests_json: {e}"
    except HttpError as e:
        return f"Error updating document: {e}"


@mcp.tool()
def append_text(document_id: str, text: str) -> str:
    """Append text to the end of a Google Doc. A convenience wrapper around batchUpdate."""
    try:
        docs = _get_docs_service()

        # Get the document to find the end index
        doc = docs.documents().get(documentId=document_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1

        docs.documents().batchUpdate(
            documentId=document_id,
            body={
                "requests": [
                    {
                        "insertText": {
                            "location": {"index": end_index},
                            "text": text,
                        }
                    }
                ]
            },
        ).execute()

        return json.dumps(
            {
                "documentId": document_id,
                "appendedAt": end_index,
                "textLength": len(text),
            },
            indent=2,
        )
    except HttpError as e:
        return f"Error appending text: {e}"


@mcp.tool()
def replace_text(document_id: str, find: str, replace: str, match_case: bool = True) -> str:
    """Find and replace all occurrences of text in a Google Doc."""
    try:
        docs = _get_docs_service()

        result = (
            docs.documents()
            .batchUpdate(
                documentId=document_id,
                body={
                    "requests": [
                        {
                            "replaceAllText": {
                                "containsText": {
                                    "text": find,
                                    "matchCase": match_case,
                                },
                                "replaceText": replace,
                            }
                        }
                    ]
                },
            )
            .execute()
        )

        occurrences = 0
        for reply in result.get("replies", []):
            if "replaceAllText" in reply:
                occurrences = reply["replaceAllText"].get("occurrencesChanged", 0)

        return json.dumps(
            {
                "documentId": document_id,
                "find": find,
                "replace": replace,
                "occurrencesChanged": occurrences,
            },
            indent=2,
        )
    except HttpError as e:
        return f"Error replacing text: {e}"


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------


@mcp.tool()
def delete_document(document_id: str) -> str:
    """Move a Google Doc to the trash (via Google Drive API).

    The document can be recovered from trash within 30 days.
    """
    try:
        drive = _get_drive_service()
        drive.files().update(fileId=document_id, body={"trashed": True}).execute()

        return json.dumps(
            {
                "documentId": document_id,
                "status": "trashed",
                "message": "Document moved to trash. It can be recovered within 30 days.",
            },
            indent=2,
        )
    except HttpError as e:
        return f"Error deleting document: {e}"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_text(doc: dict) -> str:
    """Extract plain text from a Google Docs document JSON structure."""
    text_parts = []
    for element in doc.get("body", {}).get("content", []):
        if "paragraph" in element:
            for run in element["paragraph"].get("elements", []):
                if "textRun" in run:
                    text_parts.append(run["textRun"]["content"])
    return "".join(text_parts)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
