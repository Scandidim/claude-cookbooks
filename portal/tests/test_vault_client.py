"""
Unit tests for portal/integrations/vault_client.py

All Firestore / Firebase calls are mocked — no real credentials needed.
Run:
    uv run pytest portal/tests/test_vault_client.py -v
"""

import os
import unittest
from unittest.mock import MagicMock, patch

from portal.integrations.vault_client import VaultClient

# ── helpers ──────────────────────────────────────────────────────────────────


def _make_doc(doc_id: str, data: dict) -> MagicMock:
    """Return a fake Firestore DocumentSnapshot."""
    doc = MagicMock()
    doc.id = doc_id
    doc.exists = True
    doc.to_dict.return_value = dict(data)
    return doc


def _make_missing_doc() -> MagicMock:
    doc = MagicMock()
    doc.exists = False
    return doc


# ── fixtures ─────────────────────────────────────────────────────────────────

APP_ID = "phantom-final-v1"
USER_ID = "TEST_USER_UID"
SA_FILE = "/fake/serviceAccountKey.json"


def _vault(**kwargs):
    """Construct VaultClient with sensible defaults, override via kwargs."""
    defaults = dict(service_account_file=SA_FILE, app_id=APP_ID, user_id=USER_ID)
    defaults.update(kwargs)
    return VaultClient(**defaults)


# ── test classes ─────────────────────────────────────────────────────────────


class TestVaultClientInit(unittest.TestCase):
    """Initialisation and validation."""

    def test_raises_when_service_account_file_missing(self):
        """ValueError if FIREBASE_SERVICE_ACCOUNT_FILE not provided."""
        with self.assertRaises(ValueError) as ctx:
            VaultClient(service_account_file="", app_id=APP_ID, user_id=USER_ID)
        self.assertIn("FIREBASE_SERVICE_ACCOUNT_FILE", str(ctx.exception))

    def test_raises_when_app_id_missing(self):
        with self.assertRaises(ValueError) as ctx:
            VaultClient(service_account_file=SA_FILE, app_id="", user_id=USER_ID)
        self.assertIn("SVAULT_APP_ID", str(ctx.exception))

    def test_raises_when_user_id_missing(self):
        with self.assertRaises(ValueError) as ctx:
            VaultClient(service_account_file=SA_FILE, app_id=APP_ID, user_id="")
        self.assertIn("SVAULT_USER_ID", str(ctx.exception))

    def test_reads_from_env_vars(self):
        """Constructor falls back to environment variables."""
        env = {
            "FIREBASE_SERVICE_ACCOUNT_FILE": SA_FILE,
            "SVAULT_APP_ID": APP_ID,
            "SVAULT_USER_ID": USER_ID,
        }
        with patch.dict(os.environ, env):
            v = VaultClient()
        self.assertEqual(v._service_account_file, SA_FILE)
        self.assertEqual(v._app_id, APP_ID)
        self.assertEqual(v._user_id, USER_ID)

    def test_explicit_params_override_env(self):
        """Explicit constructor args win over env vars."""
        env = {
            "FIREBASE_SERVICE_ACCOUNT_FILE": "/from/env.json",
            "SVAULT_APP_ID": "env-app",
            "SVAULT_USER_ID": "env-uid",
        }
        with patch.dict(os.environ, env):
            v = VaultClient(service_account_file=SA_FILE, app_id=APP_ID, user_id=USER_ID)
        self.assertEqual(v._service_account_file, SA_FILE)
        self.assertEqual(v._app_id, APP_ID)
        self.assertEqual(v._user_id, USER_ID)

    def test_db_is_lazy(self):
        """_db must NOT be initialised during __init__."""
        v = _vault()
        self.assertNotIn("_db", v.__dict__)


class TestVaultClientFirebaseInit(unittest.TestCase):
    """Firebase app singleton logic."""

    @patch("portal.integrations.vault_client.firestore")
    @patch("portal.integrations.vault_client.credentials.Certificate")
    @patch("portal.integrations.vault_client.firebase_admin.initialize_app")
    @patch("portal.integrations.vault_client.firebase_admin.get_app", side_effect=ValueError)
    def test_initialises_new_firebase_app(self, mock_get, mock_init, mock_cert, mock_fs):
        """Creates a new Firebase app when one doesn't exist yet."""
        mock_fs.client.return_value = MagicMock()
        v = _vault()
        _ = v._db
        mock_cert.assert_called_once_with(SA_FILE)
        mock_init.assert_called_once()
        app_name = mock_init.call_args[1].get("name") or mock_init.call_args[0][1]
        self.assertIn(APP_ID, app_name)

    @patch("portal.integrations.vault_client.firestore")
    @patch("portal.integrations.vault_client.firebase_admin.initialize_app")
    @patch("portal.integrations.vault_client.firebase_admin.get_app")
    def test_reuses_existing_firebase_app(self, mock_get, mock_init, mock_fs):
        """Reuses existing Firebase app — initialize_app NOT called twice."""
        mock_fs.client.return_value = MagicMock()
        v = _vault()
        _ = v._db
        mock_init.assert_not_called()

    @patch("portal.integrations.vault_client.firestore")
    @patch("portal.integrations.vault_client.firebase_admin.initialize_app")
    @patch("portal.integrations.vault_client.firebase_admin.get_app", side_effect=ValueError)
    @patch("portal.integrations.vault_client.credentials.Certificate")
    def test_db_cached_after_first_access(self, mock_cert, mock_get, mock_init, mock_fs):
        """_db is cached — Firebase init runs only once per instance."""
        mock_fs.client.return_value = MagicMock()
        v = _vault()
        db1 = v._db
        db2 = v._db
        self.assertIs(db1, db2)
        mock_init.assert_called_once()


