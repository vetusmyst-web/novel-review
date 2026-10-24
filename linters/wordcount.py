#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""wordcount.py —— 字数检查（只报不修，补写必须人工/AI 介入）"""
import re

NAME = "字数"
DESC = "章节汉字数是否达到书籍配置的下限"

_CJK = re.compile(r"[\u4e00-\u9fff]")


def cjk_count(text):
    return len(_CJK.findall(text))


def _min_chars(ctx):
    if ctx and isinstance(ctx, dict):
        cfg = ctx.get("book_cfg") or {}
        try:
            return int(cfg.get("min_chars", 4500))
        except Exception:
            return 4500
    return 4500


def auto_fix(text, ctx=None):
    return text, []


def check(text, ctx=None):
    need = _min_chars(ctx)
    n = cjk_count(text)
    if n < need:
        return [{
            "type": "字数",
            "desc": f"正文 {n} 字，低于下限 {need} 字",
            "position": "全章",
            "severity": "高",
            "fixable": False,
            "suggestion": f"需补写约 {need - n} 字，不可自动完成",
        }]
    return []
