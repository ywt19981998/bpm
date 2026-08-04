import http.client
import json
import tempfile
import threading
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
