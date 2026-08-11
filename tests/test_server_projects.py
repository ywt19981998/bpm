import base64
import http.client
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import quote
from unittest import mock

from docx import Document

import server
from app_storage import AppStore
from project_domain import SECTION_KEYS
from project_files import ProjectFileStore


def valid_docx_bytes(text="项目文件"):
    buffer = io.BytesIO()
    document = Document()
    document.add_paragraph(text)
    document.save(buffer)
    return buffer.getvalue()


def confirmed_project_state():
    scores = [30, 5, 4, 0, 18, 8]
    maximums = [35, 10, 5, 5, 35, 10]
    names = ["选题内容", "作者情况", "策划过程与可行性", "获奖潜质", "成本与盈利估算", "市场定位与营销"]
    return {
        "sections": [
            {"key": key, "title": title, "text": f"{title}正文", "confirmed": True}
            for key, title in SECTION_KEYS
        ],
        "scoreItems": [
            [name, maximum, score]
            for name, maximum, score in zip(names, maximums, scores)
        ],
        "bpmTopic": {
            "bookName": "人工智能通识",
            "authorName": "王老师",
            "class1": "02",
            "class2": "0201",
            "class3": "020101",
            "class4": "02010103",
            "gbClass": "G",
            "readLevel": "高等理工",
            "brief": "内容简介",
            "reader": "高校师生",
            "feature": "选题特色",
            "compare": "同类比较",
        },
        "authorMaintenance": {"name": "王老师", "bio": "王老师简介"},
    }


class ServerProjectApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store = server.APP_STORE
        self.original_file_store = getattr(server, "PROJECT_FILE_STORE", None)
        self.key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        server.APP_STORE = AppStore(
            Path(self.temp_dir.name) / "app.db", credential_key=self.key
        )
        server.PROJECT_FILE_STORE = ProjectFileStore(
            Path(self.temp_dir.name) / "projects"
        )
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = self.register("editor01", "张编辑")
        self.other_cookie = self.register("editor02", "李编辑")

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join()
        self.httpd.server_close()
        server.APP_STORE = self.original_store
        if self.original_file_store is None:
            delattr(server, "PROJECT_FILE_STORE")
        else:
            server.PROJECT_FILE_STORE = self.original_file_store
        self.temp_dir.cleanup()

    def request(self, method, path, payload=None, cookie=None, headers=None):
        body = None
        request_headers = dict(headers or {})
        if payload is not None:
            body = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
            request_headers.setdefault("Content-Type", "application/json")
        if cookie:
            request_headers["Cookie"] = cookie
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port)
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read()
        connection.close()
        return result

    def json_request(self, method, path, payload=None, cookie=None):
        status, headers, body = self.request(method, path, payload, cookie)
        return status, headers, json.loads(body.decode("utf-8"))

    def register(self, username, display_name):
        status, headers, _ = self.json_request(
            "POST",
            "/api/auth/register",
            {"username": username, "password": "S3cure-pass", "displayName": display_name},
        )
        self.assertEqual(status, 201)
        return headers["Set-Cookie"].split(";", 1)[0]

    def multipart(self, fields, *, file_field="file", filename="application.docx", content=None):
        boundary = "ProjectBoundary"
        parts = []
        for name, value in fields.items():
            parts.extend(
                (
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    str(value).encode("utf-8"),
                    b"\r\n",
                )
            )
        parts.extend(
            (
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{file_field}"; filename="{filename}"\r\n'.encode(),
                b"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n",
                valid_docx_bytes() if content is None else content,
                b"\r\n",
                f"--{boundary}--\r\n".encode(),
            )
        )
        return b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    def multipart_files(self, fields, files):
        boundary = "ProjectMultiBoundary"
        parts = []
        for name, value in fields.items():
            parts.extend(
                (
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                    str(value).encode("utf-8"),
                    b"\r\n",
                )
            )
        for name, filename, content in files:
            parts.extend(
                (
                    f"--{boundary}\r\n".encode(),
                    f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode(),
                    b"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n",
                    content,
                    b"\r\n",
                )
            )
        parts.append(f"--{boundary}--\r\n".encode())
        return b"".join(parts), {"Content-Type": f"multipart/form-data; boundary={boundary}"}

    def create_project(self, *, title="测试选题", state=None, cookie=None):
        payload = {"title": title}
        if state is not None:
            payload["state"] = state
        status, _, body = self.json_request(
            "POST", "/api/projects", payload, cookie or self.cookie
        )
        self.assertEqual(status, 201)
        return body["project"]

    def test_project_crud_search_archive_conflict_and_user_isolation(self):
        status, _, body = self.json_request("GET", "/api/projects")
        self.assertEqual(status, 401)
        self.assertEqual(body["code"], "AUTH_REQUIRED")

        project = self.create_project(title="数据库原理")
        self.assertEqual(project["editorName"], "张编辑")
        status, _, body = self.json_request("GET", "/api/projects", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in body["projects"]], [project["id"]])

        for method in ("GET", "PUT"):
            payload = None if method == "GET" else {"version": project["version"], "title": "越权"}
            status, _, _ = self.json_request(
                method, f"/api/projects/{project['id']}", payload, self.other_cookie
            )
            self.assertEqual(status, 404)

        status, _, body = self.json_request(
            "PUT",
            f"/api/projects/{project['id']}",
            {"version": project["version"], "title": "数据库系统"},
            self.cookie,
        )
        self.assertEqual(status, 200)
        updated = body["project"]
        self.assertEqual(updated["title"], "数据库系统")
        self.assertEqual(updated["version"], project["version"] + 1)

        status, _, body = self.json_request(
            "PUT",
            f"/api/projects/{project['id']}",
            {"version": project["version"], "title": "过期写入"},
            self.cookie,
        )
        self.assertEqual(status, 409)
        self.assertEqual(body["code"], "PROJECT_VERSION_CONFLICT")

        status, _, body = self.json_request(
            "GET", f"/api/projects?q={quote('数据库')}&status=empty", cookie=self.cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(len(body["projects"]), 1)

        status, _, body = self.json_request(
            "POST",
            f"/api/projects/{project['id']}/archive",
            {"version": updated["version"]},
            self.cookie,
        )
        self.assertEqual(status, 200)
        self.assertIsNotNone(body["project"]["archivedAt"])
        self.assertEqual(
            self.json_request("GET", "/api/projects", cookie=self.cookie)[2]["projects"],
            [],
        )
        self.assertEqual(
            len(
                self.json_request(
                    "GET", "/api/projects?includeArchived=true", cookie=self.cookie
                )[2]["projects"]
            ),
            1,
        )

    def test_valid_docx_upload_download_and_invalid_file_rollback(self):
        project = self.create_project()
        content = valid_docx_bytes("原始申报表")
        payload, headers = self.multipart({"kind": "application"}, content=content)

        status, _, body = self.request(
            "POST",
            f"/api/projects/{project['id']}/files",
            payload,
            self.cookie,
            headers,
        )
        self.assertEqual(status, 201)
        file_record = json.loads(body.decode("utf-8"))["file"]
        self.assertEqual(file_record["kind"], "application")
        self.assertNotIn("原始申报表", file_record["storagePath"])

        status, response_headers, downloaded = self.request(
            "GET",
            f"/api/projects/{project['id']}/files/{file_record['id']}",
            cookie=self.cookie,
        )
        self.assertEqual(status, 200)
        self.assertEqual(downloaded, content)
        self.assertIn("attachment", response_headers["Content-Disposition"])
        self.assertEqual(
            self.request(
                "GET",
                f"/api/projects/{project['id']}/files/{file_record['id']}",
                cookie=self.other_cookie,
            )[0],
            404,
        )

        invalid_project = self.create_project(title="无效文件测试")
        payload, headers = self.multipart(
            {"kind": "application"}, filename="broken.docx", content=b"not-docx"
        )
        status, _, body = self.request(
            "POST",
            f"/api/projects/{invalid_project['id']}/files",
            payload,
            self.cookie,
            headers,
        )
        self.assertEqual(status, 400)
        self.assertEqual(
            server.APP_STORE.list_project_files(self.user_id(), invalid_project["id"]),
            [],
        )
        self.assertFalse(
            (Path(self.temp_dir.name) / "projects" / str(self.user_id()) / invalid_project["id"]).exists()
        )
        self.assertEqual(json.loads(body.decode("utf-8"))["code"], "PROJECT_FILE_INVALID")

    def test_preflight_uses_project_state_and_server_credential_status(self):
        project = self.create_project(state=confirmed_project_state())

        status, _, body = self.json_request(
            "GET", f"/api/projects/{project['id']}/preflight", cookie=self.cookie
        )
        self.assertEqual(status, 200)
        self.assertFalse(body["preflight"]["ready"])
        self.assertEqual(
            {row["key"] for row in body["preflight"]["rows"] if row["status"] == "blocking_missing"},
            {"bpmCredentials"},
        )

        server.APP_STORE.put_integration_credentials(
            self.user_id(), "phei_bpm", "editor-bpm", "bpm-password"
        )
        status, _, body = self.json_request(
            "GET", f"/api/projects/{project['id']}/preflight", cookie=self.cookie
        )
        self.assertEqual(status, 200)
        self.assertTrue(body["preflight"]["ready"])
        self.assertNotIn("bpm-password", json.dumps(body, ensure_ascii=False))

    def test_generation_persists_report_and_application_file_in_project(self):
        project = self.create_project(title="人工智能通识")
        generated = confirmed_project_state()
        for section in generated["sections"]:
            section["confirmed"] = False
        generated.update(
            {
                "title": "人工智能通识",
                "scores": generated.pop("scoreItems"),
                "total": 65,
            }
        )
        content = valid_docx_bytes("选题申报表")
        payload, headers = self.multipart(
            {"projectId": project["id"], "version": project["version"]},
            filename="人工智能通识-申报表.docx",
            content=content,
        )

        with mock.patch.object(server, "generate_report_from_upload", return_value=generated):
            status, _, raw = self.request(
                "POST", "/api/generate-report", payload, self.cookie, headers
            )

        self.assertEqual(status, 200)
        body = json.loads(raw.decode("utf-8"))
        self.assertEqual(body["project"]["reportStatus"], "draft")
        self.assertEqual(body["project"]["editorName"], "张编辑")
        self.assertEqual(body["project"]["state"]["bpmTopic"]["projectEditor"], "张编辑")
        self.assertEqual(len(body["files"]), 1)
        self.assertEqual(body["files"][0]["kind"], "application")
        self.assertEqual(
            body["project"]["state"]["sourceFiles"]["application"]["fileId"],
            body["files"][0]["id"],
        )

    def test_quick_import_creates_confirmed_project_with_both_source_files(self):
        imported = confirmed_project_state()
        imported.update(
            {
                "title": "数据库系统",
                "scores": imported.pop("scoreItems"),
                "total": 65,
            }
        )
        imported["bpmTopic"]["bookName"] = "数据库系统"
        payload, headers = self.multipart_files(
            {},
            [
                ("application", "数据库-申报表.docx", valid_docx_bytes("申报表")),
                ("report", "数据库-策划报告.docx", valid_docx_bytes("策划报告")),
            ],
        )

        with mock.patch.object(server, "import_bpm_sources", return_value=imported):
            status, _, raw = self.request(
                "POST", "/api/projects/import", payload, self.cookie, headers
            )

        self.assertEqual(status, 201)
        body = json.loads(raw.decode("utf-8"))
        self.assertEqual(body["project"]["title"], "数据库系统")
        self.assertEqual(body["project"]["reportStatus"], "confirmed")
        self.assertEqual(body["project"]["bpmStatus"], "ready")
        self.assertEqual(
            {item["kind"] for item in body["files"]},
            {"application", "confirmed_report"},
        )
        self.assertEqual(
            set(body["project"]["state"]["sourceFiles"]), {"application", "report"}
        )

    def test_project_export_uses_saved_state_and_records_download(self):
        project = self.create_project(title="人工智能通识", state=confirmed_project_state())
        output = Path(self.temp_dir.name) / "项目策划报告.docx"
        output.write_bytes(valid_docx_bytes("导出内容"))

        with mock.patch.object(server, "build_docx", return_value=output) as build:
            status, headers, body = self.request(
                "POST",
                "/api/export-docx",
                {"projectId": project["id"], "title": "伪造标题"},
                self.cookie,
            )

        self.assertEqual(status, 200)
        self.assertEqual(body, output.read_bytes())
        self.assertIn("attachment", headers["Content-Disposition"])
        export_payload = build.call_args.args[0]
        self.assertEqual(export_payload["title"], "人工智能通识")
        self.assertEqual(export_payload["editorName"], "张编辑")
        refreshed = server.APP_STORE.get_project(self.user_id(), project["id"])
        self.assertTrue(refreshed["state"]["docxExported"])
        self.assertEqual(
            [item["kind"] for item in server.APP_STORE.list_project_files(self.user_id(), project["id"])],
            ["exported_report"],
        )

    def test_project_job_uses_trusted_saved_state_and_tracks_project(self):
        project = self.create_project(title="人工智能通识", state=confirmed_project_state())
        server.APP_STORE.put_integration_credentials(
            self.user_id(), "phei_bpm", "editor-bpm", "bpm-password"
        )
        captured = []

        with mock.patch.object(server.JOB_QUEUE, "put", side_effect=captured.append):
            status, _, body = self.json_request(
                "POST",
                "/api/bpm-topic-jobs",
                {
                    "projectId": project["id"],
                    "title": "伪造标题",
                    "bpmTopic": {"bookName": "伪造选题", "projectEditor": "伪造编辑"},
                    "userId": 999,
                },
                self.cookie,
            )

        self.assertEqual(status, 200)
        self.assertEqual(body["projectId"], project["id"])
        queued_payload = captured[0][3]
        self.assertEqual(queued_payload["title"], "人工智能通识")
        self.assertEqual(queued_payload["bpmTopic"]["bookName"], "人工智能通识")
        self.assertEqual(queued_payload["bpmTopic"]["projectEditor"], "张编辑")
        self.assertNotIn("userId", queued_payload)
        self.assertNotIn("bpm", queued_payload)
        self.assertEqual(
            server.APP_STORE.get_project(self.user_id(), project["id"])["bpmStatus"],
            "queued",
        )

    def user_id(self):
        return server.APP_STORE.authenticate_user("editor01", "S3cure-pass")["id"]


if __name__ == "__main__":
    unittest.main()
