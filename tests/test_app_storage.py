import base64
import inspect
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path

from app_storage import AppStore, CredentialConfigurationError, ProjectVersionConflict


class AppStoreAuthTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "app.db"
        self.store = AppStore(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def database_text(self):
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                "SELECT username, password_hash, display_name FROM users"
            ).fetchall()
        return " ".join(str(value) for row in rows for value in row)

    def test_register_authenticate_and_session_round_trip(self):
        user = self.store.register_user(" Editor01 ", "S3cure-pass", "张编辑")
        self.assertEqual(user["username"], "editor01")
        self.assertEqual(user["display_name"], "张编辑")
        self.assertNotIn("S3cure-pass", self.database_text())
        self.assertEqual(
            self.store.authenticate_user("EDITOR01", "S3cure-pass")["id"],
            user["id"],
        )
        self.assertIsNone(self.store.authenticate_user("editor01", "wrong-pass"))
        token = self.store.create_session(user["id"], ttl_seconds=3600)
        self.assertEqual(self.store.get_user_for_session(token)["id"], user["id"])
        self.store.delete_session(token)
        self.assertIsNone(self.store.get_user_for_session(token))

    def test_duplicate_usernames_are_normalized_and_rejected(self):
        self.store.register_user("Editor01", "S3cure-pass", "张编辑")
        with self.assertRaises(ValueError):
            self.store.register_user(" editor01 ", "another-pass", "另一位编辑")

    def test_registration_validates_username_password_and_display_name(self):
        invalid_users = ["ab", "a" * 41, "not valid"]
        for username in invalid_users:
            with self.subTest(username=username):
                with self.assertRaises(ValueError):
                    self.store.register_user(username, "S3cure-pass", "编辑")
        with self.assertRaises(ValueError):
            self.store.register_user("editor02", "short", "编辑")
        with self.assertRaises(ValueError):
            self.store.register_user("editor02", "S3cure-pass", " ")

    def test_session_token_is_hashed_in_database(self):
        user = self.store.register_user("editor01", "S3cure-pass", "张编辑")
        token = self.store.create_session(user["id"])
        with sqlite3.connect(self.db_path) as connection:
            stored_token = connection.execute(
                "SELECT token_hash FROM sessions"
            ).fetchone()[0]
        self.assertNotEqual(stored_token, token)
        self.assertEqual(len(stored_token), 64)
        self.assertNotIn(token, self.db_path.read_bytes().decode("utf-8", "ignore"))

    def test_token_with_unicode_suffix_does_not_resolve(self):
        user = self.store.register_user("editor01", "S3cure-pass", "张编辑")
        token = self.store.create_session(user["id"])
        self.assertIsNone(self.store.get_user_for_session(token + "中文"))


class AppStoreCredentialTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "app.db"
        self.key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        self.store = AppStore(self.db_path, credential_key=self.key)
        self.user_id = self.store.register_user("editor01", "S3cure-pass", "张编辑")["id"]
        self.other_user_id = self.store.register_user(
            "editor02", "S3cure-pass", "另一位编辑"
        )["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def database_text(self):
        database_files = [self.db_path]
        wal_path = Path(f"{self.db_path}-wal")
        if wal_path.exists():
            database_files.append(wal_path)
        return b"".join(path.read_bytes() for path in database_files).decode(
            "utf-8", "ignore"
        )

    def stored_credential_bytes(self):
        with sqlite3.connect(self.db_path) as connection:
            return connection.execute(
                "SELECT nonce, ciphertext FROM integration_credentials "
                "WHERE user_id = ? AND system_type = ?",
                (self.user_id, "phei_bpm"),
            ).fetchone()

    def test_credentials_are_encrypted_and_isolated(self):
        self.store.put_integration_credentials(self.user_id, "phei_bpm", "yewt", "bpm-secret")
        self.assertNotIn("yewt", self.database_text())
        self.assertNotIn("bpm-secret", self.database_text())
        self.assertEqual(
            self.store.get_integration_credentials(self.user_id, "phei_bpm"),
            {"account": "yewt", "password": "bpm-secret"},
        )
        self.assertIsNone(
            self.store.get_integration_credentials(self.other_user_id, "phei_bpm")
        )
        self.assertEqual(
            self.store.get_integration_status(self.user_id, "phei_bpm"),
            {"configured": True, "accountMasked": "y***t"},
        )
        self.store.delete_integration_credentials(self.user_id, "phei_bpm")
        self.assertIsNone(
            self.store.get_integration_credentials(self.user_id, "phei_bpm")
        )
        self.assertEqual(
            self.store.get_integration_status(self.user_id, "phei_bpm"),
            {"configured": False, "accountMasked": None},
        )

    def test_missing_or_wrong_key_raises(self):
        self.store.put_integration_credentials(self.user_id, "phei_bpm", "yewt", "bpm-secret")
        wrong_store = AppStore(
            self.db_path,
            credential_key=base64.urlsafe_b64encode(os.urandom(32)).decode("ascii"),
        )
        with self.assertRaises(CredentialConfigurationError):
            wrong_store.get_integration_credentials(self.user_id, "phei_bpm")
        missing_store = AppStore(self.db_path)
        with self.assertRaises(CredentialConfigurationError):
            missing_store.get_integration_credentials(self.user_id, "phei_bpm")

    def test_updating_credentials_changes_nonce_and_ciphertext(self):
        self.store.put_integration_credentials(self.user_id, "phei_bpm", "yewt", "bpm-secret")
        first_nonce, first_ciphertext = self.stored_credential_bytes()

        self.store.put_integration_credentials(
            self.user_id, "phei_bpm", "updated-account", "updated-secret"
        )
        second_nonce, second_ciphertext = self.stored_credential_bytes()

        self.assertNotEqual(first_nonce, second_nonce)
        self.assertNotEqual(first_ciphertext, second_ciphertext)
        self.assertEqual(
            self.store.get_integration_credentials(self.user_id, "phei_bpm"),
            {"account": "updated-account", "password": "updated-secret"},
        )

    def test_changing_user_id_breaks_authenticated_decryption(self):
        self.store.put_integration_credentials(self.user_id, "phei_bpm", "yewt", "bpm-secret")
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "UPDATE integration_credentials SET user_id = ? "
                "WHERE user_id = ? AND system_type = ?",
                (self.other_user_id, self.user_id, "phei_bpm"),
            )

        with self.assertRaises(CredentialConfigurationError):
            self.store.get_integration_credentials(self.other_user_id, "phei_bpm")


class AppStoreJobTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "app.db"
        self.key = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
        self.store = AppStore(self.db_path, credential_key=self.key)
        self.user_id = self.store.register_user("editor01", "S3cure-pass", "张编辑")["id"]
        self.other_user_id = self.store.register_user(
            "editor02", "S3cure-pass", "李编辑"
        )["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def database_text(self):
        database_files = [self.db_path]
        wal_path = Path(f"{self.db_path}-wal")
        if wal_path.exists():
            database_files.append(wal_path)
        return b"".join(path.read_bytes() for path in database_files).decode(
            "utf-8", "ignore"
        )

    def test_jobs_persist_status_logs_and_results_without_bpm_passwords(self):
        self.store.put_integration_credentials(
            self.user_id, "phei_bpm", "job-account", "test-bpm-password"
        )
        job = self.store.create_job(
            self.user_id,
            "topic",
            "测试选题",
            {"createdBy": "张编辑", "topicPreview": {"bookName": "测试选题"}},
        )
        self.store.update_job(job["id"], self.user_id, "running")
        self.store.append_job_log(job["id"], self.user_id, "开始填报")
        self.store.update_job(
            job["id"], self.user_id, "succeeded", result={"cno": "XT20260001"}
        )
        failed = self.store.create_job(
            self.user_id, "author", "测试作者", {"createdBy": "张编辑"}
        )
        self.store.update_job(failed["id"], self.user_id, "running")
        self.store.update_job(
            failed["id"], self.user_id, "failed", error_summary="BPM 登录失败"
        )
        self.store.create_job(
            self.other_user_id, "topic", "另一用户选题", {"createdBy": "李编辑"}
        )
        redacted = self.store.create_job(
            self.user_id,
            "topic",
            "不能持久化可信载荷",
            {"bpm": {"password": "test-bpm-password"}},
        )
        self.assertEqual(redacted["bpm"]["password"], "[REDACTED]")

        reopened = AppStore(self.db_path, self.key)
        jobs = reopened.list_jobs(self.user_id)
        self.assertEqual(
            {item["status"] for item in jobs if item["id"] in {job["id"], failed["id"]}},
            {"succeeded", "failed"},
        )
        persisted = next(item for item in jobs if item["id"] == job["id"])
        self.assertEqual(persisted["status"], "succeeded")
        self.assertEqual(persisted["createdBy"], "张编辑")
        self.assertEqual(persisted["topicPreview"], {"bookName": "测试选题"})
        self.assertEqual(persisted["logs"], ["开始填报"])
        self.assertEqual(persisted["result"], {"cno": "XT20260001"})
        self.assertIsNone(persisted["error"])
        self.assertTrue(persisted["createdAt"])
        self.assertTrue(persisted["updatedAt"])
        self.assertEqual(reopened.list_jobs(self.other_user_id)[0]["title"], "另一用户选题")
        self.assertNotIn("test-bpm-password", self.database_text())

    def test_job_writes_are_limited_to_the_owning_user(self):
        job = self.store.create_job(self.user_id, "topic", "测试选题", {})
        self.store.update_job(job["id"], self.other_user_id, "running")
        self.store.append_job_log(job["id"], self.other_user_id, "越权日志")
        self.assertEqual(self.store.list_jobs(self.user_id)[0]["status"], "queued")
        self.assertEqual(self.store.list_jobs(self.user_id)[0]["logs"], [])

    def test_mark_interrupted_jobs_failed_atomically(self):
        queued = self.store.create_job(self.user_id, "topic", "排队任务", {})
        running = self.store.create_job(self.user_id, "author", "执行中任务", {})
        completed = self.store.create_job(self.user_id, "topic", "完成任务", {})
        self.store.update_job(running["id"], self.user_id, "running")
        self.store.update_job(completed["id"], self.user_id, "succeeded", result={"ok": True})

        changed = self.store.mark_interrupted_jobs_failed()

        self.assertEqual(changed, 2)
        jobs = {job["id"]: job for job in self.store.list_jobs(self.user_id)}
        for job_id in (queued["id"], running["id"]):
            self.assertEqual(jobs[job_id]["status"], "failed")
            self.assertEqual(
                jobs[job_id]["error"],
                "服务重启，任务执行状态不确定，请先在 BPM 人工核对后再重试",
            )
        self.assertEqual(jobs[completed["id"]]["status"], "succeeded")

    def test_job_storage_redacts_sensitive_payload_results_errors_and_logs(self):
        secrets_to_scan = {
            "test-bpm-password",
            "deepseek-api-key",
            "api-key-value",
            "authorization-value",
            "token-value",
            "secret-value",
            "Bearer bearer-value",
            "bearer-value",
            "bearer-spaced-value",
            "sk-test-key-value",
        }
        job = self.store.create_job(
            self.user_id,
            "topic",
            "脱敏测试",
            {
                "bpm": {"password": "test-bpm-password"},
                "api_key": "deepseek-api-key",
                "apiKey": "api-key-value",
                "authorization": "authorization-value",
                "token": "token-value",
                "secret": "secret-value",
                "message": (
                    "Authorization: Bearer bearer-value sk-test-key-value; "
                    "aUtHoRiZaTiOn :    bEaReR bearer-spaced-value"
                ),
            },
        )
        self.store.update_job(
            job["id"],
            self.user_id,
            "succeeded",
            result={
                "password": "test-bpm-password",
                "detail": "Bearer bearer-value sk-test-key-value",
            },
            error_summary="BPM password: test-bpm-password; apiKey=api-key-value",
        )
        self.store.append_job_log(
            job["id"],
            self.user_id,
            "token=token-value Authorization: Bearer bearer-value sk-test-key-value",
        )

        persisted = self.store.list_jobs(self.user_id)[0]
        self.assertIn("[REDACTED]", json.dumps(persisted, ensure_ascii=False))
        for secret in secrets_to_scan:
            self.assertNotIn(secret, self.database_text())

    def test_create_job_reads_the_new_record_with_its_owner(self):
        source = inspect.getsource(AppStore.create_job)
        self.assertIn("WHERE id = ? AND user_id = ?", source)


class AppStoreProjectTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "app.db"
        self.store = AppStore(self.db_path)
        self.user_id = self.store.register_user(
            "editor01", "S3cure-pass", "张编辑"
        )["id"]
        self.other_user_id = self.store.register_user(
            "editor02", "S3cure-pass", "李编辑"
        )["id"]

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_project_round_trip_is_versioned_and_owner_scoped(self):
        project = self.store.create_project(
            self.user_id,
            "测试选题",
            {"sections": [{"key": "content", "text": "草稿", "confirmed": False}]},
            author_name="王老师",
            editor_name="张编辑",
        )

        self.assertEqual(project["version"], 1)
        self.assertEqual(project["title"], "测试选题")
        self.assertEqual(project["authorName"], "王老师")
        self.assertEqual(project["reportStatus"], "empty")
        self.assertIsNone(self.store.get_project(self.other_user_id, project["id"]))

        updated = self.store.update_project(
            self.user_id,
            project["id"],
            1,
            {
                "title": "修订选题",
                "report_status": "draft",
                "state": {"sections": [{"key": "content", "text": "修订稿"}]},
            },
        )

        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["title"], "修订选题")
        self.assertEqual(updated["state"]["sections"][0]["text"], "修订稿")
        with self.assertRaises(ProjectVersionConflict):
            self.store.update_project(
                self.user_id, project["id"], 1, {"title": "过期内容"}
            )
        self.assertIsNone(
            self.store.update_project(
                self.other_user_id,
                project["id"],
                2,
                {"title": "越权修改"},
            )
        )

    def test_project_list_filters_searches_and_archives(self):
        first = self.store.create_project(
            self.user_id,
            "人工智能通识",
            report_status="draft",
            bpm_status="not_ready",
        )
        second = self.store.create_project(
            self.user_id,
            "数据库原理",
            report_status="confirmed",
            bpm_status="ready",
        )
        self.store.create_project(
            self.other_user_id,
            "其他用户项目",
            report_status="confirmed",
        )

        self.assertEqual(
            [item["id"] for item in self.store.list_projects(self.user_id)],
            [second["id"], first["id"]],
        )
        self.assertEqual(
            [item["id"] for item in self.store.list_projects(self.user_id, query="数据库")],
            [second["id"]],
        )
        self.assertEqual(
            [
                item["id"]
                for item in self.store.list_projects(
                    self.user_id, status="confirmed"
                )
            ],
            [second["id"]],
        )

        archived = self.store.archive_project(
            self.user_id, second["id"], second["version"]
        )
        self.assertIsNotNone(archived["archivedAt"])
        self.assertEqual(
            [item["id"] for item in self.store.list_projects(self.user_id)],
            [first["id"]],
        )
        self.assertEqual(
            {item["id"] for item in self.store.list_projects(self.user_id, include_archived=True)},
            {first["id"], second["id"]},
        )

    def test_project_revision_is_written_only_for_explicit_checkpoint(self):
        project = self.store.create_project(self.user_id, "版本测试", {"value": 1})
        self.store.update_project(
            self.user_id,
            project["id"],
            project["version"],
            {"state": {"value": 2}},
        )
        self.assertEqual(self.store.list_project_revisions(self.user_id, project["id"]), [])

        current = self.store.get_project(self.user_id, project["id"])
        self.store.update_project(
            self.user_id,
            project["id"],
            current["version"],
            {"state": {"value": 3}},
            revision_reason="report_confirmed",
        )
        revisions = self.store.list_project_revisions(self.user_id, project["id"])
        self.assertEqual(len(revisions), 1)
        self.assertEqual(revisions[0]["reason"], "report_confirmed")
        self.assertEqual(revisions[0]["snapshot"]["state"], {"value": 3})

    def test_project_file_metadata_and_jobs_are_linked_to_owner(self):
        project = self.store.create_project(self.user_id, "文件测试")
        file_record = self.store.add_project_file(
            self.user_id,
            project["id"],
            "file-id",
            "application",
            "申报表.docx",
            "1/project/file-id.docx",
            "a" * 64,
            1024,
        )

        self.assertEqual(file_record["kind"], "application")
        self.assertEqual(
            self.store.get_project_file(
                self.user_id, project["id"], file_record["id"]
            )["originalName"],
            "申报表.docx",
        )
        self.assertIsNone(
            self.store.get_project_file(
                self.other_user_id, project["id"], file_record["id"]
            )
        )
        self.assertEqual(
            self.store.list_project_files(self.user_id, project["id"])[0]["sha256"],
            "a" * 64,
        )

        job = self.store.create_job(
            self.user_id,
            "topic",
            "文件测试",
            {"createdBy": "张编辑"},
            project_id=project["id"],
        )
        self.assertEqual(job["projectId"], project["id"])
        with self.assertRaises(ValueError):
            self.store.create_job(
                self.other_user_id,
                "topic",
                "越权项目",
                {},
                project_id=project["id"],
            )


if __name__ == "__main__":
    unittest.main()
