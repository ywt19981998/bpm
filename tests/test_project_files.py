import hashlib
import io
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document

from project_files import InvalidProjectFile, ProjectFileStore


def valid_docx_bytes(text="测试文档"):
    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(buffer)
    return buffer.getvalue()


def incomplete_docx_bytes():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types />")
    return buffer.getvalue()


class ProjectFileStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name) / "projects"
        self.files = ProjectFileStore(self.root)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_valid_docx_is_stored_atomically_under_generated_ids(self):
        content = valid_docx_bytes()

        stored = self.files.save_docx(7, "project-id", "file-id", content)

        self.assertEqual(stored.relative_path, "7/project-id/file-id.docx")
        self.assertEqual(stored.sha256, hashlib.sha256(content).hexdigest())
        self.assertEqual(stored.size_bytes, len(content))
        final_path = self.files.resolve(stored.relative_path)
        self.assertEqual(final_path.read_bytes(), content)
        self.assertEqual(list(final_path.parent.glob("*.tmp")), [])

    def test_rejects_non_docx_and_incomplete_zip_packages(self):
        for content in (b"not-a-zip", incomplete_docx_bytes()):
            with self.subTest(size=len(content)), self.assertRaises(InvalidProjectFile):
                self.files.save_docx(7, "project-id", "file-id", content)

        self.assertFalse(self.root.exists())

    def test_rejects_payloads_above_the_configured_limit(self):
        limited = ProjectFileStore(self.root, max_bytes=16)

        with self.assertRaisesRegex(InvalidProjectFile, "20 MB|too large"):
            limited.save_docx(7, "project-id", "file-id", valid_docx_bytes())

    def test_rejects_unsafe_identifiers_and_resolution_traversal(self):
        content = valid_docx_bytes()
        for user_id, project_id, file_id in (
            (0, "project-id", "file-id"),
            (7, "../project", "file-id"),
            (7, "project/id", "file-id"),
            (7, "project-id", "../file"),
            (7, "project-id", "file/id"),
        ):
            with self.subTest(
                user_id=user_id, project_id=project_id, file_id=file_id
            ), self.assertRaises(InvalidProjectFile):
                self.files.save_docx(user_id, project_id, file_id, content)

        for relative_path in ("../app.db", "/tmp/file.docx", "7/../../app.db"):
            with self.subTest(relative_path=relative_path), self.assertRaises(
                InvalidProjectFile
            ):
                self.files.resolve(relative_path)

    def test_remove_only_deletes_files_inside_the_store(self):
        stored = self.files.save_docx(
            7, "project-id", "file-id", valid_docx_bytes()
        )
        final_path = self.files.resolve(stored.relative_path)

        self.files.remove(stored.relative_path)

        self.assertFalse(final_path.exists())
        with self.assertRaises(InvalidProjectFile):
            self.files.remove("../outside.docx")


if __name__ == "__main__":
    unittest.main()
