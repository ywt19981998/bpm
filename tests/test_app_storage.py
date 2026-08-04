import base64
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app_storage import AppStore, CredentialConfigurationError


class AppStoreAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "app.db"
        self.store = AppStore(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def database_text(self):
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT username, password_hash, display_name FROM users"
            ).fetchall()
        return " ".join(str(value) for row in rows for value in row)

    def test_register_authenticate_and_session_round_trip(self):
        user = self.store.register_user(" Editor01 ", "S3cure-pass", "张编辑")
        self.assertEqual(user["username"], "editor01")
        self.assertEqual(user["display_name"], "张编辑")
        self.assertNotIn("S3cure-pass", self.database_text())
        self.assertEqual(
            self.store.authenticate_user("EDITOR01", "S3cure-pass")["id"],
            user["id"],
        )
        self.assertIsNone(self.store.authenticate_user("editor01", "wrong-pass"))
        token = self.store.create_session(user["id"], ttl_seconds=3600)
        self.assertEqual(self.store.get_user_for_session(token)["id"], user["id"])
        self.store.delete_session(token)
        self.assertIsNone(self.store.get_user_for_session(token))

    def test_duplicate_usernames_are_normalized_and_rejected(self):
        self.store.register_user("Editor01", "S3cure-pass", "张编辑")
        with self.assertRaises(ValueError):
            self.store.register_user(" editor01 ", "another-pass", "另一位编辑")

    def test_registration_validates_username_password_and_display_name(self):
        invalid_users = ["ab", "a" * 41, "not valid"]
        for username in invalid_users:
            with self.subTest(username=username):
                with self.assertRaises(ValueError):
                    self.store.register_user(username, "S3cure-pass", "编辑")
        with self.assertRaises(ValueError):
            self.store.register_user("editor02", "short", "编辑")
        with self.assertRaises(ValueError):
            self.store.register_user("editor02", "S3cure-pass", " ")

    def test_session_token_is_hashed_in_database(self):
        user = self.store.register_user("editor01", "S3cure-pass", "张编辑")
        token = self.store.create_session(user["id"])
        with sqlite3.connect(self.db_path) as connection:
            stored_token = connection.execute(
                "SELECT token_hash FROM sessions"
            ).fetchone()[0]
        self.assertNotEqual(stored_token, token)
        self.assertEqual(len(stored_token), 64)
        self.assertNotIn(token, self.db_path.read_bytes().decode("utf-8", "ignore"))

    def test_token_with_unicode_suffix_does_not_resolve(self):
        user = self.store.register_user("editor01", "S3cure-pass", "张编辑")
        token = self.store.create_session(user["id"])
        self.assertIsNone(self.store.get_user_for_session(token + "中文"))


class AppStoreCredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "app.db"
        self.key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        self.store = AppStore(self.db_path, credential_key=self.key)
        self.user_id = self.store.register_user("editor01", "S3cure-pass", "张编辑")["id"]
        self.other_user_id = self.store.register_user(
            "editor02", "S3cure-pass", "另一位编辑"
        )["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def database_text(self):
        return self.db_path.read_bytes().decode("utf-8", "ignore")

    def test_credentials_are_encrypted_and_isolated(self):
        self.store.put_integration_credentials(self.user_id, "phei_bpm", "yewt", "bpm-secret")
        self.assertNotIn("yewt", self.database_text())
        self.assertNotIn("bpm-secret", self.database_text())
        self.assertEqual(
            self.store.get_integration_credentials(self.user_id, "phei_bpm"),
            {"account": "yewt", "password": "bpm-secret"},
        )
        self.assertIsNone(
            self.store.get_integration_credentials(self.other_user_id, "phei_bpm")
        )
        self.assertEqual(
            self.store.get_integration_status(self.user_id, "phei_bpm"),
            {"configured": True, "accountMasked": "y***t"},
        )
        self.store.delete_integration_credentials(self.user_id, "phei_bpm")
        self.assertIsNone(
            self.store.get_integration_credentials(self.user_id, "phei_bpm")
        )
        self.assertEqual(
            self.store.get_integration_status(self.user_id, "phei_bpm"),
            {"configured": False, "accountMasked": None},
        )

    def test_missing_or_wrong_key_raises(self):
        self.store.put_integration_credentials(self.user_id, "phei_bpm", "yewt", "bpm-secret")
        wrong_store = AppStore(
            self.db_path,
            credential_key=base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
        )
        with self.assertRaises(CredentialConfigurationError):
            wrong_store.get_integration_credentials(self.user_id, "phei_bpm")
        missing_store = AppStore(self.db_path)
        with self.assertRaises(CredentialConfigurationError):
            missing_store.get_integration_credentials(self.user_id, "phei_bpm")


if __name__ == "__main__":
    unittest.main()
