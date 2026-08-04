import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


USERNAME_RE = re.compile(r"[a-z0-9._-]{3,40}\Z")
SCRYPT_N = 16384
SCRYPT_R = 8
SCRYPT_P = 1
SCRYPT_DKLEN = 32
JOB_STATUSES = {"queued", "running", "succeeded", "failed"}
JOB_RESERVED_PAYLOAD_KEYS = {
    "id",
    "type",
    "title",
    "status",
    "createdAt",
    "updatedAt",
    "logs",
    "result",
    "error",
}
SENSITIVE_JOB_PAYLOAD_KEYS = {
    "password",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
}


class CredentialConfigurationError(ValueError):
    pass


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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS integration_credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    system_type TEXT NOT NULL,
                    ciphertext BLOB NOT NULL,
                    nonce BLOB NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    UNIQUE(user_id, system_type)
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (2, int(time.time())),
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    job_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'succeeded', 'failed')),
                    public_payload_json TEXT NOT NULL,
                    logs_json TEXT NOT NULL,
                    result_json TEXT,
                    error_summary TEXT,
                    created_at INTEGER NOT NULL,
                    started_at INTEGER,
                    finished_at INTEGER,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_user_created ON jobs(user_id, created_at DESC)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (3, int(time.time())),
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

    def _credential_key(self) -> bytes:
        if not isinstance(self.credential_key, str) or not self.credential_key:
            raise CredentialConfigurationError("APP_CREDENTIAL_KEY must be a 32-byte URL-safe base64 key")
        try:
            padding = "=" * (-len(self.credential_key) % 4)
            key = base64.b64decode(
                self.credential_key + padding,
                altchars=b"-_",
                validate=True,
            )
        except (binascii.Error, ValueError, TypeError) as error:
            raise CredentialConfigurationError(
                "APP_CREDENTIAL_KEY must be a 32-byte URL-safe base64 key"
            ) from error
        if len(key) != 32:
            raise CredentialConfigurationError("APP_CREDENTIAL_KEY must decode to exactly 32 bytes")
        return key

    @staticmethod
    def _credential_associated_data(user_id: int, system_type: str) -> bytes:
        return f"{user_id}:{system_type}:v1".encode("utf-8")

    @staticmethod
    def _mask_account(account: str) -> str:
        if len(account) <= 2:
            return "*" * len(account)
        return f"{account[0]}{'*' * max(3, len(account) - 2)}{account[-1]}"

    def put_integration_credentials(
        self, user_id: int, system_type: str, account: str, password: str
    ) -> None:
        key = self._credential_key()
        account = account.strip()
        payload = json.dumps(
            {"account": account, "password": password},
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")
        nonce = os.urandom(12)
        associated_data = self._credential_associated_data(user_id, system_type)
        ciphertext = AESGCM(key).encrypt(nonce, payload, associated_data)
        now = int(time.time())
        with self.connect() as connection:
            connection.execute(
                """
                INSERT INTO integration_credentials(
                    user_id, system_type, ciphertext, nonce, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, system_type) DO UPDATE SET
                    ciphertext = excluded.ciphertext,
                    nonce = excluded.nonce,
                    updated_at = excluded.updated_at
                """,
                (user_id, system_type, ciphertext, nonce, now, now),
            )

    def get_integration_credentials(self, user_id: int, system_type: str) -> dict | None:
        key = self._credential_key()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT ciphertext, nonce
                FROM integration_credentials
                WHERE user_id = ? AND system_type = ?
                """,
                (user_id, system_type),
            ).fetchone()
        if row is None:
            return None
        try:
            payload = AESGCM(key).decrypt(
                row["nonce"],
                row["ciphertext"],
                self._credential_associated_data(user_id, system_type),
            )
            credentials = json.loads(payload.decode("utf-8"))
        except (InvalidTag, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise CredentialConfigurationError("integration credentials could not be decrypted") from error
        if not isinstance(credentials, dict) or not {"account", "password"} <= credentials.keys():
            raise CredentialConfigurationError("integration credentials payload is invalid")
        return {"account": credentials["account"], "password": credentials["password"]}

    def get_integration_status(self, user_id: int, system_type: str) -> dict:
        self._credential_key()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT ciphertext, nonce
                FROM integration_credentials
                WHERE user_id = ? AND system_type = ?
                """,
                (user_id, system_type),
            ).fetchone()
        if row is None:
            return {"configured": False, "accountMasked": None}
        credentials = self.get_integration_credentials(user_id, system_type)
        return {
            "configured": True,
            "accountMasked": self._mask_account(credentials["account"]),
        }

    def delete_integration_credentials(self, user_id: int, system_type: str) -> None:
        self._credential_key()
        with self.connect() as connection:
            connection.execute(
                "DELETE FROM integration_credentials WHERE user_id = ? AND system_type = ?",
                (user_id, system_type),
            )

    @staticmethod
    def _job_timestamp() -> int:
        return time.time_ns() // 1_000_000

    @staticmethod
    def _format_job_timestamp(value: int | None) -> str | None:
        if value is None:
            return None
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value / 1000))

    @classmethod
    def _validate_public_job_payload(cls, public_payload: dict) -> dict:
        if not isinstance(public_payload, dict):
            raise ValueError("public job payload must be an object")
        forbidden = JOB_RESERVED_PAYLOAD_KEYS & public_payload.keys()
        if forbidden:
            raise ValueError("public job payload cannot override job fields")

        cls._validate_public_job_value(public_payload)
        try:
            json.dumps(public_payload, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise ValueError("public job payload must be JSON serializable") from error
        return public_payload

    @classmethod
    def _validate_public_job_value(cls, value) -> None:
        def check(nested_value):
            if isinstance(nested_value, dict):
                for key, child_value in nested_value.items():
                    if str(key).lower() in SENSITIVE_JOB_PAYLOAD_KEYS:
                        raise ValueError("public job data cannot contain credentials")
                    check(child_value)
            elif isinstance(nested_value, list):
                for child_value in nested_value:
                    check(child_value)

        check(value)

    @classmethod
    def _job_from_row(cls, row: sqlite3.Row) -> dict:
        payload = json.loads(row["public_payload_json"])
        job = {
            "id": row["id"],
            "type": row["job_type"],
            "title": row["title"],
            "status": row["status"],
            "createdAt": cls._format_job_timestamp(row["created_at"]),
            "updatedAt": cls._format_job_timestamp(row["updated_at"]),
            "logs": json.loads(row["logs_json"]),
            "result": None if row["result_json"] is None else json.loads(row["result_json"]),
            "error": row["error_summary"],
        }
        job.update(payload)
        return job

    def create_job(self, user_id: int, job_type: str, title: str, public_payload: dict) -> dict:
        if not isinstance(job_type, str) or not job_type.strip():
            raise ValueError("job_type is required")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title is required")
        payload = self._validate_public_job_payload(public_payload)
        now = self._job_timestamp()
        job_id = uuid.uuid4().hex[:12]
        with self.connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO jobs(
                        id, user_id, job_type, title, status, public_payload_json,
                        logs_json, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'queued', ?, '[]', ?, ?)
                    """,
                    (
                        job_id,
                        user_id,
                        job_type.strip(),
                        title.strip(),
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("user does not exist") from error
            row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return self._job_from_row(row)

    def update_job(
        self,
        job_id: str,
        user_id: int,
        status: str,
        result=None,
        error_summary: str | None = None,
    ) -> None:
        if status not in JOB_STATUSES:
            raise ValueError("invalid job status")
        if error_summary is not None and not isinstance(error_summary, str):
            raise ValueError("error_summary must be a string")
        try:
            self._validate_public_job_value(result)
            result_json = None if result is None else json.dumps(
                result, ensure_ascii=False, separators=(",", ":")
            )
        except (TypeError, ValueError) as error:
            raise ValueError("result must be JSON serializable") from error
        now = self._job_timestamp()
        started_at = now if status == "running" else None
        finished_at = now if status in {"succeeded", "failed"} else None
        with self.connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET status = ?, result_json = ?, error_summary = ?, updated_at = ?,
                    started_at = CASE WHEN ? IS NULL THEN started_at ELSE COALESCE(started_at, ?) END,
                    finished_at = CASE WHEN ? IS NULL THEN finished_at ELSE ? END
                WHERE id = ? AND user_id = ?
                """,
                (
                    status,
                    result_json,
                    error_summary,
                    now,
                    started_at,
                    started_at,
                    finished_at,
                    finished_at,
                    job_id,
                    user_id,
                ),
            )

    def append_job_log(self, job_id: str, user_id: int, message: str) -> None:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("job log message is required")
        with self.connect() as connection:
            row = connection.execute(
                "SELECT logs_json FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id)
            ).fetchone()
            if row is None:
                return
            logs = json.loads(row["logs_json"])
            logs.append(message.strip())
            connection.execute(
                """
                UPDATE jobs SET logs_json = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (
                    json.dumps(logs, ensure_ascii=False, separators=(",", ":")),
                    self._job_timestamp(),
                    job_id,
                    user_id,
                ),
            )

    def list_jobs(self, user_id: int, limit: int = 50) -> list[dict]:
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM jobs
                WHERE user_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
        return [self._job_from_row(row) for row in rows]
