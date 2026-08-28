import base64
import http.client
import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import server
from app_storage import AppStore


def smtp_payload():
    return {
        "host": "smtp.example.com",
        "port": 465,
        "security": "ssl",
        "account": "editor@example.com",
        "password": "smtp-auth-code",
        "fromName": "张编辑",
        "fromAddress": "editor@example.com",
    }


def recipient():
    return {"name": "张老师", "email": "teacher@example.edu.cn"}


class ServerMailHttpTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_store = server.APP_STORE
        key = base64.urlsafe_b64encode(b"m" * 32).decode("ascii")
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

    def request(self, method, path, payload=None, cookie=None, headers=None):
        body = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers = dict(headers or {})
        if body is not None:
            request_headers.setdefault("Content-Type", "application/json")
        if cookie:
            request_headers["Cookie"] = cookie
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port)
        connection.request(method, path, body=body, headers=request_headers)
        response = connection.getresponse()
        result = response.status, dict(response.getheaders()), response.read().decode("utf-8", "replace")
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

    def save_smtp_config(self):
        status, _, _ = self.request("PUT", "/api/integrations/smtp", smtp_payload(), self.cookie)
        self.assertEqual(status, 200)

    def test_mail_apis_require_authentication(self):
        for method, path in (("GET", "/api/integrations/smtp"), ("GET", "/api/mail/templates")):
            with self.subTest(path=path):
                status, _, body = self.request(method, path)
                self.assertEqual(status, 401)
                self.assertEqual(json.loads(body)["code"], "AUTH_REQUIRED")

    def test_smtp_config_is_user_scoped_and_password_is_never_returned(self):
        self.save_smtp_config()
        status, _, body = self.request("GET", "/api/integrations/smtp", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(body)["configured"])
        self.assertNotIn("smtp-auth-code", body)
        self.assertNotIn("editor@example.com", body)

        status, _, body = self.request("GET", "/api/integrations/smtp", cookie=self.other_cookie)
        self.assertEqual(status, 200)
        self.assertFalse(json.loads(body)["configured"])

    def test_smtp_test_uses_saved_secret_and_does_not_accept_client_password(self):
        self.save_smtp_config()
        captured_settings = []
        with patch(
            "server.test_smtp_connection",
            side_effect=lambda settings: captured_settings.append(dict(settings)),
        ) as test_connection:
            status, _, body = self.request(
                "POST", "/api/integrations/smtp/test", {"password": "forged"}, self.cookie
            )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        test_connection.assert_called_once()
        self.assertEqual(captured_settings[0]["password"], "smtp-auth-code")

    def test_templates_preview_and_batches_are_user_scoped(self):
        status, _, body = self.request(
            "POST", "/api/mail/templates", {"name": "邀请", "subject": "{{姓名}}合作", "body": "{{姓名}}老师您好"}, self.cookie
        )
        self.assertEqual(status, 201)
        template = json.loads(body)["template"]
        status, _, body = self.request("GET", "/api/mail/templates", cookie=self.other_cookie)
        self.assertEqual(status, 200)
        self.assertNotIn(template["id"], [item["id"] for item in json.loads(body)["templates"]])

        status, _, body = self.request(
            "POST", "/api/mail/preview",
            {"subject": template["subject"], "body": template["body"], "recipients": [recipient()]},
            self.cookie,
        )
        self.assertEqual(status, 200)
        preview = json.loads(body)["preview"]
        self.assertEqual(preview[0]["subject"], "张老师合作")
        self.assertEqual(preview[0]["body"], "张老师老师您好")

        self.save_smtp_config()
        status, _, body = self.request(
            "POST", "/api/mail/batches",
            {"confirmed": False, "subject": "邀请", "body": "正文", "recipients": [recipient()]},
            self.cookie,
            {"Idempotency-Key": "create-confirmation-001"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["code"], "MAIL_CONFIRMATION_REQUIRED")

        with patch("server.schedule_mail_batch") as schedule:
            status, _, body = self.request(
                "POST", "/api/mail/batches",
                {"confirmed": True, "subject": "邀请", "body": "{{姓名}}老师您好", "recipients": [recipient()]},
                self.cookie,
                {"Idempotency-Key": "create-user-scope-001"},
            )
        self.assertEqual(status, 201)
        batch = json.loads(body)["batch"]
        schedule.assert_called_once_with(batch["id"], 1)
        status, _, _ = self.request("GET", f"/api/mail/batches/{batch['id']}", cookie=self.other_cookie)
        self.assertEqual(status, 404)

    def test_template_crud_and_draft_endpoints(self):
        status, _, body = self.request("GET", "/api/mail/templates", cookie=self.cookie)
        self.assertEqual(status, 200)
        defaults = json.loads(body)["templates"]
        self.assertEqual(len(defaults), 2)

        status, _, body = self.request(
            "POST",
            "/api/mail/templates",
            {"name": "自定义", "subject": "主题", "body": "正文"},
            self.cookie,
        )
        self.assertEqual(status, 201)
        template = json.loads(body)["template"]
        status, _, body = self.request(
            "PUT",
            f"/api/mail/templates/{template['id']}",
            {"name": "已修改", "subject": "新主题", "body": "新正文"},
            self.cookie,
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["template"]["name"], "已修改")

        draft = {
            "templateId": template["id"],
            "subject": "草稿主题",
            "body": "草稿正文",
            "recipients": [recipient()],
        }
        status, _, _ = self.request("PUT", "/api/mail/draft", draft, self.cookie)
        self.assertEqual(status, 200)
        status, _, body = self.request("GET", "/api/mail/draft", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["draft"], draft)
        status, _, body = self.request("GET", "/api/mail/draft", cookie=self.other_cookie)
        self.assertEqual(status, 200)
        self.assertIsNone(json.loads(body)["draft"])

        status, _, _ = self.request(
            "DELETE", f"/api/mail/templates/{template['id']}", cookie=self.other_cookie
        )
        self.assertEqual(status, 404)
        status, _, _ = self.request(
            "DELETE", f"/api/mail/templates/{template['id']}", cookie=self.cookie
        )
        self.assertEqual(status, 200)

    def test_smtp_delete_and_invalid_configuration(self):
        status, _, body = self.request(
            "PUT", "/api/integrations/smtp", {**smtp_payload(), "port": 70000}, self.cookie
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["code"], "SMTP_INVALID_INPUT")

        self.save_smtp_config()
        status, _, body = self.request("DELETE", "/api/integrations/smtp", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"configured": False, "accountMasked": None})

    def test_parse_invalid_file_and_preview_invalid_compose_return_400(self):
        boundary = "mail-boundary"
        content = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="teachers.txt"\r\n'
            "Content-Type: text/plain\r\n\r\n"
            "姓名,邮箱\n张老师,teacher@example.edu.cn\n"
            f"\r\n--{boundary}--\r\n"
        ).encode("utf-8")
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port)
        connection.request(
            "POST",
            "/api/mail/recipients/parse",
            body=content,
            headers={
                "Content-Type": f"multipart/form-data; boundary={boundary}",
                "Cookie": self.cookie,
            },
        )
        response = connection.getresponse()
        status, body = response.status, response.read().decode("utf-8")
        connection.close()
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["code"], "MAIL_RECIPIENT_FILE_INVALID")

        status, _, body = self.request(
            "POST",
            "/api/mail/preview",
            {"subject": "", "body": "正文", "recipients": [recipient()]},
            self.cookie,
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["code"], "MAIL_COMPOSE_INVALID")

    def test_batch_list_get_and_retry_require_confirmation(self):
        self.save_smtp_config()
        user = server.APP_STORE.get_user_for_session(self.cookie.split("=", 1)[1])
        original = server.APP_STORE.create_mail_batch(
            user["id"],
            "邀请",
            "正文",
            [{**recipient(), "subject": "邀请", "body": "正文"}],
        )
        server.APP_STORE.start_mail_batch(user["id"], original["id"])
        delivery = original["deliveries"][0]
        server.APP_STORE.update_mail_delivery(
            user["id"], original["id"], delivery["id"], "sending"
        )
        server.APP_STORE.update_mail_delivery(
            user["id"], original["id"], delivery["id"], "failed", "模拟失败"
        )
        server.APP_STORE.finish_mail_batch(user["id"], original["id"])

        status, _, body = self.request("GET", "/api/mail/batches", cookie=self.cookie)
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["batches"][0]["id"], original["id"])
        status, _, body = self.request(
            "GET", f"/api/mail/batches/{original['id']}", cookie=self.cookie
        )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["batch"]["failedCount"], 1)

        status, _, body = self.request(
            "POST",
            f"/api/mail/batches/{original['id']}/retry",
            {"confirmed": False},
            self.cookie,
            {"Idempotency-Key": "retry-confirmation-001"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["code"], "MAIL_CONFIRMATION_REQUIRED")

        with patch("server.schedule_mail_batch") as schedule:
            status, _, body = self.request(
                "POST",
                f"/api/mail/batches/{original['id']}/retry",
                {"confirmed": True},
                self.cookie,
                {"Idempotency-Key": "retry-failed-mail-001"},
            )
        self.assertEqual(status, 201)
        retry = json.loads(body)["batch"]
        self.assertEqual(retry["totalCount"], 1)
        schedule.assert_called_once_with(retry["id"], user["id"])

        with patch("server.schedule_mail_batch") as replay_schedule:
            status, _, body = self.request(
                "POST",
                f"/api/mail/batches/{original['id']}/retry",
                {"confirmed": True},
                self.cookie,
                {"Idempotency-Key": "retry-failed-mail-001"},
            )
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["batch"]["id"], retry["id"])
        replay_schedule.assert_not_called()

    def test_mail_batch_scheduler_uses_a_daemon_thread(self):
        with patch("server.threading.Thread") as worker:
            server.schedule_mail_batch("batch-1", 42)

        worker.assert_called_once_with(
            target=server.process_mail_batch,
            args=("batch-1", 42),
            daemon=True,
        )
        worker.return_value.start.assert_called_once_with()

    def test_batch_creation_rejects_client_smtp_secret(self):
        self.save_smtp_config()
        status, _, body = self.request(
            "POST",
            "/api/mail/batches",
            {
                "confirmed": True,
                "subject": "邀请",
                "body": "正文",
                "recipients": [recipient()],
                "password": "forged-secret",
            },
            self.cookie,
            {"Idempotency-Key": "create-secret-check-001"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["code"], "MAIL_CLIENT_SECRET_FORBIDDEN")

    def test_batch_creation_requires_a_valid_idempotency_key(self):
        self.save_smtp_config()
        payload = {
            "confirmed": True,
            "subject": "邀请",
            "body": "正文",
            "recipients": [recipient()],
        }

        status, _, body = self.request(
            "POST", "/api/mail/batches", payload, self.cookie
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["code"], "MAIL_IDEMPOTENCY_KEY_INVALID")

        status, _, body = self.request(
            "POST",
            "/api/mail/batches",
            payload,
            self.cookie,
            {"Idempotency-Key": "bad key with spaces"},
        )
        self.assertEqual(status, 400)
        self.assertEqual(json.loads(body)["code"], "MAIL_IDEMPOTENCY_KEY_INVALID")

    def test_json_request_body_has_a_hard_size_limit(self):
        with patch("server.MAX_JSON_BODY_BYTES", 1024):
            status, _, body = self.request(
                "POST",
                "/api/mail/templates",
                {"name": "超大模板", "subject": "x" * 2048, "body": "正文"},
                self.cookie,
            )

        self.assertEqual(status, 413)
        self.assertEqual(json.loads(body)["code"], "REQUEST_BODY_TOO_LARGE")

    def test_batch_creation_is_persistently_idempotent_and_detects_conflict(self):
        self.save_smtp_config()
        payload = {
            "confirmed": True,
            "subject": "合作邀请",
            "body": "{{姓名}}老师您好",
            "recipients": [recipient()],
        }
        headers = {"Idempotency-Key": "create-mail-batch-001"}

        with patch("server.schedule_mail_batch") as schedule:
            first_status, _, first_body = self.request(
                "POST", "/api/mail/batches", payload, self.cookie, headers
            )
            replay_status, _, replay_body = self.request(
                "POST", "/api/mail/batches", payload, self.cookie, headers
            )

        self.assertEqual(first_status, 201)
        self.assertEqual(replay_status, 200)
        first = json.loads(first_body)["batch"]
        replay = json.loads(replay_body)["batch"]
        self.assertEqual(replay["id"], first["id"])
        schedule.assert_called_once_with(first["id"], 1)

        conflict_status, _, conflict_body = self.request(
            "POST",
            "/api/mail/batches",
            {**payload, "subject": "另一个主题"},
            self.cookie,
            headers,
        )
        self.assertEqual(conflict_status, 409)
        self.assertEqual(
            json.loads(conflict_body)["code"], "MAIL_IDEMPOTENCY_CONFLICT"
        )

    def test_parse_endpoint_accepts_csv(self):
        boundary = "mail-boundary"
        content = (
            f"--{boundary}\r\n"
            'Content-Disposition: form-data; name="file"; filename="teachers.csv"\r\n'
            "Content-Type: text/csv\r\n\r\n"
            "姓名,邮箱,学校\n张老师,teacher@example.edu.cn,测试大学\n"
            f"\r\n--{boundary}--\r\n"
        ).encode("utf-8")
        connection = http.client.HTTPConnection("127.0.0.1", self.httpd.server_port)
        connection.request(
            "POST", "/api/mail/recipients/parse", body=content,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}", "Cookie": self.cookie},
        )
        response = connection.getresponse()
        status, body = response.status, response.read().decode("utf-8")
        connection.close()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["valid"][0]["name"], "张老师")

    def test_process_mail_batch_reads_server_secret_and_persists_results(self):
        self.save_smtp_config()
        user = server.APP_STORE.get_user_for_session(self.cookie.split("=", 1)[1])
        batch = server.APP_STORE.create_mail_batch(
            user["id"], "邀请", "正文", [{**recipient(), "subject": "邀请", "body": "张老师您好"}]
        )
        captured_settings = []
        with patch(
            "server.send_smtp_message",
            side_effect=lambda settings, _delivery: captured_settings.append(dict(settings)),
        ) as send:
            server.process_mail_batch(batch["id"], user["id"])
        send.assert_called_once()
        self.assertEqual(captured_settings[0]["password"], "smtp-auth-code")
        self.assertEqual(server.APP_STORE.get_mail_batch(user["id"], batch["id"])["status"], "succeeded")

    def test_process_mail_batch_exits_when_batch_was_already_claimed(self):
        self.save_smtp_config()
        user = server.APP_STORE.get_user_for_session(self.cookie.split("=", 1)[1])
        batch = server.APP_STORE.create_mail_batch(
            user["id"], "邀请", "正文", [{**recipient(), "subject": "邀请", "body": "正文"}]
        )
        server.APP_STORE.start_mail_batch(user["id"], batch["id"])

        with patch("server.send_smtp_message") as send:
            server.process_mail_batch(batch["id"], user["id"])

        send.assert_not_called()

    def test_process_mail_batch_sanitizes_delivery_failure(self):
        self.save_smtp_config()
        user = server.APP_STORE.get_user_for_session(self.cookie.split("=", 1)[1])
        batch = server.APP_STORE.create_mail_batch(
            user["id"], "邀请", "正文", [{**recipient(), "subject": "邀请", "body": "正文"}]
        )
        with patch(
            "server.send_smtp_message",
            side_effect=RuntimeError("login failed smtp-auth-code"),
        ):
            server.process_mail_batch(batch["id"], user["id"])

        result = server.APP_STORE.get_mail_batch(user["id"], batch["id"])
        self.assertEqual(result["status"], "failed")
        self.assertNotIn("smtp-auth-code", json.dumps(result, ensure_ascii=False))

    def test_process_mail_batch_sends_only_after_claiming_delivery_state(self):
        self.save_smtp_config()
        user = server.APP_STORE.get_user_for_session(self.cookie.split("=", 1)[1])
        batch = server.APP_STORE.create_mail_batch(
            user["id"], "邀请", "正文", [{**recipient(), "subject": "邀请", "body": "正文"}]
        )
        original_update = server.APP_STORE.update_mail_delivery

        def lose_delivery_claim(user_id, batch_id, delivery_id, status, error_summary=None):
            if status == "sending":
                return False
            return original_update(user_id, batch_id, delivery_id, status, error_summary)

        with patch.object(
            server.APP_STORE, "update_mail_delivery", side_effect=lose_delivery_claim
        ), patch("server.send_smtp_message") as send:
            server.process_mail_batch(batch["id"], user["id"])

        send.assert_not_called()


