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


if __name__ == "__main__":
    unittest.main()