class TestGetLatestSecret(unittest.TestCase):
    """VaultClient.get_latest_secret()"""

    def _patched_vault(self, stream_docs):
        """Return a VaultClient whose Firestore collection is mocked."""
        v = _vault()
        query = MagicMock()
        query.stream.return_value = iter(stream_docs)
        col = MagicMock()
        col.order_by.return_value.limit.return_value = query
        v.__dict__["_db"] = MagicMock()  # bypass cached_property
        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda self: col)):
            yield v, col

    def test_returns_latest_document(self):
        doc = _make_doc("secret-001", {"key": "value", "env": "prod"})
        v = _vault()
        col = MagicMock()
        col.order_by.return_value.limit.return_value.stream.return_value = iter([doc])
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            result = v.get_latest_secret()

        self.assertIsNotNone(result)
        self.assertEqual(result["key"], "value")
        self.assertEqual(result["env"], "prod")
        self.assertEqual(result["_id"], "secret-001")

    def test_returns_none_when_collection_empty(self):
        v = _vault()
        col = MagicMock()
        col.order_by.return_value.limit.return_value.stream.return_value = iter([])
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            result = v.get_latest_secret()

        self.assertIsNone(result)

    def test_injects_doc_id_into_result(self):
        doc = _make_doc("abc-123", {"token": "s3cr3t"})
        v = _vault()
        col = MagicMock()
        col.order_by.return_value.limit.return_value.stream.return_value = iter([doc])
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            result = v.get_latest_secret()

        self.assertIn("_id", result)
        self.assertEqual(result["_id"], "abc-123")

    def test_queries_with_limit_1(self):
        """Must request exactly 1 document — no over-fetching."""
        v = _vault()
        col = MagicMock()
        order_mock = col.order_by.return_value
        limit_mock = order_mock.limit.return_value
        limit_mock.stream.return_value = iter([])
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            v.get_latest_secret()

        order_mock.limit.assert_called_once_with(1)


class TestGetSecret(unittest.TestCase):
    """VaultClient.get_secret(doc_id)"""

    def test_returns_document_when_found(self):
        doc = _make_doc("doc-777", {"password": "hunter2"})
        v = _vault()
        col = MagicMock()
        col.document.return_value.get.return_value = doc
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            result = v.get_secret("doc-777")

        self.assertEqual(result["password"], "hunter2")
        self.assertEqual(result["_id"], "doc-777")
        col.document.assert_called_once_with("doc-777")

    def test_returns_none_when_not_found(self):
        missing = _make_missing_doc()
        v = _vault()
        col = MagicMock()
        col.document.return_value.get.return_value = missing
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            result = v.get_secret("no-such-doc")

        self.assertIsNone(result)


class TestListSecrets(unittest.TestCase):
    """VaultClient.list_secrets(limit)"""

    def _make_docs(self, n: int) -> list:
        return [_make_doc(f"doc-{i}", {"index": i}) for i in range(n)]

    def test_returns_all_documents(self):
        docs = self._make_docs(3)
        v = _vault()
        col = MagicMock()
        col.order_by.return_value.limit.return_value.stream.return_value = iter(docs)
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            result = v.list_secrets()

        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["index"], 0)
        self.assertEqual(result[2]["_id"], "doc-2")

    def test_empty_collection_returns_empty_list(self):
        v = _vault()
        col = MagicMock()
        col.order_by.return_value.limit.return_value.stream.return_value = iter([])
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            result = v.list_secrets()

        self.assertEqual(result, [])

    def test_default_limit_is_20(self):
        v = _vault()
        col = MagicMock()
        order_mock = col.order_by.return_value
        limit_mock = order_mock.limit.return_value
        limit_mock.stream.return_value = iter([])
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            v.list_secrets()

        order_mock.limit.assert_called_once_with(20)

    def test_custom_limit_is_forwarded(self):
        v = _vault()
        col = MagicMock()
        order_mock = col.order_by.return_value
        limit_mock = order_mock.limit.return_value
        limit_mock.stream.return_value = iter([])
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            v.list_secrets(limit=5)

        order_mock.limit.assert_called_once_with(5)

    def test_each_doc_has_id_injected(self):
        docs = self._make_docs(2)
        v = _vault()
        col = MagicMock()
        col.order_by.return_value.limit.return_value.stream.return_value = iter(docs)
        v.__dict__["_db"] = MagicMock()

        with patch.object(type(v), "_collection", new_callable=lambda: property(lambda s: col)):
            result = v.list_secrets()

        for item in result:
            self.assertIn("_id", item)


class TestFirestorePathConstruction(unittest.TestCase):
    """Verify the Firestore path follows the S-VAULT spec exactly."""

    @patch("portal.integrations.vault_client.firestore")
    @patch("portal.integrations.vault_client.credentials.Certificate")
    @patch("portal.integrations.vault_client.firebase_admin.initialize_app")
    @patch("portal.integrations.vault_client.firebase_admin.get_app", side_effect=ValueError)
    def test_collection_path_matches_svault_spec(self, mock_get, mock_init, mock_cert, mock_fs):
        """
        Path must be:
          artifacts / {app_id} / users / {user_id} / secrets
        """
        db = MagicMock()
        mock_fs.client.return_value = db

        v = _vault()
        _ = v._collection  # trigger path construction

        # Verify chain: db.collection("artifacts").document(app_id)
        #               .collection("users").document(user_id).collection("secrets")
        db.collection.assert_called_once_with("artifacts")
        db.collection().document.assert_called_once_with(APP_ID)
        db.collection().document().collection.assert_called_once_with("users")
        db.collection().document().collection().document.assert_called_once_with(USER_ID)
        db.collection().document().collection().document().collection.assert_called_once_with(
            "secrets"
        )


if __name__ == "__main__":
    unittest.main()
