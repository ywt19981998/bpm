import tempfile
import unittest
from pathlib import Path

from app_storage import AppStore


class MailTemplateStorageTests(unittest.TestCase):
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

    def test_template_crud_is_user_scoped(self):
        created = self.store.create_mail_template(
            self.user_id, "教材主编邀请", "主题 {{姓名}}", "{{姓名}}老师，您好"
        )
        self.assertEqual(
            set(created),
            {"id", "name", "subject", "body", "createdAt", "updatedAt", "lastUsedAt"},
        )
        self.assertIsInstance(created["createdAt"], str)
        self.assertIsInstance(created["updatedAt"], str)
        self.assertIsNone(created["lastUsedAt"])

        templates = self.store.list_mail_templates(self.user_id)
        self.assertEqual(len(templates), 1)
        self.assertEqual(templates[0], created)
        self.assertEqual(self.store.list_mail_templates(self.other_user_id), [])

        updated = self.store.update_mail_template(
            self.user_id, created["id"], "主编邀请", "新主题", "新正文"
        )
        self.assertEqual(updated["name"], "主编邀请")
        self.assertEqual(updated["subject"], "新主题")
        self.assertEqual(updated["body"], "新正文")
        self.assertIsInstance(updated["createdAt"], str)
        self.assertIsInstance(updated["updatedAt"], str)
        self.assertIsNone(updated["lastUsedAt"])
        self.assertIsNone(
            self.store.update_mail_template(
                self.other_user_id, created["id"], "越权", "越权", "越权"
            )
        )
        self.assertFalse(self.store.delete_mail_template(self.other_user_id, created["id"]))
        self.assertTrue(self.store.delete_mail_template(self.user_id, created["id"]))
        self.assertEqual(self.store.list_mail_templates(self.user_id), [])

    def test_default_templates_are_initialized_only_once(self):
        defaults = [
            {"name": "邀请", "subject": "邀请 {{姓名}}", "body": "{{姓名}}老师，您好"},
            {"name": "提醒", "subject": "提醒 {{姓名}}", "body": "请查看附件"},
        ]

        first = self.store.ensure_default_mail_templates(self.user_id, defaults)
        second = self.store.ensure_default_mail_templates(self.user_id, defaults)

        self.assertEqual([template["name"] for template in first], ["邀请", "提醒"])
        self.assertEqual([template["name"] for template in second], ["邀请", "提醒"])
        self.assertEqual(len(self.store.list_mail_templates(self.user_id)), 2)
        self.assertEqual(self.store.list_mail_templates(self.other_user_id), [])

        for template in first:
            self.assertTrue(self.store.delete_mail_template(self.user_id, template["id"]))
        self.assertEqual(self.store.list_mail_templates(self.user_id), [])
        self.assertEqual(self.store.ensure_default_mail_templates(self.user_id, defaults), [])

    def test_touch_mail_template_is_user_scoped_and_updates_last_used_at(self):
        template = self.store.create_mail_template(
            self.user_id, "教材主编邀请", "主题 {{姓名}}", "{{姓名}}老师，您好"
        )

        self.assertIsNone(
            self.store.touch_mail_template(self.other_user_id, template["id"])
        )
        touched = self.store.touch_mail_template(self.user_id, template["id"])

        self.assertEqual(touched["id"], template["id"])
        self.assertIsInstance(touched["lastUsedAt"], str)
        self.assertEqual(self.store.list_mail_templates(self.user_id), [touched])

    def test_default_templates_do_not_mix_with_existing_user_templates(self):
        created = self.store.create_mail_template(
            self.user_id, "自建模板", "自建主题", "自建正文"
        )
        defaults = [{"name": "邀请", "subject": "邀请 {{姓名}}", "body": "您好"}]

        self.assertEqual(
            self.store.ensure_default_mail_templates(self.user_id, defaults), [created]
        )

    def test_mail_draft_persists_across_reopen_and_is_user_scoped(self):
        template = self.store.create_mail_template(
            self.user_id, "教材主编邀请", "主题 {{姓名}}", "{{姓名}}老师，您好"
        )
        payload = {
            "templateId": template["id"],
            "subject": "教材主编邀请",
            "body": "王老师，您好",
            "recipients": [
                {"name": "王老师", "email": "wang@example.com"},
                {"name": "李老师", "email": "li@example.com"},
            ],
        }

        self.assertIsNone(self.store.get_mail_draft(self.user_id))
        self.store.put_mail_draft(self.user_id, payload)

        reopened = AppStore(self.db_path)
        self.assertEqual(reopened.get_mail_draft(self.user_id), payload)
        self.assertIsNone(reopened.get_mail_draft(self.other_user_id))


