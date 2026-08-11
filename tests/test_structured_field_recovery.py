import unittest
from unittest import mock

import server


def complete_facts():
    return {
        "canonical_fields": {
            "选题名称": "工业自动化项目式教程",
            "姓名": "朱万浩",
        },
        "application_fields": {},
        "table_rows": [],
        "safe_table_rows": [],
    }


class StructuredFieldRecoveryTests(unittest.TestCase):
    def test_complete_native_fields_skip_fast_model(self):
        facts = complete_facts()

        with mock.patch.object(server, "call_fast_model") as call:
            recovered = server.recover_missing_structured_fields(facts)

        call.assert_not_called()
        self.assertEqual(recovered["canonical_fields"], facts["canonical_fields"])

    def test_missing_fields_are_recovered_once_when_grounded_in_safe_rows(self):
        facts = {
            "canonical_fields": {},
            "application_fields": {},
            "table_rows": [{"cells": ["身份证号", "110101199001011234"]}],
            "safe_table_rows": [
                {"cells": ["选题名", "工业自动化项目式教程"]},
                {"cells": ["姓 名", "朱万浩"]},
                {"cells": ["身份证号", "[已隐藏]"]},
            ],
        }
        response = {
            "fields": {
                "bookName": {"value": "工业自动化项目式教程", "evidence": "选题名"},
                "authorName": {"value": "朱万浩", "evidence": "姓 名"},
            }
        }

        with mock.patch.object(server, "call_fast_model", return_value=response) as call:
            recovered = server.recover_missing_structured_fields(facts)

        call.assert_called_once()
        self.assertNotIn("110101199001011234", call.call_args.args[0])
        self.assertEqual(recovered["canonical_fields"]["选题名称"], "工业自动化项目式教程")
        self.assertEqual(recovered["canonical_fields"]["姓名"], "朱万浩")
        self.assertEqual(recovered["recovered_fields"], {
            "选题名称": "model_grounded",
            "姓名": "model_grounded",
        })

    def test_unseen_model_values_are_rejected(self):
        facts = {
            "canonical_fields": {},
            "application_fields": {},
            "table_rows": [],
            "safe_table_rows": [{"cells": ["选题名", "工业自动化项目式教程"]}],
        }
        response = {
            "fields": {
                "bookName": {"value": "模型臆造书名", "evidence": ""},
                "authorName": {"value": "李四", "evidence": ""},
            }
        }

        with mock.patch.object(server, "call_fast_model", return_value=response):
            recovered = server.recover_missing_structured_fields(facts)

        self.assertNotIn("选题名称", recovered["canonical_fields"])
        self.assertNotIn("姓名", recovered["canonical_fields"])

    def test_fast_model_service_failure_does_not_block_report_generation(self):
        facts = {
            "canonical_fields": {},
            "application_fields": {},
            "table_rows": [],
            "safe_table_rows": [{"cells": ["其他字段", "其他内容"]}],
        }

        with (
            mock.patch.object(
                server,
                "call_fast_model",
                side_effect=server.ModelServiceError("temporary failure"),
            ),
            mock.patch.object(server, "runtime_log") as log,
        ):
            recovered = server.recover_missing_structured_fields(facts)

        self.assertEqual(recovered["canonical_fields"], {})
        self.assertIn("选题名称", log.call_args.args[0])
        self.assertNotIn("其他内容", log.call_args.args[0])

    def test_application_title_overrides_a_different_report_model_title(self):
        class Extractor:
            def build_payload(self, *_args, **_kwargs):
                return complete_facts()

        model_result = {"title": "工业自动化教材选题（书名待定）", "sections": [], "scores": []}
        with (
            mock.patch.object(server, "load_extractor", return_value=Extractor()),
            mock.patch.object(server, "call_complete_report_model", return_value=model_result),
        ):
            generated = server.generate_report_from_upload(b"test", "application.docx")

        self.assertEqual(generated["title"], "工业自动化项目式教程")
        self.assertEqual(generated["bpmTopic"]["bookName"], "工业自动化项目式教程")


if __name__ == "__main__":
    unittest.main()
