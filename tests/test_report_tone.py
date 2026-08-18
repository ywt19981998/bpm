import unittest
from unittest import mock

import server


class ReportToneTests(unittest.TestCase):
    def sample_result(self):
        return {
            "title": "示例选题",
            "sections": [
                {
                    "key": "content",
                    "title": "一、选题内容",
                    "text": "　　内容定位清晰，能够回应课程教学需求。",
                },
                {
                    "key": "author",
                    "title": "二、作者情况",
                    "text": "　　作者具有与选题相匹配的教学实践基础。",
                },
                {
                    "key": "feasibility",
                    "title": "三、策划过程与可行性",
                    "text": "　　建议责任编辑在组稿阶段进一步核实资源安排。",
                },
                {
                    "key": "award",
                    "title": "四、获奖潜质",
                    "text": "　　申报表中没有提供获奖记录。",
                },
                {
                    "key": "profit",
                    "title": "五、成本与盈利估算",
                    "text": server.FIXED_PROFIT_SECTION_TEXT,
                },
                {
                    "key": "marketing",
                    "title": "六、市场定位与营销",
                    "text": "　　本书可面向相关专业课程开展推广。",
                },
            ],
            "scores": [["选题内容", 35, 30]],
            "pending_questions": ["确认配套资源交付范围"],
        }

    def test_prompt_uses_leadership_approval_voice_and_omits_missing_facts(self):
        prompt = server.build_prompt({"canonical_fields": {"选题名称": "示例选题"}})

        self.assertIn("供出版社领导审议", prompt)
        self.assertIn("帮助领导判断是否批准立项", prompt)
        self.assertIn("某项信息缺失时，直接略去", prompt)
        self.assertIn("不得向责任编辑、策划编辑或作者布置工作", prompt)
        self.assertNotIn("待确认信息单独提供给编辑核对", prompt)

    def test_detector_flags_internal_advice_and_missing_information_narration(self):
        violations = server.find_report_tone_violations(self.sample_result())

        self.assertEqual({item["key"] for item in violations}, {"feasibility", "award"})
        self.assertTrue(any("建议责任编辑" in item["matches"] for item in violations))
        self.assertTrue(
            any(
                "申报表中没有" in match
                for item in violations
                for match in item["matches"]
            )
        )

    def test_rewriter_replaces_only_report_sections_and_preserves_editor_metadata(self):
        result = self.sample_result()
        rewritten = {
            "sections": [
                {
                    "key": "feasibility",
                    "title": "三、策划过程与可行性",
                    "text": "　　现有内容框架和资源安排能够支撑书稿顺利完成。",
                },
                {
                    "key": "award",
                    "title": "四、获奖潜质",
                    "text": "　　选题在课程应用和数字资源建设方面具有成果培育空间。",
                },
            ]
        }

        with mock.patch.object(server, "call_complete_report_model", return_value=rewritten) as model:
            revised = server.revise_report_tone_if_needed(
                {"canonical_fields": {"选题名称": "示例选题"}}, result
            )

        section_map = {section["key"]: section for section in revised["sections"]}
        self.assertIn("能够支撑书稿顺利完成", section_map["feasibility"]["text"])
        self.assertEqual(section_map["profit"]["text"], server.FIXED_PROFIT_SECTION_TEXT)
        self.assertEqual(revised["pending_questions"], result["pending_questions"])
        model.assert_called_once()

    def test_rewriter_skips_the_model_when_sections_already_match_the_tone(self):
        result = self.sample_result()
        for section in result["sections"]:
            if section["key"] == "feasibility":
                section["text"] = "　　现有内容框架能够支撑书稿按计划完成。"
            if section["key"] == "award":
                section["text"] = "　　选题具有课程应用和数字资源建设潜力。"

        with mock.patch.object(server, "call_complete_report_model") as model:
            revised = server.revise_report_tone_if_needed({}, result)

        self.assertEqual(revised, result)
        model.assert_not_called()


if __name__ == "__main__":
    unittest.main()
