import unittest
from unittest import mock

import server


class BpmContentGenerationTests(unittest.TestCase):
    def test_parse_exa_search_output_keeps_title_url_and_highlights(self):
        output = """Title: 新能源发电功率预测_科学出版社官网
URL: https://www.ecsponline.com/goods.php?id=205264
Published: N/A
Author: N/A
Highlights:
书号：9787030651587 作者：王飞等 出版社：科学出版社 目录：风电、光伏预测。

---

Title: 光伏发电功率预测技术及应用
URL: https://www.dushu.com/book/13734244/
Highlights:
作者王伟胜等，中国电力出版社，包含数值天气预报与预测系统。
"""

        results = server.parse_exa_search_output(output)

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]["url"], "https://www.ecsponline.com/goods.php?id=205264")
        self.assertIn("科学出版社", results[0]["excerpt"])

    def test_prompt_requests_all_four_dedicated_bpm_fields_and_two_verified_books(self):
        with mock.patch.object(
            server,
            "book_comparison_search_context",
            return_value=[
                {
                    "title": "新能源发电功率预测",
                    "url": "https://example.com/book-1",
                    "excerpt": "风电与光伏发电功率预测",
                },
                {
                    "title": "光伏发电功率预测技术及应用",
                    "url": "https://example.com/book-2",
                    "excerpt": "光伏预测与工程应用",
                },
            ],
        ):
            prompt = server.build_prompt(
                {"canonical_fields": {"选题名称": "新能源功率预测应用技术"}}
            )

        self.assertIn("bpmFields.brief", prompt)
        self.assertIn("bpmFields.reader", prompt)
        self.assertIn("恰好选择 2 本", prompt)
        self.assertIn("compareSources", prompt)
        self.assertIn("https://example.com/book-1", prompt)

    def test_normalize_generated_preserves_bpm_fields_and_two_sources(self):
        result = server.normalize_generated(
            {
                "title": "新能源功率预测应用技术",
                "sections": [],
                "scores": [],
                "bpmFields": {
                    "brief": "内容简介",
                    "reader": "大学相关专业本科生、研究生，以及相关工作人员。",
                    "feature": "选题特色",
                    "compare": "两本同类书比较",
                    "compareSources": [
                        {"title": "书一", "url": "https://example.com/1"},
                        {"title": "书一 - 读书网", "url": "https://example.com/duplicate"},
                        {"title": "书二", "url": "https://example.com/2"},
                    ],
                },
            }
        )

        fields = result["bpmFields"]
        self.assertEqual(fields["brief"], "内容简介")
        self.assertEqual(fields["reader"], "大学相关专业本科生、研究生，以及相关工作人员。")
        self.assertEqual(fields["feature"], "选题特色")
        self.assertEqual(fields["compare"], "两本同类书比较")
        self.assertEqual(len(fields["compareSources"]), 2)
        self.assertEqual([item["title"] for item in fields["compareSources"]], ["书一", "书二"])

    def test_build_bpm_topic_prefers_dedicated_fields_over_report_sections(self):
        result = {
            "title": "新能源功率预测应用技术",
            "sections": [
                {"key": "content", "text": "很长的第一部分策划报告"},
                {"key": "author", "text": "作者情况"},
                {"key": "marketing", "text": "很长的第六部分策划报告"},
            ],
            "scores": [],
            "bpmFields": {
                "brief": "BPM专用内容简介",
                "reader": "BPM专用读者对象",
                "feature": "BPM专用选题特色",
                "compare": "BPM专用同类比较",
                "compareSources": [
                    {"title": "书一", "url": "https://example.com/1"},
                    {"title": "书二", "url": "https://example.com/2"},
                ],
            },
        }

        topic = server.build_bpm_topic(
            {"canonical_fields": {"选题名称": "新能源功率预测应用技术"}},
            result,
        )

        self.assertEqual(topic["brief"], "BPM专用内容简介")
        self.assertEqual(topic["reader"], "BPM专用读者对象")
        self.assertEqual(topic["feature"], "BPM专用选题特色")
        self.assertEqual(topic["compare"], "BPM专用同类比较")
        self.assertEqual(len(topic["compareSources"]), 2)

    def test_book_search_returns_ranked_pages_with_excerpts(self):
        search_results = [
            {
                "title": "新能源发电功率预测_科学出版社",
                "url": "https://www.ecsponline.com/goods.php?id=1",
            },
            {
                "title": "光伏发电功率预测技术及应用_中国电力出版社",
                "url": "https://www.dushu.com/book/2/",
            },
            {"title": "无关新闻", "url": "https://news.example.com/item"},
        ]

        with (
            mock.patch.object(server, "search_web_results", return_value=search_results),
            mock.patch.object(
                server,
                "fetch_url_text",
                side_effect=lambda url, **_kwargs: (
                    "<html>新能源发电功率预测 作者王飞 出版社科学出版社 目录 风电 光伏 预测</html>"
                    if "ecsponline" in url
                    else "<html>光伏发电功率预测技术及应用 中国电力出版社 目录 数值天气预报</html>"
                ),
            ),
        ):
            books = server.book_comparison_search_context(
                {"canonical_fields": {"选题名称": "新能源功率预测应用技术"}}
            )

        self.assertEqual(len(books), 2)
        self.assertTrue(all(book["excerpt"] for book in books))
        self.assertEqual(books[0]["url"], "https://www.ecsponline.com/goods.php?id=1")

    def test_generate_dedicated_fields_uses_report_and_verified_search_context(self):
        model_result = {
            "bpmFields": {
                "brief": "专用内容简介",
                "reader": "本书适合大学电气类专业本科生、研究生，以及从事相关工作的人员使用。",
                "feature": "专用选题特色",
                "compare": "两本书的比较",
                "compareSources": [
                    {"title": "书一", "url": "https://example.com/1"},
                    {"title": "书二", "url": "https://example.com/2"},
                ],
            }
        }
        report = {
            "sections": [
                {"key": "content", "text": "策划报告第一部分"},
                {"key": "marketing", "text": "策划报告第六部分"},
            ]
        }

        with (
            mock.patch.object(
                server,
                "book_comparison_search_context",
                return_value=[
                    {"title": "书一", "url": "https://example.com/1", "excerpt": "目录一"},
                    {"title": "书二", "url": "https://example.com/2", "excerpt": "目录二"},
                ],
            ),
            mock.patch.object(server, "call_complete_report_model", return_value=model_result) as model,
        ):
            fields = server.generate_dedicated_bpm_fields(
                {"canonical_fields": {"选题名称": "测试选题"}}, report
            )

        prompt = model.call_args.args[0]
        self.assertIn("策划报告第一部分", prompt)
        self.assertIn("https://example.com/1", prompt)
        self.assertEqual(fields["brief"], "专用内容简介")
        self.assertEqual(len(fields["compareSources"]), 2)


if __name__ == "__main__":
    unittest.main()