class ServerStartupSafetyTests(unittest.TestCase):
    def test_import_does_not_mark_interrupted_batches(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "app.db"
            key = base64.urlsafe_b64encode(b"i" * 32).decode("ascii")
            store = AppStore(db_path, credential_key=key)
            user_id = store.register_user("importcheck", "S3cure-pass", "导入检查")["id"]
            batch = store.create_mail_batch(
                user_id,
                "待发送",
                "正文",
                [{**recipient(), "subject": "待发送", "body": "正文"}],
            )
            env = os.environ.copy()
            env.update(
                {
                    "PHEI_DB_PATH": str(db_path),
                    "PHEI_PROJECTS_PATH": str(Path(temp_dir) / "projects"),
                    "APP_CREDENTIAL_KEY": key,
                }
            )

            completed = subprocess.run(
                [sys.executable, "-c", "import server"],
                cwd=server.ROOT,
                env=env,
                capture_output=True,
                text=True,
                timeout=20,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            reopened = AppStore(db_path, credential_key=key)
            self.assertEqual(reopened.get_mail_batch(user_id, batch["id"])["status"], "queued")

    def test_single_instance_lock_rejects_a_second_holder(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / "server.lock"
            with server.single_instance_lock(lock_path):
                with self.assertRaisesRegex(RuntimeError, "已在运行"):
                    with server.single_instance_lock(lock_path):
                        pass

    def test_main_locks_before_recovering_interrupted_work(self):
        events = []

        @contextmanager
        def fake_lock(_path):
            events.append("lock")
            yield
            events.append("unlock")

        class FakeServer:
            def serve_forever(self):
                events.append("serve")

            def server_close(self):
                events.append("close")

        with patch("server.single_instance_lock", fake_lock), patch.object(
            server.APP_STORE,
            "mark_interrupted_jobs_failed",
            side_effect=lambda: events.append("recover-jobs"),
        ), patch.object(
            server.APP_STORE,
            "mark_interrupted_mail_batches_failed",
            side_effect=lambda: events.append("recover-mail"),
        ), patch("server.ThreadingHTTPServer", return_value=FakeServer()):
            server.main()

        self.assertEqual(
            events,
            ["lock", "recover-jobs", "recover-mail", "serve", "close", "unlock"],
        )


if __name__ == "__main__":
    unittest.main()
