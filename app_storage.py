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
PROJECT_REPORT_STATUSES = {"empty", "draft", "confirmed"}
PROJECT_AUTHOR_STATUSES = {"unknown", "ready", "queued", "running", "succeeded", "failed"}
PROJECT_BPM_STATUSES = {"not_ready", "ready", "queued", "running", "succeeded", "failed"}
PROJECT_FILE_KINDS = {"application", "confirmed_report", "exported_report", "bpm_evidence"}
INTERRUPTED_JOB_ERROR = "服务重启，任务执行状态不确定，请先在 BPM 人工核对后再重试"
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
    "projectId",
}
SENSITIVE_JOB_PAYLOAD_KEYS = {
    "password",
    "bpm_password",
    "token",
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "secret",
}
REDACTED_JOB_VALUE = "[REDACTED]"
SENSITIVE_JOB_ASSIGNMENT_RE = re.compile(
    r"(?i)(\b(?:bpm[ _-]?)?(?:password|api[ _-]?key|authorization|token|secret)\b\s*[:=]\s*)([^\s,;]+)"
)
AUTHORIZATION_BEARER_RE = re.compile(
    r"(?i)\bauthorization\s*:\s*bearer\s+[^\s,;]+"
)
BEARER_TOKEN_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+")
API_KEY_VALUE_RE = re.compile(r"\bsk-[A-Za-z0-9_-]+\b", re.IGNORECASE)


class CredentialConfigurationError(ValueError):
    pass


