#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""paragraph.py —— 超长段落拆分

规则：一段（两个换行之间）去掉空白后超过 threshold 字，且不含对话引号，
     按句末标点拆成多个自然段。默认阈值从书籍配置读（paragraph_max，缺省 100）。
"""
import re

NAME = "分段"
DESC = "超长叙述段应拆分，保证手机端阅读呼吸感"

DEFAULT_MAX = 100
_SENT_SPLIT = re.compile(r"(?<=[。！？…])")


def _limit(ctx):
    if ctx and isinstance(ctx, dict):
        cfg = ctx.get("book_cfg") or {}
        try:
            return int(cfg.get("paragraph_max", DEFAULT_MAX))
        except Exception:
            return DEFAULT_MAX
    return DEFAULT_MAX


def _split_paragraph(p, limit):
    sents = [s for s in _SENT_SPLIT.split(p) if s.strip()]
    if len(sents) <= 1:
        return None
    groups, cur = [], ""
    for s in sents:
        if cur and len(re.sub(r"\s", "", cur + s)) > limit:
            groups.append(cur)
            cur = s
        else:
            cur += s
    if cur:
        groups.append(cur)
    return groups if len(groups) > 1 else None


def auto_fix(text, ctx=None):
    limit = _limit(ctx)
    paras = text.split("\n\n")
    out, n = [], 0
    for p in paras:
        body = p.strip()
        # 跳过标题、空行、含对话引号的段、Markdown 结构行
        if (not body or body.startswith("#") or body.startswith(">")
                or "“" in body or "”" in body or body.startswith("|")
                or body.startswith("- ") or body.startswith("* ")):
            out.append(p)
            continue
        if len(re.sub(r"\s", "", body)) > limit:
            groups = _split_paragraph(body, limit)
            if groups:
                out.extend(groups)
                n += 1
                continue
        out.append(p)
    fixes = [f"超长段拆段 ×{n}"] if n else []
    return "\n\n".join(out), fixes


def check(text, ctx=None):
    limit = _limit(ctx)
    problems = []
    for i, p in enumerate(text.split("\n\n"), 1):
        body = p.strip()
        if not body or body.startswith("#") or "“" in body:
            continue
        ln = len(re.sub(r"\s", "", body))
        if ln > limit:
            problems.append({
                "type": "分段",
                "desc": f"第{i}段长度 {ln} 字，超过 {limit} 字上限",
                "position": f"第{i}段",
                "severity": "低",
                "fixable": True,
                "suggestion": "按句号拆成多段",
            })
    return problems
