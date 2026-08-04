import http.client
import base64
import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from app_storage import AppStore


class ServerAuthHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store = server.APP_STORE
        server.APP_STORE = AppStore(Path(self.temp_dir.name) / "app.db")
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = None

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join()
        self.httpd.server_close()
        server.APP_STORE = self.original_store
        self.temp_dir.cleanup()

    def request(self, method, path, payload=None, cookie=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode("utf-8")
        connection.close()
        return result

    def register(self):
        status, headers, body = self.request(
            "POST",
            "/api/auth/register",
            {"username": "editor01", "password": "S3cure-pass", "displayName": "张编辑"},
        )
        self.assertEqual(status, 201)
        self.assertEqual(json.loads(body)["user"], {"id": 1, "username": "editor01", "displayName": "张编辑"})
        self.assertIn("phei_session=", headers["Set-Cookie"])
        self.assertIn("Path=/", headers["Set-Cookie"])
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", headers["Set-Cookie"])
        self.assertIn("Max-Age=604800", headers["Set-Cookie"])
        self.cookie = headers["Set-Cookie"].split(";", 1)[0]

    def test_registers_user_and_returns_current_user_for_session(self):
        self.register()
        status, _, body = self.request("GET", "/api/auth/me", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["user"]["displayName"], "张编辑")

    def test_logout_clears_session_cookie_and_invalidates_session(self):
        self.register()
        status, headers, body = self.request("POST", "/api/auth/logout", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        status, _, body = self.request("GET", "/api/auth/me", cookie=self.cookie)
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body)["code"], "AUTH_REQUIRED")

    def test_logout_requires_a_valid_session(self):
        status, _, body = self.request("POST", "/api/auth/logout")
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body), {"error": "请先登录。", "code": "AUTH_REQUIRED"})

    def test_rejects_wrong_login(self):
        self.register()
        status, _, body = self.request(
            "POST", "/api/auth/login", {"username": "editor01", "password": "wrong-pass"}
        )
        self.assertEqual(status, 401)
        self.assertEqual(json.loads(body)["code"], "AUTH_INVALID")

    def test_protects_business_apis_without_a_session(self):
        for method, path in (("GET", "/api/bpm-jobs"), ("POST", "/api/generate-report")):
            with self.subTest(method=method, path=path):
                status, _, body = self.request(method, path, {})
                self.assertEqual(status, 401)
                self.assertEqual(json.loads(body), {"error": "请先登录。", "code": "AUTH_REQUIRED"})

    def test_authenticated_requests_dispatch_to_every_existing_business_route(self):
        self.register()
        routes = (
            ("/api/generate-report", "handle_generate_report", ()),
            ("/api/import-bpm-sources", "handle_import_bpm_sources", ()),
            ("/api/bpm-jobs", "handle_bpm_job", ("topic",)),
            ("/api/bpm-topic-jobs", "handle_bpm_job", ("topic",)),
            ("/api/bpm-author-jobs", "handle_bpm_job", ("author",)),
            ("/api/bpm-submit", "handle_bpm_submit", ()),
        )
        for path, handler_name, expected_args in routes:
            calls = []

            def stub(request_handler, *args):
                calls.append(args)
                request_handler.send_json(200, {"route": path})

            with self.subTest(path=path), patch.object(server.Handler, handler_name, stub):
                status, _, body = self.request("POST", path, {}, cookie=self.cookie)
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body), {"route": path})
                self.assertEqual(calls, [expected_args])

        export_path = Path(self.temp_dir.name) / "report.docx"
        export_path.write_bytes(b"test-docx")
        with patch("server.build_docx", return_value=export_path):
            status, _, body = self.request("POST", "/api/export-docx", {}, cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(body, "test-docx")

        with patch("server.public_jobs", return_value=[]):
            status, _, body = self.request("GET", "/api/bpm-jobs", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"jobs": []})


class ServerCredentialHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store = server.APP_STORE
        key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        server.APP_STORE = AppStore(Path(self.temp_dir.name) / "app.db", credential_key=key)
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
        self.temp_dir.cleanup()

    def request(self, method, path, payload=None, cookie=None):
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        headers = {}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if cookie:
            headers["Cookie"] = cookie
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port)
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode("utf-8")
        connection.close()
        return result

    def register(self, username, display_name):
        status, headers, _ = self.request(
            "POST",
            "/api/auth/register",
            {"username": username, "password": "S3cure-pass", "displayName": display_name},
        )
        self.assertEqual(status, 201)
        return headers["Set-Cookie"].split(";", 1)[0]

    def test_credentials_require_a_session_for_every_method(self):
        for method in ("GET", "PUT", "DELETE"):
            with self.subTest(method=method):
                status, _, body = self.request(method, "/api/integrations/phei-bpm", {})
                self.assertEqual(status, 401)
                self.assertEqual(json.loads(body)["code"], "AUTH_REQUIRED")

    def test_rejects_empty_account_or_password(self):
        for payload in (
            {"account": "", "password": "bpm-secret"},
            {"account": "editor-bpm", "password": ""},
            {"account": "   ", "password": "bpm-secret"},
        ):
            with self.subTest(payload=payload):
                status, _, body = self.request(
                    "PUT", "/api/integrations/phei-bpm", payload, cookie=self.cookie
                )
                self.assertEqual(status, 400)
                self.assertNotIn("bpm-secret", body)

    def test_saves_masks_updates_and_clears_credentials_without_echoing_passwords(self):
        status, _, body = self.request(
            "PUT",
            "/api/integrations/phei-bpm",
            {"account": "editor-bpm", "password": "bpm-secret"},
            cookie=self.cookie,
        )
        self.assertEqual(status, 200)
        self.assertNotIn("bpm-secret", body)

        status, _, body = self.request("GET", "/api/integrations/phei-bpm", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"configured": True, "accountMasked": "e********m"})
        self.assertNotIn("bpm-secret", body)

        status, _, body = self.request(
            "PUT",
            "/api/integrations/phei-bpm",
            {"account": "updated-account", "password": "updated-secret"},
            cookie=self.cookie,
        )
        self.assertEqual(status, 200)
        self.assertNotIn("updated-secret", body)
        status, _, body = self.request("GET", "/api/integrations/phei-bpm", cookie=self.cookie)
        self.assertEqual(json.loads(body), {"configured": True, "accountMasked": "u*************t"})

        status, _, body = self.request("DELETE", "/api/integrations/phei-bpm", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"configured": False, "accountMasked": None})
        self.assertNotIn("updated-secret", body)

    def test_credentials_are_isolated_by_authenticated_user(self):
        status, _, body = self.request(
            "PUT",
            "/api/integrations/phei-bpm",
            {"account": "editor-bpm", "password": "bpm-secret"},
            cookie=self.cookie,
        )
        self.assertEqual(status, 200)
        self.assertNotIn("bpm-secret", body)

        status, _, body = self.request(
            "GET", "/api/integrations/phei-bpm", cookie=self.other_cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"configured": False, "accountMasked": None})
        self.assertNotIn("bpm-secret", body)

    def test_legacy_bpm_submit_uses_current_users_stored_credentials(self):
        status, _, _ = self.request(
            "PUT",
            "/api/integrations/phei-bpm",
            {"account": "stored-account", "password": "stored-secret"},
            cookie=self.cookie,
        )
        self.assertEqual(status, 200)
        client_payload = {
            "title": "可信注入测试",
            "editorName": "客户端伪造编辑",
            "bpm": {
                "user": "client-account",
                "password": "client-secret",
                "name": "客户端伪造编辑",
            },
        }

        with patch("server.run_bpm_submit", return_value={"ok": True}) as submit:
            status, _, body = self.request(
                "POST", "/api/bpm-submit", client_payload, cookie=self.cookie
            )

        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        trusted_payload = submit.call_args.args[0]
        self.assertEqual(trusted_payload["editorName"], "张编辑")
        self.assertEqual(
            trusted_payload["bpm"],
            {
                "url": os.environ.get(
                    "BPM_URL", "http://bpm.phei.com.cn:8088/portal/r/w"
                ),
                "user": "stored-account",
                "name": "张编辑",
                "password": "stored-secret",
            },
        )
        self.assertNotIn("client-secret", json.dumps(trusted_payload, ensure_ascii=False))
        self.assertNotIn("client-account", json.dumps(trusted_payload, ensure_ascii=False))
        self.assertNotIn("stored-secret", body)
        self.assertNotIn("client-secret", body)


class MultipartFormTests(unittest.TestCase):
    def test_repeated_fields_keep_the_first_value_and_file(self):
        boundary = "Task3Boundary"

        def field(name, value, filename=None):
            disposition = f'Content-Disposition: form-data; name="{name}"'
            if filename:
                disposition += f'; filename="{filename}"'
            return f"--{boundary}\r\n{disposition}\r\n\r\n".encode("utf-8") + value + b"\r\n"

        body = b"".join(
            (
                field("model", b"first-model"),
                field("model", b"last-model"),
                field("file", b"first-file", "first.docx"),
                field("file", b"last-file", "last.docx"),
                f"--{boundary}--\r\n".encode("utf-8"),
            )
        )
        form = server.MultipartForm(
            io.BytesIO(body),
            {"Content-Type": f"multipart/form-data; boundary={boundary}"},
            {"CONTENT_LENGTH": str(len(body))},
        )

        self.assertEqual(form.getfirst("model"), "first-model")
        self.assertEqual(form["file"].filename, "first.docx")
        self.assertEqual(form["file"].file.read(), b"first-file")


if __name__ == "__main__":
    unittest.main()