class ProjectVersionConflict(ValueError):
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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    title TEXT NOT NULL,
                    author_name TEXT NOT NULL DEFAULT '',
                    editor_name TEXT NOT NULL DEFAULT '',
                    report_status TEXT NOT NULL CHECK(report_status IN ('empty', 'draft', 'confirmed')),
                    author_status TEXT NOT NULL CHECK(author_status IN ('unknown', 'ready', 'queued', 'running', 'succeeded', 'failed')),
                    bpm_status TEXT NOT NULL CHECK(bpm_status IN ('not_ready', 'ready', 'queued', 'running', 'succeeded', 'failed')),
                    state_json TEXT NOT NULL,
                    version INTEGER NOT NULL DEFAULT 1,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    archived_at INTEGER
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_projects_user_active_updated
                ON projects(user_id, archived_at, updated_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_files (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    kind TEXT NOT NULL CHECK(kind IN ('application', 'confirmed_report', 'exported_report', 'bpm_evidence')),
                    original_name TEXT NOT NULL,
                    storage_path TEXT NOT NULL UNIQUE,
                    sha256 TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_project_files_project_created
                ON project_files(project_id, created_at DESC)
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS project_revisions (
                    id TEXT PRIMARY KEY,
                    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
                    version INTEGER NOT NULL,
                    snapshot_json TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_project_revisions_project_version
                ON project_revisions(project_id, version DESC)
                """
            )
            job_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(jobs)").fetchall()
            }
            if "project_id" not in job_columns:
                connection.execute(
                    "ALTER TABLE jobs ADD COLUMN project_id TEXT REFERENCES projects(id) ON DELETE SET NULL"
                )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_jobs_project_created ON jobs(project_id, created_at DESC)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (4, int(time.time())),
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mail_templates (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    updated_at INTEGER NOT NULL,
                    last_used_at INTEGER,
                    UNIQUE(user_id, name)
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mail_drafts (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    template_id TEXT REFERENCES mail_templates(id) ON DELETE SET NULL,
                    subject TEXT NOT NULL,
                    body TEXT NOT NULL,
                    recipients_json TEXT NOT NULL,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (5, int(time.time())),
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mail_template_default_initializations (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    initialized_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (6, int(time.time())),
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mail_batches (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    subject_template TEXT NOT NULL,
                    body_template TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued', 'running', 'succeeded', 'partial_failed', 'failed')),
                    total_count INTEGER NOT NULL,
                    sent_count INTEGER NOT NULL DEFAULT 0,
                    failed_count INTEGER NOT NULL DEFAULT 0,
                    created_at INTEGER NOT NULL,
                    started_at INTEGER,
                    finished_at INTEGER,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS mail_deliveries (
                    id TEXT PRIMARY KEY,
                    batch_id TEXT NOT NULL REFERENCES mail_batches(id) ON DELETE CASCADE,
                    recipient_name TEXT NOT NULL,
                    recipient_email TEXT NOT NULL,
                    rendered_subject TEXT NOT NULL,
                    rendered_body TEXT NOT NULL,
                    status TEXT NOT NULL CHECK(status IN ('queued', 'sending', 'succeeded', 'failed')),
                    error_summary TEXT,
                    sent_at INTEGER,
                    updated_at INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mail_batches_user_created "
                "ON mail_batches(user_id, created_at DESC)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_mail_deliveries_batch "
                "ON mail_deliveries(batch_id)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (7, int(time.time())),
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

    def get_user_by_id(self, user_id: int) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT id, username, display_name FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        return None if row is None else self._row_to_user(row)

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

    @staticmethod
    def _validate_mail_template(name: str, subject: str, body: str) -> tuple[str, str, str]:
        if not isinstance(name, str) or not name.strip():
            raise ValueError("mail template name is required")
        if not isinstance(subject, str):
            raise ValueError("mail template subject must be a string")
        if not isinstance(body, str):
            raise ValueError("mail template body must be a string")
        return name.strip(), subject, body

    @staticmethod
    def _format_mail_template_timestamp(value: int | None) -> str | None:
        if value is None:
            return None
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value))

    @classmethod
    def _mail_template_from_row(cls, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["name"],
            "subject": row["subject"],
            "body": row["body"],
            "createdAt": cls._format_mail_template_timestamp(row["created_at"]),
            "updatedAt": cls._format_mail_template_timestamp(row["updated_at"]),
            "lastUsedAt": cls._format_mail_template_timestamp(row["last_used_at"]),
        }

    def create_mail_template(self, user_id: int, name: str, subject: str, body: str) -> dict:
        name, subject, body = self._validate_mail_template(name, subject, body)
        template_id = uuid.uuid4().hex[:12]
        now = int(time.time())
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO mail_templates(id, user_id, name, subject, body, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (template_id, user_id, name, subject, body, now, now),
                )
                row = connection.execute(
                    """
                    SELECT id, name, subject, body, created_at, updated_at, last_used_at
                    FROM mail_templates
                    WHERE id = ? AND user_id = ?
                    """,
                    (template_id, user_id),
                ).fetchone()
        except sqlite3.IntegrityError as error:
            raise ValueError("mail template could not be created") from error
        return self._mail_template_from_row(row)

    def list_mail_templates(self, user_id: int) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT id, name, subject, body, created_at, updated_at, last_used_at
                FROM mail_templates
                WHERE user_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (user_id,),
            ).fetchall()
        return [self._mail_template_from_row(row) for row in rows]

    def update_mail_template(
        self, user_id: int, template_id: str, name: str, subject: str, body: str
    ) -> dict | None:
        name, subject, body = self._validate_mail_template(name, subject, body)
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE mail_templates
                SET name = ?, subject = ?, body = ?, updated_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (name, subject, body, int(time.time()), template_id, user_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                """
                SELECT id, name, subject, body, created_at, updated_at, last_used_at
                FROM mail_templates
                WHERE id = ? AND user_id = ?
                """,
                (template_id, user_id),
            ).fetchone()
        return self._mail_template_from_row(row)

    def delete_mail_template(self, user_id: int, template_id: str) -> bool:
        with self.connect() as connection:
            cursor = connection.execute(
                "DELETE FROM mail_templates WHERE id = ? AND user_id = ?",
                (template_id, user_id),
            )
        return cursor.rowcount > 0

    def touch_mail_template(self, user_id: int, template_id: str) -> dict | None:
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE mail_templates
                SET last_used_at = ?
                WHERE id = ? AND user_id = ?
                """,
                (int(time.time()), template_id, user_id),
            )
            if cursor.rowcount == 0:
                return None
            row = connection.execute(
                """
                SELECT id, name, subject, body, created_at, updated_at, last_used_at
                FROM mail_templates
                WHERE id = ? AND user_id = ?
                """,
                (template_id, user_id),
            ).fetchone()
        return self._mail_template_from_row(row)

    def ensure_default_mail_templates(self, user_id: int, defaults: list[dict]) -> list[dict]:
        templates = []
        for default in defaults:
            if not isinstance(default, dict):
                raise ValueError("mail template defaults must be objects")
            templates.append(
                self._validate_mail_template(
                    default.get("name"), default.get("subject"), default.get("body")
                )
            )
        now = int(time.time())
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            initialization = connection.execute(
                """
                INSERT OR IGNORE INTO mail_template_default_initializations(user_id, initialized_at)
                VALUES (?, ?)
                """,
                (user_id, now),
            )
            existing_count = connection.execute(
                "SELECT COUNT(*) FROM mail_templates WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            if initialization.rowcount and existing_count == 0:
                connection.executemany(
                    """
                    INSERT INTO mail_templates(id, user_id, name, subject, body, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (uuid.uuid4().hex[:12], user_id, name, subject, body, now, now)
                        for name, subject, body in templates
                    ],
                )
        return self.list_mail_templates(user_id)

    @staticmethod
    def _validate_mail_draft(payload: dict) -> tuple[str | None, str, str, str]:
        if not isinstance(payload, dict):
            raise ValueError("mail draft payload must be an object")
        template_id = payload.get("templateId")
        if template_id is not None and (not isinstance(template_id, str) or not template_id):
            raise ValueError("mail draft templateId must be a non-empty string or null")
        subject = payload.get("subject")
        body = payload.get("body")
        recipients = payload.get("recipients")
        if not isinstance(subject, str) or not isinstance(body, str):
            raise ValueError("mail draft subject and body must be strings")
        if not isinstance(recipients, list):
            raise ValueError("mail draft recipients must be a list")
        try:
            recipients_json = json.dumps(recipients, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise ValueError("mail draft recipients must be JSON serializable") from error
        return template_id, subject, body, recipients_json

    def get_mail_draft(self, user_id: int) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT template_id, subject, body, recipients_json
                FROM mail_drafts
                WHERE user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "templateId": row["template_id"],
            "subject": row["subject"],
            "body": row["body"],
            "recipients": json.loads(row["recipients_json"]),
        }

    def put_mail_draft(self, user_id: int, payload: dict) -> None:
        template_id, subject, body, recipients_json = self._validate_mail_draft(payload)
        with self.connect() as connection:
            if template_id is not None:
                template = connection.execute(
                    "SELECT 1 FROM mail_templates WHERE id = ? AND user_id = ?",
                    (template_id, user_id),
                ).fetchone()
                if template is None:
                    raise ValueError("mail template does not exist for user")
            connection.execute(
                """
                INSERT INTO mail_drafts(user_id, template_id, subject, body, recipients_json, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    template_id = excluded.template_id,
                    subject = excluded.subject,
                    body = excluded.body,
                    recipients_json = excluded.recipients_json,
                    updated_at = excluded.updated_at
                """,
                (user_id, template_id, subject, body, recipients_json, int(time.time())),
            )

    @staticmethod
    def _format_mail_batch_timestamp(value: int | None) -> str | None:
        if value is None:
            return None
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(value / 1000))

    @staticmethod
    def _validate_mail_batch_content(
        subject: str, body: str, deliveries: list[dict]
    ) -> tuple[str, str, list[dict]]:
        if not isinstance(subject, str) or not isinstance(body, str):
            raise ValueError("mail batch subject and body must be strings")
        if not isinstance(deliveries, list) or not deliveries:
            raise ValueError("mail batch deliveries must be a non-empty list")
        normalized = []
        for delivery in deliveries:
            if not isinstance(delivery, dict):
                raise ValueError("mail delivery must be an object")
            fields = {
                "name": delivery.get("name"),
                "email": delivery.get("email"),
                "subject": delivery.get("subject"),
                "body": delivery.get("body"),
            }
            if any(not isinstance(value, str) or not value.strip() for value in fields.values()):
                raise ValueError("mail delivery requires non-empty name, email, subject and body")
            normalized.append({key: value.strip() for key, value in fields.items()})
        return subject, body, normalized

    @classmethod
    def _mail_delivery_from_row(cls, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "name": row["recipient_name"],
            "email": row["recipient_email"],
            "subject": row["rendered_subject"],
            "body": row["rendered_body"],
            "status": row["status"],
            "errorSummary": row["error_summary"],
            "sentAt": cls._format_mail_batch_timestamp(row["sent_at"]),
            "updatedAt": cls._format_mail_batch_timestamp(row["updated_at"]),
        }

    @classmethod
    def _mail_batch_from_row(cls, row: sqlite3.Row, deliveries: list[dict]) -> dict:
        return {
            "id": row["id"],
            "subject": row["subject_template"],
            "body": row["body_template"],
            "status": row["status"],
            "totalCount": row["total_count"],
            "sentCount": row["sent_count"],
            "failedCount": row["failed_count"],
            "createdAt": cls._format_mail_batch_timestamp(row["created_at"]),
            "startedAt": cls._format_mail_batch_timestamp(row["started_at"]),
            "finishedAt": cls._format_mail_batch_timestamp(row["finished_at"]),
            "updatedAt": cls._format_mail_batch_timestamp(row["updated_at"]),
            "deliveries": deliveries,
        }

    def _get_mail_batch_with_connection(
        self, connection: sqlite3.Connection, user_id: int, batch_id: str
    ) -> dict | None:
        row = connection.execute(
            "SELECT * FROM mail_batches WHERE id = ? AND user_id = ?", (batch_id, user_id)
        ).fetchone()
        if row is None:
            return None
        delivery_rows = connection.execute(
            "SELECT * FROM mail_deliveries WHERE batch_id = ? ORDER BY rowid ASC", (batch_id,)
        ).fetchall()
        return self._mail_batch_from_row(
            row, [self._mail_delivery_from_row(delivery) for delivery in delivery_rows]
        )

    def create_mail_batch(
        self, user_id: int, subject: str, body: str, deliveries: list[dict]
    ) -> dict:
        subject, body, deliveries = self._validate_mail_batch_content(subject, body, deliveries)
        batch_id = uuid.uuid4().hex[:12]
        now = self._job_timestamp()
        try:
            with self.connect() as connection:
                connection.execute(
                    """
                    INSERT INTO mail_batches(
                        id, user_id, subject_template, body_template, status, total_count,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, 'queued', ?, ?, ?)
                    """,
                    (batch_id, user_id, subject, body, len(deliveries), now, now),
                )
                connection.executemany(
                    """
                    INSERT INTO mail_deliveries(
                        id, batch_id, recipient_name, recipient_email, rendered_subject,
                        rendered_body, status, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'queued', ?)
                    """,
                    [
                        (
                            uuid.uuid4().hex[:12],
                            batch_id,
                            delivery["name"],
                            delivery["email"],
                            delivery["subject"],
                            delivery["body"],
                            now,
                        )
                        for delivery in deliveries
                    ],
                )
                batch = self._get_mail_batch_with_connection(connection, user_id, batch_id)
        except sqlite3.IntegrityError as error:
            raise ValueError("mail batch could not be created") from error
        return batch

    def get_mail_batch(self, user_id: int, batch_id: str) -> dict | None:
        with self.connect() as connection:
            return self._get_mail_batch_with_connection(connection, user_id, batch_id)

    def list_mail_batches(self, user_id: int, limit: int = 30) -> list[dict]:
        if not isinstance(limit, int) or limit <= 0:
            raise ValueError("limit must be a positive integer")
        with self.connect() as connection:
            batch_ids = connection.execute(
                """
                SELECT id FROM mail_batches
                WHERE user_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
                """,
                (user_id, limit),
            ).fetchall()
            return [
                self._get_mail_batch_with_connection(connection, user_id, row["id"])
                for row in batch_ids
            ]

    def start_mail_batch(self, user_id: int, batch_id: str) -> dict | None:
        now = self._job_timestamp()
        with self.connect() as connection:
            cursor = connection.execute(
                """
                UPDATE mail_batches
                SET status = 'running', updated_at = ?, started_at = COALESCE(started_at, ?)
                WHERE id = ? AND user_id = ? AND status = 'queued'
                """,
                (now, now, batch_id, user_id),
            )
            if cursor.rowcount == 0:
                return None
            return self._get_mail_batch_with_connection(connection, user_id, batch_id)

    def update_mail_delivery(
        self,
        user_id: int,
        batch_id: str,
        delivery_id: str,
        status: str,
        error_summary: str | None = None,
    ) -> None:
        if status not in {"sending", "succeeded", "failed"}:
            raise ValueError("invalid mail delivery status")
        if error_summary is not None and not isinstance(error_summary, str):
            raise ValueError("error_summary must be a string")
        now = self._job_timestamp()
        with self.connect() as connection:
            if status == "sending":
                connection.execute(
                    """
                    UPDATE mail_deliveries
                    SET status = 'sending', error_summary = NULL, updated_at = ?
                    WHERE id = ? AND batch_id = ? AND status = 'queued'
                      AND EXISTS (
                          SELECT 1 FROM mail_batches
                          WHERE id = ? AND user_id = ? AND status = 'running'
                      )
                    """,
                    (now, delivery_id, batch_id, batch_id, user_id),
                )
                return

            connection.execute(
                """
                UPDATE mail_deliveries
                SET status = ?, error_summary = ?, sent_at = ?, updated_at = ?
                WHERE id = ? AND batch_id = ? AND status = 'sending'
                  AND EXISTS (
                      SELECT 1 FROM mail_batches
                      WHERE id = ? AND user_id = ? AND status = 'running'
                  )
                """,
                (
                    status,
                    error_summary if status == "failed" else None,
                    now if status == "succeeded" else None,
                    now,
                    delivery_id,
                    batch_id,
                    batch_id,
                    user_id,
                ),
            )

    def finish_mail_batch(self, user_id: int, batch_id: str) -> dict | None:
        now = self._job_timestamp()
        with self.connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            batch = connection.execute(
                "SELECT * FROM mail_batches WHERE id = ? AND user_id = ?", (batch_id, user_id)
            ).fetchone()
            if batch is None or batch["status"] != "running":
                return None
            counts = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN status = 'succeeded' THEN 1 ELSE 0 END) AS sent_count,
                    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                    SUM(CASE WHEN status IN ('queued', 'sending') THEN 1 ELSE 0 END) AS pending_count
                FROM mail_deliveries WHERE batch_id = ?
                """,
                (batch_id,),
            ).fetchone()
            sent_count = counts["sent_count"] or 0
            failed_count = counts["failed_count"] or 0
            pending_count = counts["pending_count"] or 0
            if pending_count:
                return self._get_mail_batch_with_connection(connection, user_id, batch_id)
            if sent_count == batch["total_count"]:
                status = "succeeded"
            elif sent_count and failed_count:
                status = "partial_failed"
            else:
                status = "failed"
            connection.execute(
                """
                UPDATE mail_batches
                SET status = ?, sent_count = ?, failed_count = ?, updated_at = ?,
                    finished_at = ?
                WHERE id = ? AND user_id = ? AND status = 'running'
                """,
                (status, sent_count, failed_count, now, now, batch_id, user_id),
            )
            return self._get_mail_batch_with_connection(connection, user_id, batch_id)

    def create_retry_mail_batch(self, user_id: int, batch_id: str) -> dict:
        with self.connect() as connection:
            original = connection.execute(
                "SELECT * FROM mail_batches WHERE id = ? AND user_id = ?", (batch_id, user_id)
            ).fetchone()
            if original is None:
                raise ValueError("mail batch does not exist for user")
            failed_rows = connection.execute(
                """
                SELECT recipient_name, recipient_email, rendered_subject, rendered_body
                FROM mail_deliveries
                WHERE batch_id = ? AND status = 'failed'
                ORDER BY rowid ASC
                """,
                (batch_id,),
            ).fetchall()
        if not failed_rows:
            raise ValueError("没有可重试的失败邮件")
        return self.create_mail_batch(
            user_id,
            original["subject_template"],
            original["body_template"],
            [
                {
                    "name": row["recipient_name"],
                    "email": row["recipient_email"],
                    "subject": row["rendered_subject"],
                    "body": row["rendered_body"],
                }
                for row in failed_rows
            ],
        )

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

    def _upsert_integration_ciphertext(
        self, user_id: int, system_type: str, ciphertext: bytes, nonce: bytes
    ) -> None:
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

    def _integration_ciphertext_row(self, user_id: int, system_type: str):
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT ciphertext, nonce
                FROM integration_credentials
                WHERE user_id = ? AND system_type = ?
                """,
                (user_id, system_type),
            ).fetchone()
        return row

    def put_integration_secret(self, user_id: int, system_type: str, payload: dict) -> None:
        if not isinstance(payload, dict) or not payload:
            raise ValueError("integration secret payload must be a non-empty object")
        key = self._credential_key()
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(
            nonce, encoded, self._credential_associated_data(user_id, system_type)
        )
        self._upsert_integration_ciphertext(user_id, system_type, ciphertext, nonce)

    def get_integration_secret(self, user_id: int, system_type: str) -> dict | None:
        row = self._integration_ciphertext_row(user_id, system_type)
        if row is None:
            return None
        try:
            payload = AESGCM(self._credential_key()).decrypt(
                row["nonce"],
                row["ciphertext"],
                self._credential_associated_data(user_id, system_type),
            )
            result = json.loads(payload.decode("utf-8"))
        except (InvalidTag, UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError) as error:
            raise CredentialConfigurationError("integration credentials could not be decrypted") from error
        if not isinstance(result, dict):
            raise CredentialConfigurationError("integration credentials payload is invalid")
        return result

    def put_integration_credentials(
        self, user_id: int, system_type: str, account: str, password: str
    ) -> None:
        self.put_integration_secret(
            user_id,
            system_type,
            {"account": account.strip(), "password": password},
        )

    def get_integration_credentials(self, user_id: int, system_type: str) -> dict | None:
        self._credential_key()
        credentials = self.get_integration_secret(user_id, system_type)
        if credentials is None:
            return None
        if not {"account", "password"} <= credentials.keys():
            raise CredentialConfigurationError("integration credentials payload is invalid")
        return {"account": credentials["account"], "password": credentials["password"]}

    def has_integration_credentials(self, user_id: int, system_type: str) -> bool:
        self._credential_key()
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT 1 FROM integration_credentials
                WHERE user_id = ? AND system_type = ?
                """,
                (user_id, system_type),
            ).fetchone()
        return row is not None

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

    @classmethod
    def _validate_project_state(cls, state: dict | None) -> dict:
        if state is None:
            return {}
        if not isinstance(state, dict):
            raise ValueError("project state must be an object")
        state = cls.sanitize_job_data(state)
        try:
            json.dumps(state, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise ValueError("project state must be JSON serializable") from error
        return state

    @staticmethod
    def _validate_project_status(value: str, allowed: set[str], field_name: str) -> str:
        if value not in allowed:
            raise ValueError(f"invalid {field_name}")
        return value

    @classmethod
    def _project_from_row(cls, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "title": row["title"],
            "authorName": row["author_name"],
            "editorName": row["editor_name"],
            "reportStatus": row["report_status"],
            "authorStatus": row["author_status"],
            "bpmStatus": row["bpm_status"],
            "state": json.loads(row["state_json"]),
            "version": row["version"],
            "createdAt": cls._format_job_timestamp(row["created_at"]),
            "updatedAt": cls._format_job_timestamp(row["updated_at"]),
            "archivedAt": cls._format_job_timestamp(row["archived_at"]),
        }

    @classmethod
    def _revision_from_row(cls, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "version": row["version"],
            "snapshot": json.loads(row["snapshot_json"]),
            "reason": row["reason"],
            "createdAt": cls._format_job_timestamp(row["created_at"]),
        }

    @classmethod
    def _project_file_from_row(cls, row: sqlite3.Row) -> dict:
        return {
            "id": row["id"],
            "projectId": row["project_id"],
            "kind": row["kind"],
            "originalName": row["original_name"],
            "storagePath": row["storage_path"],
            "sha256": row["sha256"],
            "sizeBytes": row["size_bytes"],
            "createdAt": cls._format_job_timestamp(row["created_at"]),
        }

    def create_project(
        self,
        user_id: int,
        title: str,
        state: dict | None = None,
        *,
        author_name: str = "",
        editor_name: str = "",
        report_status: str = "empty",
        author_status: str = "unknown",
        bpm_status: str = "not_ready",
    ) -> dict:
        if not isinstance(title, str):
            raise ValueError("project title must be a string")
        title = self.sanitize_job_data(title).strip() or "未命名选题"
        author_name = self.sanitize_job_data(str(author_name)).strip()
        editor_name = self.sanitize_job_data(str(editor_name)).strip()
        state = self._validate_project_state(state)
        self._validate_project_status(report_status, PROJECT_REPORT_STATUSES, "report status")
        self._validate_project_status(author_status, PROJECT_AUTHOR_STATUSES, "author status")
        self._validate_project_status(bpm_status, PROJECT_BPM_STATUSES, "BPM status")
        project_id = str(uuid.uuid4())
        now = self._job_timestamp()
        with self.connect() as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO projects(
                        id, user_id, title, author_name, editor_name,
                        report_status, author_status, bpm_status, state_json,
                        version, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
                    """,
                    (
                        project_id,
                        user_id,
                        title,
                        author_name,
                        editor_name,
                        report_status,
                        author_status,
                        bpm_status,
                        json.dumps(state, ensure_ascii=False, separators=(",", ":")),
                        now,
                        now,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("user does not exist") from error
            row = connection.execute(
                "SELECT * FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
        return self._project_from_row(row)

    def get_project(self, user_id: int, project_id: str) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
        return None if row is None else self._project_from_row(row)

    def list_projects(
        self,
        user_id: int,
        *,
        include_archived: bool = False,
        query: str = "",
        status: str = "",
    ) -> list[dict]:
        clauses = ["user_id = ?"]
        parameters: list = [user_id]
        if not include_archived:
            clauses.append("archived_at IS NULL")
        query = query.strip() if isinstance(query, str) else ""
        if query:
            clauses.append("(title LIKE ? OR author_name LIKE ? OR editor_name LIKE ?)")
            like = f"%{query}%"
            parameters.extend((like, like, like))
        status = status.strip() if isinstance(status, str) else ""
        if status:
            clauses.append("(report_status = ? OR author_status = ? OR bpm_status = ?)")
            parameters.extend((status, status, status))
        sql = (
            "SELECT * FROM projects WHERE "
            + " AND ".join(clauses)
            + " ORDER BY updated_at DESC, rowid DESC"
        )
        with self.connect() as connection:
            rows = connection.execute(sql, parameters).fetchall()
        return [self._project_from_row(row) for row in rows]

    def update_project(
        self,
        user_id: int,
        project_id: str,
        expected_version: int,
        patch: dict,
        *,
        revision_reason: str | None = None,
    ) -> dict | None:
        if not isinstance(expected_version, int) or expected_version <= 0:
            raise ValueError("project version must be a positive integer")
        if not isinstance(patch, dict):
            raise ValueError("project patch must be an object")
        allowed = {
            "title",
            "author_name",
            "editor_name",
            "report_status",
            "author_status",
            "bpm_status",
            "state",
        }
        unknown = set(patch) - allowed
        if unknown:
            raise ValueError("project patch contains unsupported fields")
        values = dict(patch)
        if "title" in values:
            if not isinstance(values["title"], str):
                raise ValueError("project title must be a string")
            values["title"] = self.sanitize_job_data(values["title"]).strip() or "未命名选题"
        for key in ("author_name", "editor_name"):
            if key in values:
                values[key] = self.sanitize_job_data(str(values[key])).strip()
        if "report_status" in values:
            self._validate_project_status(
                values["report_status"], PROJECT_REPORT_STATUSES, "report status"
            )
        if "author_status" in values:
            self._validate_project_status(
                values["author_status"], PROJECT_AUTHOR_STATUSES, "author status"
            )
        if "bpm_status" in values:
            self._validate_project_status(
                values["bpm_status"], PROJECT_BPM_STATUSES, "BPM status"
            )
        if "state" in values:
            values["state_json"] = json.dumps(
                self._validate_project_state(values.pop("state")),
                ensure_ascii=False,
                separators=(",", ":"),
            )

        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
            if row is None:
                return None
            if row["version"] != expected_version:
                raise ProjectVersionConflict("project was updated by another request")
            assignments = [f"{key} = ?" for key in values]
            parameters = list(values.values())
            now = self._job_timestamp()
            assignments.extend(("version = version + 1", "updated_at = ?"))
            parameters.extend((now, project_id, user_id, expected_version))
            connection.execute(
                f"UPDATE projects SET {', '.join(assignments)} "
                "WHERE id = ? AND user_id = ? AND version = ?",
                parameters,
            )
            updated_row = connection.execute(
                "SELECT * FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
            if revision_reason is not None:
                reason = self.sanitize_job_data(str(revision_reason)).strip()
                if not reason:
                    raise ValueError("revision reason is required")
                snapshot = self._project_from_row(updated_row)
                connection.execute(
                    """
                    INSERT INTO project_revisions(
                        id, project_id, version, snapshot_json, reason, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        project_id,
                        updated_row["version"],
                        json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")),
                        reason,
                        now,
                    ),
                )
        return self._project_from_row(updated_row)

    def archive_project(
        self, user_id: int, project_id: str, expected_version: int
    ) -> dict | None:
        if not isinstance(expected_version, int) or expected_version <= 0:
            raise ValueError("project version must be a positive integer")
        now = self._job_timestamp()
        with self.connect() as connection:
            row = connection.execute(
                "SELECT version FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
            if row is None:
                return None
            if row["version"] != expected_version:
                raise ProjectVersionConflict("project was updated by another request")
            connection.execute(
                """
                UPDATE projects
                SET archived_at = ?, updated_at = ?, version = version + 1
                WHERE id = ? AND user_id = ? AND version = ?
                """,
                (now, now, project_id, user_id, expected_version),
            )
            updated_row = connection.execute(
                "SELECT * FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
        return self._project_from_row(updated_row)

    def list_project_revisions(self, user_id: int, project_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT pr.*
                FROM project_revisions AS pr
                JOIN projects AS p ON p.id = pr.project_id
                WHERE pr.project_id = ? AND p.user_id = ?
                ORDER BY pr.version DESC, pr.created_at DESC
                """,
                (project_id, user_id),
            ).fetchall()
        return [self._revision_from_row(row) for row in rows]

    def add_project_file(
        self,
        user_id: int,
        project_id: str,
        file_id: str,
        kind: str,
        original_name: str,
        storage_path: str,
        sha256: str,
        size_bytes: int,
    ) -> dict:
        if kind not in PROJECT_FILE_KINDS:
            raise ValueError("invalid project file kind")
        if not isinstance(file_id, str) or not file_id.strip():
            raise ValueError("project file id is required")
        if not isinstance(original_name, str) or not original_name.strip():
            raise ValueError("original file name is required")
        if not isinstance(storage_path, str) or not storage_path.strip():
            raise ValueError("project storage path is required")
        if not isinstance(sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", sha256):
            raise ValueError("invalid project file sha256")
        if not isinstance(size_bytes, int) or size_bytes < 0:
            raise ValueError("invalid project file size")
        now = self._job_timestamp()
        with self.connect() as connection:
            project = connection.execute(
                "SELECT 1 FROM projects WHERE id = ? AND user_id = ?",
                (project_id, user_id),
            ).fetchone()
            if project is None:
                raise ValueError("project does not exist for user")
            connection.execute(
                """
                INSERT INTO project_files(
                    id, project_id, kind, original_name, storage_path,
                    sha256, size_bytes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    file_id.strip(),
                    project_id,
                    kind,
                    self.sanitize_job_data(original_name).strip(),
                    storage_path.strip(),
                    sha256,
                    size_bytes,
                    now,
                ),
            )
            row = connection.execute(
                "SELECT * FROM project_files WHERE id = ?", (file_id.strip(),)
            ).fetchone()
        return self._project_file_from_row(row)

    def get_project_file(
        self, user_id: int, project_id: str, file_id: str
    ) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT pf.*
                FROM project_files AS pf
                JOIN projects AS p ON p.id = pf.project_id
                WHERE pf.id = ? AND pf.project_id = ? AND p.user_id = ?
                """,
                (file_id, project_id, user_id),
            ).fetchone()
        return None if row is None else self._project_file_from_row(row)

    def list_project_files(self, user_id: int, project_id: str) -> list[dict]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT pf.*
                FROM project_files AS pf
                JOIN projects AS p ON p.id = pf.project_id
                WHERE pf.project_id = ? AND p.user_id = ?
                ORDER BY pf.created_at DESC, pf.rowid DESC
                """,
                (project_id, user_id),
            ).fetchall()
        return [self._project_file_from_row(row) for row in rows]

    def delete_project_file(
        self, user_id: int, project_id: str, file_id: str
    ) -> dict | None:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT pf.*
                FROM project_files AS pf
                JOIN projects AS p ON p.id = pf.project_id
                WHERE pf.id = ? AND pf.project_id = ? AND p.user_id = ?
                """,
                (file_id, project_id, user_id),
            ).fetchone()
            if row is None:
                return None
            connection.execute(
                "DELETE FROM project_files WHERE id = ? AND project_id = ?",
                (file_id, project_id),
            )
        return self._project_file_from_row(row)

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

        public_payload = cls.sanitize_job_data(public_payload)
        try:
            json.dumps(public_payload, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise ValueError("public job payload must be JSON serializable") from error
        return public_payload

    @classmethod
    def sanitize_job_data(cls, value, known_secrets=()):
        secrets_to_redact = tuple(
            secret for secret in known_secrets if isinstance(secret, str) and secret
        )

        def sanitize_text(text: str) -> str:
            sanitized = AUTHORIZATION_BEARER_RE.sub(
                f"Authorization: Bearer {REDACTED_JOB_VALUE}", text
            )
            sanitized = BEARER_TOKEN_RE.sub(f"Bearer {REDACTED_JOB_VALUE}", sanitized)
            sanitized = SENSITIVE_JOB_ASSIGNMENT_RE.sub(
                lambda match: f"{match.group(1)}{REDACTED_JOB_VALUE}", sanitized
            )
            sanitized = API_KEY_VALUE_RE.sub(REDACTED_JOB_VALUE, sanitized)
            for secret in secrets_to_redact:
                sanitized = sanitized.replace(secret, REDACTED_JOB_VALUE)
            return sanitized

        def sanitize(nested_value):
            if isinstance(nested_value, dict):
                return {
                    key: REDACTED_JOB_VALUE
                    if cls._is_sensitive_job_key(key)
                    else sanitize(child_value)
                    for key, child_value in nested_value.items()
                }
            if isinstance(nested_value, (list, tuple)):
                return [sanitize(child_value) for child_value in nested_value]
            if isinstance(nested_value, str):
                return sanitize_text(nested_value)
            return nested_value

        return sanitize(value)

    @staticmethod
    def _is_sensitive_job_key(key) -> bool:
        normalized = re.sub(r"[^a-z0-9]", "", str(key).lower())
        if normalized in {item.replace("_", "") for item in SENSITIVE_JOB_PAYLOAD_KEYS}:
            return True
        return normalized.endswith(("password", "apikey", "authorization", "token", "secret"))

    @classmethod
    def _job_from_row(cls, row: sqlite3.Row) -> dict:
        payload = json.loads(row["public_payload_json"])
        job = {
            "id": row["id"],
            "type": row["job_type"],
            "title": row["title"],
            "status": row["status"],
            "projectId": row["project_id"] if "project_id" in row.keys() else None,
            "createdAt": cls._format_job_timestamp(row["created_at"]),
            "updatedAt": cls._format_job_timestamp(row["updated_at"]),
            "logs": json.loads(row["logs_json"]),
            "result": None if row["result_json"] is None else json.loads(row["result_json"]),
            "error": row["error_summary"],
        }
        job.update(payload)
        return job

    def create_job(
        self,
        user_id: int,
        job_type: str,
        title: str,
        public_payload: dict,
        project_id: str | None = None,
    ) -> dict:
        if not isinstance(job_type, str) or not job_type.strip():
            raise ValueError("job_type is required")
        if not isinstance(title, str) or not title.strip():
            raise ValueError("title is required")
        title = self.sanitize_job_data(title).strip()
        payload = self._validate_public_job_payload(public_payload)
        now = self._job_timestamp()
        job_id = uuid.uuid4().hex[:12]
        with self.connect() as connection:
            if project_id is not None:
                project = connection.execute(
                    "SELECT 1 FROM projects WHERE id = ? AND user_id = ?",
                    (project_id, user_id),
                ).fetchone()
                if project is None:
                    raise ValueError("project does not exist for user")
            try:
                connection.execute(
                    """
                    INSERT INTO jobs(
                        id, user_id, job_type, title, status, public_payload_json,
                        logs_json, created_at, updated_at, project_id
                    ) VALUES (?, ?, ?, ?, 'queued', ?, '[]', ?, ?, ?)
                    """,
                    (
                        job_id,
                        user_id,
                        job_type.strip(),
                        title.strip(),
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                        now,
                        now,
                        project_id,
                    ),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("user does not exist") from error
            row = connection.execute(
                "SELECT * FROM jobs WHERE id = ? AND user_id = ?", (job_id, user_id)
            ).fetchone()
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
        result = self.sanitize_job_data(result)
        error_summary = self.sanitize_job_data(error_summary)
        try:
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

    def mark_interrupted_jobs_failed(self) -> int:
        now = self._job_timestamp()
        with self.connect() as connection:
            result = connection.execute(
                """
                UPDATE jobs
                SET status = 'failed', result_json = NULL, error_summary = ?,
                    updated_at = ?, finished_at = ?
                WHERE status IN ('queued', 'running')
                """,
                (INTERRUPTED_JOB_ERROR, now, now),
            )
        return result.rowcount

    def append_job_log(self, job_id: str, user_id: int, message: str) -> None:
        if not isinstance(message, str) or not message.strip():
            raise ValueError("job log message is required")
        message = self.sanitize_job_data(message).strip()
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
