#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_engine.py —— 引擎容错测试

重点验证：AI 返回各种脏数据时，引擎不能崩。
运行： python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import engine  # noqa: E402


class TestJsonParse(unittest.TestCase):
    def test_plain_object(self):
        self.assertIsInstance(engine._parse_json_obj('{"problems": []}'), dict)

    def test_markdown_wrapped(self):
        self.assertIsInstance(engine._parse_json_obj('```json\n{"problems": []}\n```'), dict)

    def test_text_before_json(self):
        d = engine._parse_json_obj('好的，分析如下：\n{"problems": []}')
        self.assertEqual(d, {"problems": []})

    def test_garbage_returns_none(self):
        self.assertIsNone(engine._parse_json_obj("这章没问题"))
        self.assertIsNone(engine._parse_json_obj(""))
        self.assertIsNone(engine._parse_json_obj('{"problems": [{"a": '))

    def test_array_parse(self):
        self.assertEqual(engine._parse_json_arr('[{"index":0}]'), [{"index": 0}])
        self.assertIsNone(engine._parse_json_arr("没有数组"))


class TestNormalizeProblems(unittest.TestCase):
    """AI 返回格式错误时不能崩溃 —— 曾经这里是 AttributeError 崩溃点。"""

    def test_problems_is_string(self):
        self.assertEqual(engine._normalize_problems({"problems": "不是数组"}), [])

    def test_problems_is_dict(self):
        out = engine._normalize_problems({"problems": {"type": "x", "severity": "高"}})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["type"], "x")

    def test_list_with_non_dict(self):
        out = engine._normalize_problems({"problems": ["字符串", None, 123, {"type": "ok"}]})
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]["type"], "ok")

    def test_missing_problems_key(self):
        self.assertEqual(engine._normalize_problems({"other": 1}), [])

    def test_none_input(self):
        self.assertEqual(engine._normalize_problems(None), [])

    def test_not_a_dict(self):
        self.assertEqual(engine._normalize_problems([1, 2, 3]), [])

    def test_bad_severity_defaults_to_mid(self):
        out = engine._normalize_problems({"problems": [{"type": "x", "severity": "严重"}]})
        self.assertEqual(out[0]["severity"], "中")

    def test_valid_severity_kept(self):
        for sev in ("高", "中", "低"):
            out = engine._normalize_problems({"problems": [{"severity": sev}]})
            self.assertEqual(out[0]["severity"], sev)


class TestChapterNum(unittest.TestCase):
    PAT = r"^第(\d+)章[-\s]*(.*)\.md$"

    def test_standard(self):
        self.assertEqual(engine.chapter_num("第01章-门锁.md", self.PAT), (1, "门锁"))

    def test_space_separator(self):
        self.assertEqual(engine.chapter_num("第1章 门锁.md", self.PAT), (1, "门锁"))

    def test_no_title(self):
        n, t = engine.chapter_num("第01章.md", self.PAT)
        self.assertEqual((n, t), (1, ""))

    def test_leading_zeros(self):
        n, _ = engine.chapter_num("第003章.md", self.PAT)
        self.assertEqual(n, 3)

    def test_non_matching(self):
        self.assertEqual(engine.chapter_num("第一章-门锁.md", self.PAT)[0], 0)

    def test_wrong_extension(self):
        self.assertEqual(engine.chapter_num("第1章-门锁.txt", self.PAT)[0], 0)


class TestChapterTitle(unittest.TestCase):
    def test_with_title(self):
        self.assertEqual(engine.chapter_title(3, "风起"), "第03章 风起")

    def test_without_title(self):
        self.assertEqual(engine.chapter_title(3, ""), "第03章")


if __name__ == "__main__":
    unittest.main()
