#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""punct.py —— 半角标点 → 全角（只处理中文语境，不动英文/代码块）"""
import re

NAME = "标点"
DESC = "中文正文中的半角标点应为全角"

# 需要跳过整段的标记（代码块、行内代码）
_SKIP_RE = re.compile(r"```.*?```|`[^`\n]*`", re.S)

_PAIRS = [
    (re.compile(r"([\u4e00-\u9fff]),"), "，"),
    (re.compile(r"([\u4e00-\u9fff])\."), "。"),
    (re.compile(r"([\u4e00-\u9fff]);"), "；"),
    (re.compile(r"([\u4e00-\u9fff]):"), "："),
    (re.compile(r"([\u4e00-\u9fff])\?"), "？"),
    (re.compile(r"([\u4e00-\u9fff])!"), "！"),
]


def _map_outside_skip(text, fn):
    """对非代码片段执行 fn，代码片段原样保留。"""
    out = []
    last = 0
    for m in _SKIP_RE.finditer(text):
        out.append(fn(text[last:m.start()]))
        out.append(m.group(0))
        last = m.end()
    out.append(fn(text[last:]))
    return "".join(out)


def _fix_plain(seg):
    for pat, rep in _PAIRS:
        seg = pat.sub(lambda m, r=rep: m.group(1) + r, seg)
    return seg


def _fix_quotes(seg):
    """成对半角双引号 → 中文弯引号。按出现顺序交替。"""
    buf = []
    opening = True
    for ch in seg:
        if ch == '"':
            buf.append("“" if opening else "”")
            opening = not opening
        else:
            buf.append(ch)
    return "".join(buf)


def auto_fix(text, ctx=None):
    new = _map_outside_skip(text, lambda s: _fix_quotes(_fix_plain(s)))
    fixes = []
    if new != text:
        n = sum(1 for a, b in zip(text, new) if a != b)
        fixes.append(f"半角标点→全角 ×{n}")
    return new, fixes


def check(text, ctx=None):
    fixed, _ = auto_fix(text)
    problems = []
    if fixed != text:
        # 找第一处差异做定位提示
        pos = next((i for i, (a, b) in enumerate(zip(text, fixed)) if a != b), 0)
        problems.append({
            "type": "标点",
            "desc": "存在半角标点（应为全角）",
            "position": f"约第{pos}字符",
            "severity": "低",
            "fixable": True,
            "suggestion": "运行 check 会自动修复",
        })
    return problems