class MailBatchStorageTests(unittest.TestCase):
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

    @staticmethod
    def _deliveries():
        return [
            {
                "name": "张三",
                "email": "a@example.com",
                "subject": "合作邀请",
                "body": "张三老师，您好",
            },
            {
                "name": "李四",
                "email": "b@example.com",
                "subject": "合作邀请",
                "body": "李四老师，您好",
            },
        ]

    def test_batch_rolls_up_partial_failure(self):
        batch = self.store.create_mail_batch(
            self.user_id,
            "合作邀请",
            "{{姓名}}老师，您好",
            self._deliveries(),
        )
        first, second = batch["deliveries"]
        self.store.start_mail_batch(self.user_id, batch["id"])
        self.store.update_mail_delivery(self.user_id, batch["id"], first["id"], "sending")
        self.store.update_mail_delivery(self.user_id, batch["id"], first["id"], "succeeded")
        self.store.update_mail_delivery(self.user_id, batch["id"], second["id"], "sending")
        self.store.update_mail_delivery(
            self.user_id, batch["id"], second["id"], "failed", "连接中断"
        )

        finished = self.store.finish_mail_batch(self.user_id, batch["id"])

        self.assertEqual(finished["status"], "partial_failed")
        self.assertEqual(finished["totalCount"], 2)
        self.assertEqual(finished["sentCount"], 1)
        self.assertEqual(finished["failedCount"], 1)
        self.assertEqual(finished["deliveries"][1]["errorSummary"], "连接中断")

    def test_batch_is_user_scoped_and_lists_newest_first(self):
        first = self.store.create_mail_batch(
            self.user_id, "第一封", "正文", self._deliveries()[:1]
        )
        second = self.store.create_mail_batch(
            self.user_id, "第二封", "正文", self._deliveries()[1:]
        )

        self.assertIsNone(self.store.get_mail_batch(self.other_user_id, first["id"]))
        self.assertEqual(self.store.list_mail_batches(self.other_user_id), [])
        self.assertEqual(
            [batch["id"] for batch in self.store.list_mail_batches(self.user_id)],
            [second["id"], first["id"]],
        )
        self.assertEqual(self.store.list_mail_batches(self.user_id, limit=1), [
            self.store.get_mail_batch(self.user_id, second["id"])
        ])

    def test_retry_copies_only_failed_deliveries(self):
        original = self.store.create_mail_batch(
            self.user_id, "合作邀请", "{{姓名}}老师，您好", self._deliveries()
        )
        succeeded, failed = original["deliveries"]
        self.store.start_mail_batch(self.user_id, original["id"])
        self.store.update_mail_delivery(
            self.user_id, original["id"], succeeded["id"], "sending"
        )
        self.store.update_mail_delivery(
            self.user_id, original["id"], succeeded["id"], "succeeded"
        )
        self.store.update_mail_delivery(
            self.user_id, original["id"], failed["id"], "sending"
        )
        self.store.update_mail_delivery(
            self.user_id, original["id"], failed["id"], "failed", "连接中断"
        )
        self.store.finish_mail_batch(self.user_id, original["id"])

        retry = self.store.create_retry_mail_batch(self.user_id, original["id"])

        self.assertNotEqual(retry["id"], original["id"])
        self.assertEqual(retry["status"], "queued")
        self.assertEqual(retry["totalCount"], 1)
        self.assertEqual(retry["deliveries"][0]["name"], "李四")
        self.assertEqual(retry["deliveries"][0]["email"], "b@example.com")
        self.assertEqual(retry["deliveries"][0]["status"], "queued")
        self.assertEqual(retry["deliveries"][0]["errorSummary"], None)
        self.assertEqual(
            self.store.get_mail_batch(self.user_id, original["id"])["status"],
            "partial_failed",
        )

    def test_retry_requires_a_failed_delivery(self):
        batch = self.store.create_mail_batch(
            self.user_id, "合作邀请", "正文", self._deliveries()[:1]
        )

        with self.assertRaisesRegex(ValueError, "没有可重试的失败邮件"):
            self.store.create_retry_mail_batch(self.user_id, batch["id"])

    def test_start_and_delivery_status_are_user_scoped(self):
        batch = self.store.create_mail_batch(
            self.user_id, "合作邀请", "正文", self._deliveries()[:1]
        )

        self.assertIsNone(self.store.start_mail_batch(self.other_user_id, batch["id"]))
        self.assertIsNone(
            self.store.update_mail_delivery(
                self.other_user_id, batch["id"], batch["deliveries"][0]["id"], "sending"
            )
        )
        started = self.store.start_mail_batch(self.user_id, batch["id"])
        self.assertEqual(started["status"], "running")
        self.store.update_mail_delivery(
            self.user_id, batch["id"], batch["deliveries"][0]["id"], "sending"
        )
        self.store.update_mail_delivery(
            self.user_id, batch["id"], batch["deliveries"][0]["id"], "succeeded"
        )
        finished = self.store.finish_mail_batch(self.user_id, batch["id"])
        self.assertEqual(finished["status"], "succeeded")

    def test_start_is_an_atomic_one_time_claim(self):
        batch = self.store.create_mail_batch(
            self.user_id, "合作邀请", "正文", self._deliveries()[:1]
        )

        first_claim = self.store.start_mail_batch(self.user_id, batch["id"])
        second_claim = self.store.start_mail_batch(self.user_id, batch["id"])

        self.assertEqual(first_claim["status"], "running")
        self.assertIsNone(second_claim)
        self.assertEqual(
            self.store.get_mail_batch(self.user_id, batch["id"])["status"], "running"
        )

    def test_delivery_state_machine_blocks_terminal_rollbacks(self):
        batch = self.store.create_mail_batch(
            self.user_id, "合作邀请", "正文", self._deliveries()[:1]
        )
        delivery = batch["deliveries"][0]

        self.store.update_mail_delivery(
            self.user_id, batch["id"], delivery["id"], "sending"
        )
        self.assertEqual(
            self.store.get_mail_batch(self.user_id, batch["id"])["deliveries"][0]["status"],
            "queued",
        )

        self.store.start_mail_batch(self.user_id, batch["id"])
        self.store.update_mail_delivery(
            self.user_id, batch["id"], delivery["id"], "sending"
        )
        self.store.update_mail_delivery(
            self.user_id, batch["id"], delivery["id"], "succeeded"
        )
        self.store.update_mail_delivery(
            self.user_id, batch["id"], delivery["id"], "failed", "should be ignored"
        )
        finished = self.store.finish_mail_batch(self.user_id, batch["id"])
        self.store.update_mail_delivery(
            self.user_id, batch["id"], delivery["id"], "sending"
        )
        finished_again = self.store.finish_mail_batch(self.user_id, batch["id"])

        self.assertEqual(finished["status"], "succeeded")
        self.assertIsNone(finished_again)
        final = self.store.get_mail_batch(self.user_id, batch["id"])
        self.assertEqual(final["status"], "succeeded")
        self.assertEqual(final["deliveries"][0]["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
