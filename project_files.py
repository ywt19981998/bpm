import hashlib
import io
import os
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path


SAFE_ID_RE = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
REQUIRED_DOCX_MEMBERS = {"[Content_Types].xml", "word/document.xml"}
DEFAULT_MAX_BYTES = 20 * 1024 * 1024


class InvalidProjectFile(ValueError):
    pass


@dataclass(frozen=True)
class StoredProjectFile:
    relative_path: str
    sha256: str
    size_bytes: int


class ProjectFileStore:
    def __init__(self, root: Path, max_bytes: int = DEFAULT_MAX_BYTES):
        if not isinstance(max_bytes, int) or max_bytes <= 0:
            raise ValueError("max_bytes must be a positive integer")
        self.root = Path(root)
        self.max_bytes = max_bytes

    @staticmethod
    def _safe_id(value, label: str) -> str:
        text = str(value)
        if not SAFE_ID_RE.fullmatch(text):
            raise InvalidProjectFile(f"invalid {label}")
        return text

    def _validate_docx(self, content: bytes) -> None:
        if not isinstance(content, bytes) or not content:
            raise InvalidProjectFile("DOCX file is empty")
        if len(content) > self.max_bytes:
            raise InvalidProjectFile(
                f"DOCX file is too large; limit is {self.max_bytes} bytes (20 MB by default)"
            )
        try:
            with zipfile.ZipFile(io.BytesIO(content)) as archive:
                members = set(archive.namelist())
                if not REQUIRED_DOCX_MEMBERS <= members:
                    raise InvalidProjectFile("file is not a complete DOCX package")
                for required in REQUIRED_DOCX_MEMBERS:
                    archive.getinfo(required)
        except (zipfile.BadZipFile, KeyError, OSError) as error:
            raise InvalidProjectFile("file is not a valid DOCX package") from error

    def resolve(self, relative_path: str) -> Path:
        if not isinstance(relative_path, str) or not relative_path:
            raise InvalidProjectFile("project file path is required")
        raw = Path(relative_path)
        if raw.is_absolute():
            raise InvalidProjectFile("absolute project file paths are not allowed")
        root = self.root.resolve()
        candidate = (root / raw).resolve()
        if not candidate.is_relative_to(root):
            raise InvalidProjectFile("project file path leaves the storage root")
        return candidate

    def save_docx(
        self,
        user_id: int,
        project_id: str,
        file_id: str,
        content: bytes,
    ) -> StoredProjectFile:
        if not isinstance(user_id, int) or user_id <= 0:
            raise InvalidProjectFile("invalid user id")
        user_part = self._safe_id(user_id, "user id")
        project_part = self._safe_id(project_id, "project id")
        file_part = self._safe_id(file_id, "file id")
        self._validate_docx(content)

        relative_path = f"{user_part}/{project_part}/{file_part}.docx"
        final_path = self.resolve(relative_path)
        final_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                prefix=f".{file_part}-",
                suffix=".tmp",
                dir=final_path.parent,
                delete=False,
            ) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(content)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, final_path)
        except OSError:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)
            raise

        return StoredProjectFile(
            relative_path=relative_path,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        )

    def remove(self, relative_path: str) -> None:
        path = self.resolve(relative_path)
        path.unlink(missing_ok=True)
