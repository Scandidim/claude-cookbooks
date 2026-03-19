"""
S-VAULT Phantom — Firestore client.

Reads secrets from the path:
  artifacts/{SVAULT_APP_ID}/users/{SVAULT_USER_ID}/secrets

Environment variables (all required for vault operations):
  FIREBASE_SERVICE_ACCOUNT_FILE   path to serviceAccountKey.json
  SVAULT_APP_ID                   Firestore app ID (e.g. phantom-final-v1)
  SVAULT_USER_ID                  Firestore user/master ID

Usage:
    from portal.integrations.vault_client import VaultClient

    vault = VaultClient()
    secret = vault.get_latest_secret()
"""

import os
from functools import cached_property
from typing import Any

import firebase_admin
from firebase_admin import credentials, firestore


class VaultClient:
    """Read secrets from S-VAULT Phantom Firestore collection."""

    def __init__(
        self,
        service_account_file: str | None = None,
        app_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self._service_account_file = service_account_file or os.environ.get(
            "FIREBASE_SERVICE_ACCOUNT_FILE", ""
        )
        self._app_id = app_id or os.environ.get("SVAULT_APP_ID", "")
        self._user_id = user_id or os.environ.get("SVAULT_USER_ID", "")

        if not self._service_account_file:
            raise ValueError("FIREBASE_SERVICE_ACCOUNT_FILE is required")
        if not self._app_id:
            raise ValueError("SVAULT_APP_ID is required")
        if not self._user_id:
            raise ValueError("SVAULT_USER_ID is required")

    @cached_property
    def _db(self):
        """Lazy Firebase initialisation (singleton per process)."""
        app_name = f"svault-{self._app_id}"
        try:
            app = firebase_admin.get_app(app_name)
        except ValueError:
            cred = credentials.Certificate(self._service_account_file)
            app = firebase_admin.initialize_app(cred, name=app_name)
        return firestore.client(app=app)

    @property
    def _collection(self):
        return (
            self._db.collection("artifacts")
            .document(self._app_id)
            .collection("users")
            .document(self._user_id)
            .collection("secrets")
        )

    def get_latest_secret(self) -> dict[str, Any] | None:
        """Return the most recently added document from the secrets collection."""
        docs = (
            self._collection.order_by(
                "__name__",
                direction=firestore.Query.DESCENDING,  # type: ignore[attr-defined]
            )
            .limit(1)
            .stream()
        )
        for doc in docs:
            data = doc.to_dict()
            data["_id"] = doc.id
            return data
        return None

    def get_secret(self, doc_id: str) -> dict[str, Any] | None:
        """Return a specific document by ID."""
        doc = self._collection.document(doc_id).get()
        if doc.exists:
            data = doc.to_dict()
            data["_id"] = doc.id
            return data
        return None

    def list_secrets(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return up to *limit* secrets ordered newest-first."""
        docs = (
            self._collection.order_by(
                "__name__",
                direction=firestore.Query.DESCENDING,  # type: ignore[attr-defined]
            )
            .limit(limit)
            .stream()
        )
        results = []
        for doc in docs:
            data = doc.to_dict()
            data["_id"] = doc.id
            results.append(data)
        return results
