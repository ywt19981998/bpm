import base64
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from pathlib import Path


USERNAME_RE = re.compile(r"[a-z0-9._-]{3,40}\Z")
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32


class AppStore:
    def __init__(self, db_path: Path, credential_key: str | None = None):
        self.db_path = Path(db_path)
        self.credential_key = credential_key
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    def connect(self):
        connection = sqlite3.connect(self.db_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def migrate(self):
        with self.connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY,
                    applied_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash TEXT NOT NULL UNIQUE,
                    expires_at INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_sessions_expires_at ON sessions(expires_at)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (1, int(time.time())),
            )

    @staticmethod
    def _normalize_username(username: str) -> str:
        normalized = username.strip().lower()
        if not USERNAME_RE.fullmatch(normalized):
            raise ValueError("username must be 3-40 lowercase ASCII characters")
        return normalized

    @staticmethod
    def _password_hash(password: str) -> str:
        if len(password) < 8:
            raise ValueError("password must be at least 8 characters")
        salt = secrets.token_bytes(16)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=SCRYPT_DKLEN,
        )
        encoded_salt = base64.urlsafe_b64encode(salt).decode("ascii").rstrip("=")
        encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        return f"scrypt$v1${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${encoded_salt}${encoded_digest}"

    @staticmethod
    def _verify_password(password: str, encoded: str) -> bool:
        try:
            scheme, version, n, r, p, encoded_salt, encoded_digest = encoded.split("$")
            if scheme != "scrypt" or version != "v1":
                return False
            padding = "=" * (-len(encoded_salt) % 4)
            salt = base64.urlsafe_b64decode(encoded_salt + padding)
            padding = "=" * (-len(encoded_digest) % 4)
            expected = base64.urlsafe_b64decode(encoded_digest + padding)
            actual = hashlib.scrypt(
                password.encode("utf-8"),
                salt=salt,
                n=int(n),
                r=int(r),
                p=int(p),
                dklen=len(expected),
            )
        except (TypeError, ValueError, base64.binascii.Error):
            return False
        return hmac.compare_digest(actual, expected)

    @staticmethod
    def _row_to_user(row):
        return {"id": row["id"], "username": row["username"], "display_name": row["display_name"]}

    def register_user(self, username: str, password: str, display_name: str) -> dict:
        normalized = self._normalize_username(username)
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("display_name is required")
        password_hash = self._password_hash(password)
        now = int(time.time())
        try:
            with self.connect() as connection:
                cursor = connection.execute(
                    "INSERT INTO users(username, password_hash, display_name, created_at) VALUES (?, ?, ?, ?)",
                    (normalized, password_hash, display_name.strip(), now),
                )
                user_id = cursor.lastrowid
        except sqlite3.IntegrityError as error:
            raise ValueError("username is already registered") from error
        return {"id": user_id, "username": normalized, "display_name": display_name.strip()}

    def authenticate_user(self, username: str, password: str) -> dict | None:
        try:
            normalized = self._normalize_username(username)
        except (AttributeError, TypeError, ValueError):
            return None
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, display_name FROM users WHERE username = ?",
                (normalized,),
            ).fetchone()
        if row is None or not self._verify_password(password, row["password_hash"]):
            return None
        return self._row_to_user(row)

    def create_session(self, user_id: int, ttl_seconds: int = 604800) -> str:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        token = secrets.token_urlsafe(32)
        now = int(time.time())
        with self.connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO sessions(user_id, token_hash, expires_at, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, hashlib.sha256(token.encode("utf-8")).hexdigest(), now + ttl_seconds, now),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("user does not exist") from error
        return token

    def get_user_for_session(self, token: str) -> dict | None:
        if not isinstance(token, str) or not token:
            return None
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT u.id, u.username, u.display_name
                FROM sessions AS s
                JOIN users AS u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.expires_at > ?
                """,
                (token_hash, int(time.time())),
            ).fetchone()
        return None if row is None else self._row_to_user(row)

    def delete_session(self, token: str) -> None:
        if not isinstance(token, str) or not token:
            return
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
