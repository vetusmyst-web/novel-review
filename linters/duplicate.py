#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""duplicate.py —— 重复词 / 重复句检测（只报不修）

两类：
  1. 口头禅式重复：同一 2-4 字短语在章内高频出现（排除常见虚词、人名）
  2. 整句重复：同一句（≥12字）出现两次以上
"""
import os
import re

NAME = "重复"
DESC = "章内高频重复词与重复句"

DEFAULT_PHRASE_LIMIT = 6   # 同一短语出现超过这个次数就报
MIN_SENT_LEN = 12

_WHITELIST = {
    "的时候", "什么都", "了一下", "不知道", "没有说话", "什么都没",
    "自己的", "一瞬间", "这么一", "那么一", "是不是", "忍不住",
    "看着", "听见", "声音", "心里", "眼睛", "似乎", "好像",
    # 高频虚词/助词组合：出现多不代表冗余
    "了一", "了他", "了她", "的地", "得地", "了吗", "了呢",
    "没有", "什么", "就是", "还是", "只是", "已经", "起来",
    "了起", "着不", "不的", "他的", "她的", "我的", "你的",
}
_SENT_SPLIT = re.compile(r"[。！？…\n]+")


def _person_names(ctx):
    """从书籍设定文件里抽取人名，避免把人名当重复词误报。"""
    names = set()
    if not isinstance(ctx, dict):
        return names
    book = ctx.get("book_cfg") or {}
    root = ctx.get("root")
    for rel in (book.get("setup_files") or {}).values():
        p = os.path.join(str(root), rel) if root else rel
        try:
            txt = open(p, encoding="utf-8").read(4000)
        except Exception:
            continue
        # 形如 "- 陈默：..." / "陈默，" / "### 陈默" 的条目
        for m in re.finditer(r"(?:^|\n)\s*[-*#>\s]*([\u4e00-\u9fff]{2,4})\s*[：:，,]", txt):
            names.add(m.group(1))
    return names


def _sents(text):
    return [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) >= MIN_SENT_LEN]


def auto_fix(text, ctx=None):
    return text, []


def check(text, ctx=None):
    problems = []
    limit = DEFAULT_PHRASE_LIMIT
    if ctx and isinstance(ctx, dict):
        try:
            limit = int((ctx.get("book_cfg") or {}).get("duplicate_limit", DEFAULT_PHRASE_LIMIT))
        except Exception:
            limit = DEFAULT_PHRASE_LIMIT

    skip_words = set(_WHITELIST) | _person_names(ctx)

    # 1) 短语重复
    cjk_only = re.sub(r"[^\u4e00-\u9fff]", " ", text)
    for w in skip_words:
        if len(w) >= 2:
            cjk_only = cjk_only.replace(w, " " * len(w))

    counts = {}
    for n in (2, 3, 4):
        for i in range(len(cjk_only) - n + 1):
            w = cjk_only[i:i + n]
            if " " in w or w in skip_words:
                continue
            counts.setdefault(w, {}).setdefault(n, 0)
            counts[w][n] += 1
    # 只保留不被更长短语包含的（避免 "他看着" 和 "看着" 同时报）
    hits = []
    for w, d in counts.items():
        best_n = max(d)
        c = d[best_n]
        if c <= limit:
            continue
        if any(w in other and other != w for other in hits):
            continue
        hits.append(w)
        hits.sort(key=len, reverse=True)
        problems.append({
            "type": "重复",
            "desc": f"短语「{w}」本章出现 {c} 次",
            "position": "全章",
            "severity": "低",
            "fixable": False,
            "suggestion": "换用同义表达或删去冗余",
        })

    # 2) 整句重复
    seen = {}
    for s in _sents(text):
        seen[s] = seen.get(s, 0) + 1
    for s, c in seen.items():
        if c >= 2:
            problems.append({
                "type": "重复",
                "desc": f"整句重复 {c} 次：{s[:30]}…",
                "position": "全章",
                "severity": "中",
                "fixable": False,
                "suggestion": "保留一处，其余改写或删除",
            })
    return problems
