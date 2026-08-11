import unittest

from project_domain import (
    SECTION_KEYS,
    build_bpm_preflight,
    normalize_project_state,
    project_state_from_report,
    summarize_project_state,
)


def ready_sections():
    return [
        {
            "key": key,
            "title": title,
            "text": f"{title}已确认内容",
            "confirmed": True,
        }
        for key, title in SECTION_KEYS
    ]


def ready_scores():
    return [
        ["选题内容", 35, 30],
        ["作者情况", 10, 5],
        ["策划过程与可行性", 5, 4],
        ["获奖潜质", 5, 0],
        ["成本与盈利估算", 35, 18],
        ["市场定位与营销", 10, 8],
    ]


def ready_state():
    return {
        "sections": ready_sections(),
        "scoreItems": ready_scores(),
        "bpmTopic": {
            "bookName": "人工智能通识",
            "authorName": "王老师",
            "projectEditor": "张编辑",
            "editor": "张编辑",
            "class1": "02",
            "class2": "0201",
            "class3": "020101",
            "class4": "02010103",
            "gbClass": "G",
            "readLevel": "高等理工",
            "brief": "内容简介",
            "reader": "高校师生",
            "feature": "人工修订后的选题特色",
            "compare": "同类选题比较",
        },
        "authorMaintenance": {"name": "王老师", "bio": "王老师简介"},
        "fieldSources": {
            "bpmTopic.bookName": "application",
            "bpmTopic.authorName": "application",
            "bpmTopic.class1": "fixed",
            "bpmTopic.class3": "model",
            "bpmTopic.feature": "user",
            "bpmTopic.compare": "report",
            "bpmTopic.projectEditor": "bpm_profile",
        },
        "sourceFiles": {},
        "docxExported": False,
    }


class ProjectStateTests(unittest.TestCase):
    def test_normalizes_sections_and_removes_sensitive_nested_keys(self):
        normalized = normalize_project_state(
            {
                "sections": [
                    {"key": "marketing", "text": "营销", "confirmed": True},
                    {"key": "unknown", "text": "不应保留"},
                    {"key": "content", "text": "内容", "confirmed": False},
                ],
                "scoreItems": "invalid",
                "bpmTopic": {
                    "bookName": "测试选题",
                    "customField": "保留",
                    "apiKey": "sk-secret",
                    "nested": {"password": "secret", "safe": "value"},
                },
                "authorMaintenance": [],
                "unknownRoot": "drop-me",
            }
        )

        self.assertEqual([section["key"] for section in normalized["sections"]], [
            key for key, _ in SECTION_KEYS
        ])
        self.assertEqual(normalized["sections"][0]["text"], "内容")
        self.assertEqual(normalized["sections"][-1]["text"], "营销")
        self.assertEqual(normalized["scoreItems"], [])
        self.assertEqual(normalized["authorMaintenance"], {})
        self.assertEqual(normalized["bpmTopic"]["customField"], "保留")
        self.assertNotIn("apiKey", normalized["bpmTopic"])
        self.assertNotIn("password", normalized["bpmTopic"]["nested"])
        self.assertEqual(normalized["bpmTopic"]["nested"]["safe"], "value")
        self.assertNotIn("unknownRoot", normalized)

    def test_summary_uses_authenticated_editor_and_derives_statuses(self):
        summary = summarize_project_state(ready_state(), "服务端编辑")

        self.assertEqual(summary["title"], "人工智能通识")
        self.assertEqual(summary["authorName"], "王老师")
        self.assertEqual(summary["editorName"], "服务端编辑")
        self.assertEqual(summary["reportStatus"], "confirmed")
        self.assertEqual(summary["authorStatus"], "ready")
        self.assertEqual(summary["state"]["bpmTopic"]["projectEditor"], "服务端编辑")
        self.assertEqual(summary["state"]["bpmTopic"]["editor"], "服务端编辑")
        self.assertNotIn("projectEditorNo", summary["state"]["bpmTopic"])

    def test_report_result_becomes_canonical_project_state(self):
        state = project_state_from_report(
            {
                "title": "数据库原理",
                "sections": ready_sections(),
                "scores": ready_scores(),
                "bpmTopic": ready_state()["bpmTopic"],
                "authorMaintenance": {"name": "李老师", "bio": "作者简介"},
            },
            source_kind="generated",
        )

        self.assertEqual(state["bpmTopic"]["bookName"], "人工智能通识")
        self.assertEqual(len(state["sections"]), 6)
        self.assertEqual(state["fieldSources"]["bpmTopic.class1"], "fixed")
        self.assertEqual(state["fieldSources"]["bpmTopic.class3"], "model")
        self.assertEqual(state["fieldSources"]["sections.content"], "model")


class BpmPreflightTests(unittest.TestCase):
    def test_ready_project_exposes_values_sources_and_no_blockers(self):
        result = build_bpm_preflight(ready_state(), bpm_configured=True)

        self.assertTrue(result["ready"])
        self.assertEqual(result["blockingCount"], 0)
        self.assertEqual(
            {row["source"] for row in result["rows"]},
            {"application", "report", "fixed", "model", "user", "bpm_profile"},
        )
        self.assertTrue(all("value" in row for row in result["rows"]))
        self.assertEqual(
            next(row for row in result["rows"] if row["key"] == "scoreTotal")["value"],
            65,
        )

    def test_only_real_requirements_block_queueing(self):
        state = ready_state()
        state["sections"][2]["confirmed"] = False
        state["bpmTopic"]["compare"] = ""

        result = build_bpm_preflight(state, bpm_configured=False)

        self.assertFalse(result["ready"])
        blockers = {row["key"] for row in result["rows"] if row["status"] == "blocking_missing"}
        self.assertEqual(blockers, {"sections.feasibility", "bpmCredentials"})
        compare = next(row for row in result["rows"] if row["key"] == "bpmTopic.compare")
        self.assertEqual(compare["status"], "optional_missing")
        self.assertFalse(compare["required"])

    def test_invalid_score_total_blocks_even_when_sections_are_confirmed(self):
        state = ready_state()
        state["scoreItems"][0][2] = "not-a-number"

        result = build_bpm_preflight(state, bpm_configured=True)

        score = next(row for row in result["rows"] if row["key"] == "scoreTotal")
        self.assertEqual(score["status"], "blocking_missing")
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
