"""
Google Workspace Integration
─────────────────────────────
Create and update Google Docs, Sheets, and Drive files.

Auth options (choose one):
  A. Service Account (recommended for server-side bots):
       GOOGLE_SERVICE_ACCOUNT_FILE=/path/to/service-account.json
       GOOGLE_DELEGATED_USER=admin@company.com   # for domain-wide delegation

  B. OAuth2 credentials (for user-facing apps):
       Use google_auth_oauthlib flow — see Google docs.

Scopes required:
  https://www.googleapis.com/auth/documents
  https://www.googleapis.com/auth/drive
  https://www.googleapis.com/auth/spreadsheets
"""

from __future__ import annotations

from portal import config


class GoogleWorkspace:
    def __init__(self) -> None:
        self._creds = self._build_credentials()
        self._docs_service = None
        self._drive_service = None
        self._sheets_service = None

    def _build_credentials(self):
        try:
            from google.oauth2 import service_account  # type: ignore[import]
        except ImportError as e:
            raise ImportError(
                "Install: uv add google-api-python-client google-auth-httplib2 google-auth-oauthlib"
            ) from e

        scopes = [
            "https://www.googleapis.com/auth/documents",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets",
        ]
        creds = service_account.Credentials.from_service_account_file(
            config.GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes
        )
        if config.GOOGLE_DELEGATED_USER:
            creds = creds.with_subject(config.GOOGLE_DELEGATED_USER)
        return creds

    def _docs(self):
        if self._docs_service is None:
            from googleapiclient.discovery import build  # type: ignore[import]

            self._docs_service = build("docs", "v1", credentials=self._creds, cache_discovery=False)
        return self._docs_service

    def _drive(self):
        if self._drive_service is None:
            from googleapiclient.discovery import build  # type: ignore[import]

            self._drive_service = build(
                "drive", "v3", credentials=self._creds, cache_discovery=False
            )
        return self._drive_service

    def _sheets(self):
        if self._sheets_service is None:
            from googleapiclient.discovery import build  # type: ignore[import]

            self._sheets_service = build(
                "sheets", "v4", credentials=self._creds, cache_discovery=False
            )
        return self._sheets_service

    # ── Documents ──────────────────────────────────────────────────────────────

    def create_doc(self, title: str, content: str, folder_id: str | None = None) -> str:
        """Create a Google Doc with plain-text content. Returns the doc URL."""
        doc = self._docs().documents().create(body={"title": title}).execute()
        doc_id = doc["documentId"]

        # Insert content
        self._docs().documents().batchUpdate(
            documentId=doc_id,
            body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
        ).execute()

        # Move to folder if specified
        if folder_id:
            file_info = self._drive().files().get(fileId=doc_id, fields="parents").execute()
            previous_parents = ",".join(file_info.get("parents", []))
            self._drive().files().update(
                fileId=doc_id,
                addParents=folder_id,
                removeParents=previous_parents,
                fields="id, parents",
            ).execute()

        return f"https://docs.google.com/document/d/{doc_id}/edit"

    def append_to_doc(self, doc_id: str, text: str) -> None:
        """Append text to an existing Google Doc."""
        doc = self._docs().documents().get(documentId=doc_id).execute()
        end_index = doc["body"]["content"][-1]["endIndex"] - 1
        self._docs().documents().batchUpdate(
            documentId=doc_id,
            body={
                "requests": [
                    {"insertText": {"location": {"index": end_index}, "text": "\n" + text}}
                ]
            },
        ).execute()

    # ── Sheets ─────────────────────────────────────────────────────────────────

    def create_sheet(self, title: str, rows: list[list[str]]) -> str:
        """Create a Google Sheet with given rows. Returns the sheet URL."""
        spreadsheet = (
            self._sheets().spreadsheets().create(body={"properties": {"title": title}}).execute()
        )
        sheet_id = spreadsheet["spreadsheetId"]

        if rows:
            self._sheets().spreadsheets().values().update(
                spreadsheetId=sheet_id,
                range="A1",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()

        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"

    # ── Drive ──────────────────────────────────────────────────────────────────

    def list_files(self, folder_id: str | None = None, limit: int = 20) -> list[dict]:
        """List files in Drive (or a specific folder)."""
        query = f"'{folder_id}' in parents" if folder_id else ""
        result = (
            self._drive()
            .files()
            .list(q=query, pageSize=limit, fields="files(id,name,mimeType)")
            .execute()
        )
        return result.get("files", [])
