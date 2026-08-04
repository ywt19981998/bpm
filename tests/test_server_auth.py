import http.client
import base64
import io
import json
import os
import queue
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
        result = response.status, dict(response.getheaders()), response.read().decode("utf-8", "replace")
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

    def test_static_allowlist_blocks_runtime_data_and_repository_files(self):
        for path in (
            "/.env",
            "/data/app.db",
            "/server.py",
            "/README.md",
            "/output/bpm-runs/topic.json",
            "/backups/app.db",
        ):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path)
                self.assertIn(status, {403, 404})

        for path in (
            "/",
            "/index.html",
            "/auth_session_generation.js",
            "/vendor/lucide-0.468.0.min.js",
            "/assets/report-preview.png",
        ):
            with self.subTest(path=path):
                status, _, _ = self.request("GET", path)
                self.assertEqual(status, 200)

    def test_export_uses_the_authenticated_users_name_not_forged_fields(self):
        self.register()
        export_path = Path(self.temp_dir.name) / "report.docx"
        export_path.write_bytes(b"test-docx")
        forged_payload = {
            "title": "署名测试",
            "editorName": "客户端伪造编辑",
            "createdBy": "客户端伪造发起人",
            "sections": [],
            "scores": [],
        }
        with patch("server.build_docx", return_value=export_path) as build:
            status, _, body = self.request(
                "POST", "/api/export-docx", forged_payload, cookie=self.cookie
            )

        self.assertEqual(status, 200)
        self.assertEqual(body, "test-docx")
        built_payload = build.call_args.args[0]
        self.assertEqual(built_payload["editorName"], "张编辑")
        self.assertEqual(built_payload["createdBy"], "张编辑")

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

        with patch.object(server.APP_STORE, "list_jobs", return_value=[]):
            status, _, body = self.request("GET", "/api/bpm-jobs", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"jobs": []})


class ServerModelConfigTests(unittest.TestCase):
    valid_model_result = {"title": "测试选题", "sections": [], "scores": []}

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store = server.APP_STORE
        server.APP_STORE = AppStore(Path(self.temp_dir.name) / "app.db")
        self.httpd = server.ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.cookie = self.register()

    def tearDown(self):
        self.httpd.shutdown()
        self.thread.join()
        self.httpd.server_close()
        server.APP_STORE = self.original_store
        self.temp_dir.cleanup()

    def register(self):
        status, headers, _ = self.request(
            "POST",
            "/api/auth/register",
            {"username": "model-editor", "password": "S3cure-pass", "displayName": "模型编辑"},
        )
        self.assertEqual(status, 201)
        return headers["Set-Cookie"].split(";", 1)[0]

    def request(self, method, path, payload=None, cookie=None, headers=None):
        body = None if payload is None else (
            payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        )
        request_headers = dict(headers or {})
        if body is not None:
            request_headers.setdefault("Content-Type", "application/json")
        if cookie:
            request_headers["Cookie"] = cookie
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port)
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode("utf-8")
        connection.close()
        return result

    def post_generate_form(self, fields, cookie):
        boundary = "Task8Boundary"
        parts = []
        for name, value in fields.items():
            parts.extend(
                (
                    f"--{boundary}\r\n".encode("utf-8"),
                    f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode("utf-8"),
                    str(value).encode("utf-8"),
                    b"\r\n",
                )
            )
        parts.extend(
            (
                f"--{boundary}\r\n".encode("utf-8"),
                b'Content-Disposition: form-data; name="file"; filename="application.docx"\r\n',
                b"Content-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n",
                b"test-docx",
                b"\r\n",
                f"--{boundary}--\r\n".encode("utf-8"),
            )
        )
        return self.request(
            "POST",
            "/api/generate-report",
            payload=b"".join(parts),
            cookie=cookie,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )

    def test_full_report_uses_server_pro_model_despite_client_model_fields(self):
        class Extractor:
            def build_payload(self, *_args, **_kwargs):
                return {"title": "测试选题"}

        with (
            patch.object(server, "load_extractor", return_value=Extractor()),
            patch.object(server, "build_bpm_topic", return_value={}),
            patch.object(server, "call_model", return_value=self.valid_model_result) as call,
        ):
            status, _, body = self.post_generate_form(
                {
                    "model": "attacker-model",
                    "apiKey": "attacker-key",
                    "modelUrl": "https://attacker.invalid",
                },
                cookie=self.cookie,
            )

        self.assertEqual(status, 200, body)
        self.assertEqual(server.DEFAULT_MODEL, "deepseek-v4-pro")
        self.assertEqual(call.call_args.args[1:], (server.DEFAULT_MODEL_URL, server.DEFAULT_API_KEY, "deepseek-v4-pro"))

    def test_missing_server_key_returns_a_generic_configuration_error(self):
        with patch.object(server, "DEFAULT_API_KEY", ""):
            with self.assertRaisesRegex(ValueError, "模型服务暂不可用") as error:
                server.call_model("test prompt", server.DEFAULT_MODEL_URL, server.DEFAULT_API_KEY, server.DEFAULT_MODEL)

        self.assertNotIn("DEEPSEEK_API_KEY", str(error.exception))

    def test_missing_server_key_returns_503_without_echoing_client_key(self):
        class Extractor:
            def build_payload(self, *_args, **_kwargs):
                return {"title": "测试选题"}

        log_entries = []
        with (
            patch.object(server, "DEFAULT_API_KEY", ""),
            patch.object(server, "load_extractor", return_value=Extractor()),
            patch.object(server, "runtime_log", side_effect=log_entries.append),
            patch.object(server, "build_bpm_topic", return_value={}),
        ):
            status, _, body = self.post_generate_form(
                {"apiKey": "attacker-key", "model": "attacker-model"}, cookie=self.cookie
            )

        self.assertEqual(status, 503)
        self.assertEqual(body, server.MODEL_CONFIGURATION_ERROR)
        self.assertNotIn("attacker-key", body)
        self.assertNotIn("attacker-key", "\n".join(log_entries))


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


class ServerJobHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store = server.APP_STORE
        self.key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        self.db_path = Path(self.temp_dir.name) / "app.db"
        server.APP_STORE = AppStore(self.db_path, credential_key=self.key)
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

    @staticmethod
    def valid_topic_payload():
        return {
            "title": "队列测试选题",
            "editorName": "客户端伪造编辑",
            "bpm": {"user": "client-account", "password": "client-secret"},
            "sections": [
                {"key": f"section-{index}", "text": "已确认正文", "confirmed": True}
                for index in range(6)
            ],
            "bpmTopic": {"bookName": "队列测试选题"},
        }

    def current_user(self):
        return server.APP_STORE.get_user_for_session(self.cookie.split("=", 1)[1])

    def test_queued_item_keeps_only_business_payload_without_bpm_credentials(self):
        user = self.current_user()
        server.APP_STORE.put_integration_credentials(
            user["id"], "phei_bpm", "stored-account", "stored-secret"
        )
        work_queue = queue.Queue()
        with patch.object(server, "JOB_QUEUE", work_queue):
            job = server.create_bpm_job(self.valid_topic_payload(), user)

        item = work_queue.get_nowait()
        self.assertEqual(item[:3], (job["id"], user["id"], "topic"))
        self.assertNotIn("bpm", item[3])
        self.assertNotIn("client-secret", json.dumps(item[3], ensure_ascii=False))
        self.assertNotIn("stored-secret", json.dumps(item[3], ensure_ascii=False))

    def test_worker_reads_updated_credentials_only_when_the_job_starts(self):
        user = self.current_user()
        server.APP_STORE.put_integration_credentials(
            user["id"], "phei_bpm", "old-account", "old-secret"
        )
        job = server.APP_STORE.create_job(user["id"], "topic", "执行时更新", {})
        server.APP_STORE.put_integration_credentials(
            user["id"], "phei_bpm", "new-account", "new-secret"
        )
        work_queue = queue.Queue()
        work_queue.put((job["id"], user["id"], "topic", {"title": "执行时更新"}))
        stop_event = threading.Event()

        captured_payloads = []

        def submit(payload):
            captured_payloads.append(json.loads(json.dumps(payload, ensure_ascii=False)))
            return {"title": "执行时更新"}

        with patch("server.run_bpm_topic_submit", side_effect=submit) as submit_mock:
            worker = threading.Thread(
                target=server.bpm_job_worker, args=(work_queue, stop_event), daemon=True
            )
            worker.start()
            work_queue.join()
            stop_event.set()
            worker.join(timeout=2)

        trusted_payload = captured_payloads[0]
        self.assertEqual(trusted_payload["editorName"], "张编辑")
        self.assertEqual(trusted_payload["bpm"]["user"], "new-account")
        self.assertEqual(trusted_payload["bpm"]["password"], "new-secret")
        self.assertNotIn("password", submit_mock.call_args.args[0]["bpm"])

    def test_worker_fails_queued_job_when_credentials_are_deleted_before_execution(self):
        user = self.current_user()
        server.APP_STORE.put_integration_credentials(
            user["id"], "phei_bpm", "stored-account", "stored-secret"
        )
        job = server.APP_STORE.create_job(user["id"], "topic", "配置已删除", {})
        server.APP_STORE.delete_integration_credentials(user["id"], "phei_bpm")
        work_queue = queue.Queue()
        work_queue.put((job["id"], user["id"], "topic", {"title": "配置已删除"}))
        stop_event = threading.Event()

        with patch("server.run_bpm_topic_submit") as submit:
            worker = threading.Thread(
                target=server.bpm_job_worker, args=(work_queue, stop_event), daemon=True
            )
            worker.start()
            work_queue.join()
            stop_event.set()
            worker.join(timeout=2)

        submit.assert_not_called()
        failed = next(item for item in server.APP_STORE.list_jobs(user["id"]) if item["id"] == job["id"])
        self.assertEqual(failed["status"], "failed")
        self.assertIn("请先保存 BPM 账号和密码", failed["error"])

    def test_jobs_are_isolated_and_survive_replacing_the_app_store(self):
        first_user = server.APP_STORE.get_user_for_session(self.cookie.split("=", 1)[1])
        job = server.APP_STORE.create_job(
            first_user["id"], "topic", "仅张编辑可见", {"createdBy": "张编辑"}
        )

        status, _, body = self.request("GET", "/api/bpm-jobs", cookie=self.other_cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"jobs": []})

        server.APP_STORE = AppStore(self.db_path, credential_key=self.key)
        status, _, body = self.request("GET", "/api/bpm-jobs", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["jobs"][0]["id"], job["id"])

    def test_worker_continues_after_storage_failures_and_completes_next_job(self):
        user = server.APP_STORE.get_user_for_session(self.cookie.split("=", 1)[1])
        server.APP_STORE.put_integration_credentials(
            user["id"], "phei_bpm", "stored-account", "stored-secret"
        )
        first = server.APP_STORE.create_job(user["id"], "topic", "第一任务", {})
        second = server.APP_STORE.create_job(user["id"], "topic", "第二任务", {})
        work_queue = queue.Queue()
        stop_event = threading.Event()
        work_queue.put((first["id"], user["id"], "topic", {"title": "第一任务", "bpm": {}}))
        work_queue.put((second["id"], user["id"], "topic", {"title": "第二任务", "bpm": {}}))
        original_update = server.APP_STORE.update_job
        original_append = server.APP_STORE.append_job_log
        update_failed = False
        append_failed = False

        def flaky_update(*args, **kwargs):
            nonlocal update_failed
            if not update_failed:
                update_failed = True
                raise OSError("temporary update failure")
            return original_update(*args, **kwargs)

        def flaky_append(*args, **kwargs):
            nonlocal append_failed
            if not append_failed:
                append_failed = True
                raise OSError("temporary log failure")
            return original_append(*args, **kwargs)

        with patch.object(server.APP_STORE, "update_job", side_effect=flaky_update), patch.object(
            server.APP_STORE, "append_job_log", side_effect=flaky_append
        ), patch("server.run_bpm_topic_submit", side_effect=[{"title": "第一任务"}, {"title": "第二任务"}]) as submit:
            worker = threading.Thread(
                target=server.bpm_job_worker, args=(work_queue, stop_event), daemon=True
            )
            worker.start()
            work_queue.join()
            stop_event.set()
            worker.join(timeout=2)

        self.assertTrue(update_failed)
        self.assertTrue(append_failed)
        self.assertFalse(worker.is_alive())
        self.assertEqual([call.args[0]["title"] for call in submit.call_args_list], ["第一任务", "第二任务"])
        self.assertEqual(server.APP_STORE.list_jobs(user["id"])[0]["status"], "succeeded")

    def test_worker_survives_malformed_bpm_payload_cleanup_and_completes_next_job(self):
        user = server.APP_STORE.get_user_for_session(self.cookie.split("=", 1)[1])
        server.APP_STORE.put_integration_credentials(
            user["id"], "phei_bpm", "stored-account", "stored-secret"
        )
        malformed = server.APP_STORE.create_job(user["id"], "topic", "畸形任务", {})
        next_job = server.APP_STORE.create_job(user["id"], "topic", "后续任务", {})
        work_queue = queue.Queue()
        stop_event = threading.Event()
        completed = threading.Event()
        task_done_calls = 0
        original_task_done = work_queue.task_done

        def counting_task_done():
            nonlocal task_done_calls
            task_done_calls += 1
            original_task_done()

        work_queue.task_done = counting_task_done
        work_queue.put((malformed["id"], user["id"], "topic", {"bpm": None}))
        work_queue.put((next_job["id"], user["id"], "topic", {"title": "后续任务", "bpm": {}}))

        def submit(payload):
            completed.set()
            return {"title": payload["title"]}

        with patch("server.run_bpm_topic_submit", side_effect=submit):
            worker = threading.Thread(
                target=server.bpm_job_worker, args=(work_queue, stop_event), daemon=True
            )
            worker.start()
            self.assertTrue(completed.wait(timeout=2))
            work_queue.join()
            stop_event.set()
            worker.join(timeout=2)

        self.assertFalse(worker.is_alive())
        self.assertEqual(task_done_calls, 2)
        self.assertEqual(server.APP_STORE.list_jobs(user["id"])[0]["status"], "succeeded")


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
