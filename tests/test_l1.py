#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tests/test_l1.py —— L1 检查器单元测试（标准库 unittest）

运行： python3 -m unittest discover -s tests -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from linters import punct, paragraph, wordcount, duplicate  # noqa: E402


class TestPunct(unittest.TestCase):
    def test_half_to_full(self):
        src = "他说,这样不对."
        out, fixes = punct.auto_fix(src)
        self.assertEqual(out, "他说，这样不对。")
        self.assertTrue(fixes)

    def test_quote_pairing(self):
        src = '"你来吧."'
        out, _ = punct.auto_fix(src)
        self.assertIn("“", out)
        self.assertIn("”", out)

    def test_code_block_untouched(self):
        src = "```\na, b\n```"
        out, _ = punct.auto_fix(src)
        self.assertEqual(out, src)

    def test_clean_text_no_fix(self):
        src = "他说，这样不对。"
        out, fixes = punct.auto_fix(src)
        self.assertEqual(out, src)
        self.assertFalse(fixes)


class TestParagraph(unittest.TestCase):
    def test_long_paragraph_split(self):
        long_p = "这是第一句话。" * 20
        out, fixes = paragraph.auto_fix(long_p, {"book_cfg": {"paragraph_max": 50}})
        self.assertGreater(len(out.split("\n\n")), 1)
        self.assertTrue(fixes)

    def test_dialogue_paragraph_untouched(self):
        p = "“你今天怎么样？”" + "他问。" * 40
        out, fixes = paragraph.auto_fix(p, {"book_cfg": {"paragraph_max": 50}})
        self.assertEqual(out, p)
        self.assertFalse(fixes)

    def test_short_paragraph_untouched(self):
        p = "很短的一段。"
        out, fixes = paragraph.auto_fix(p, {})
        self.assertEqual(out, p)


class TestWordcount(unittest.TestCase):
    def test_below_min(self):
        probs = wordcount.check("字" * 100, {"book_cfg": {"min_chars": 200}})
        self.assertEqual(len(probs), 1)
        self.assertEqual(probs[0]["severity"], "高")

    def test_above_min(self):
        probs = wordcount.check("字" * 300, {"book_cfg": {"min_chars": 200}})
        self.assertEqual(probs, [])

    def test_cjk_count_ignores_latin(self):
        self.assertEqual(wordcount.cjk_count("abc汉字def"), 2)


class TestDuplicate(unittest.TestCase):
    def test_repeated_sentence(self):
        s = "他站在门口看了很久很久才转身离开。"
        probs = duplicate.check(s + s, {"book_cfg": {"duplicate_limit": 99}})
        types = [p["type"] for p in probs]
        self.assertIn("重复", types)

    def test_clean_text(self):
        probs = duplicate.check("他推开门。屋里没有人。窗外下着雨。", {})
        self.assertEqual([p for p in probs if p["severity"] == "中"], [])


if __name__ == "__main__":
    unittest.main()
