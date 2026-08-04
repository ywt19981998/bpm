import sqlite3
import tempfile
import unittest
from pathlib import Path

from app_storage import AppStore


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


if __name__ == "__main__":
    unittest.main()
