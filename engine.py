#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
engine.py —— 审查引擎核心（L1 硬扫 / L2 语义 / L3 复核）
==========================================================
与具体书内容完全解耦：
  - 书单从 config/books/*.json 自动发现
  - 审查规则从 rules/*.md 读取
  - 后端从 config/config.json 读取
  - 所有路径相对项目根

只用 Python 标准库。
"""
import os
import re
import json
import shutil
import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CONFIG_DIR = ROOT / "config"
BOOKS_DIR = CONFIG_DIR / "books"
RULES_DIR = ROOT / "rules"

CJK = re.compile(r"[\u4e00-\u9fff]")


# ---------------------------------------------------------------- 配置
def load_config():
    p = CONFIG_DIR / "config.json"
    if not p.exists():
        raise SystemExit(
            "❌ 缺少 config/config.json\n"
            "   请执行： cp config/config.example.json config/config.json\n"
            "   然后填入 model 与 api key 环境变量。"
        )
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def _resolve(book):
    """把配置里的相对路径解析成绝对路径（就地写入 _chapter_dir）。"""
    if book.get("chapter_dir"):
        book["_chapter_dir"] = str((ROOT / book["chapter_dir"]).resolve())
    return book


def list_books():
    out = {}
    if not BOOKS_DIR.is_dir():
        return out
    for f in sorted(BOOKS_DIR.glob("*.json")):
        if f.name.startswith("_"):
            continue
        try:
            cfg = json.load(open(f, encoding="utf-8"))
        except Exception as e:
            print(f"⚠️  配置解析失败 {f.name}: {e}")
            continue
        if cfg.get("enabled", True):
            out[f.stem] = _resolve(cfg)
    return out


def load_book(name):
    books = list_books()
    if name not in books:
        raise SystemExit(
            f"❌ 没有书 [ {name} ]\n   可用书：{', '.join(books) or '（无）'}\n"
            f"   新增：python3 cli.py add-book {name}"
        )
    cfg = books[name]
    if cfg.get("chapter_dir"):
        cfg["_chapter_dir"] = str((ROOT / cfg["chapter_dir"]).resolve())
    return cfg


# ---------------------------------------------------------------- 规则
def load_rule(rule_name):
    """从 rules/ 或 rules/examples/ 加载规则 .md。返回 dict。"""
    for cand in (RULES_DIR / f"{rule_name}.md", RULES_DIR / "examples" / f"{rule_name}.md"):
        if cand.exists():
            return parse_rule(cand)
    raise SystemExit(f"❌ 找不到规则文件：rules/{rule_name}.md")


def parse_rule(path):
    raw = open(path, encoding="utf-8").read()
    meta = {}
    body = raw
    # 头部 bullet 元信息：  - 规则名: xxx
    for m in re.finditer(r"^\s*-\s*(规则名|严重度门槛|max_tokens|temperature)\s*[:：]\s*(.+)$", raw, re.M):
        meta[m.group(1)] = m.group(2).strip()
    m = re.search(r"^##\s*Prompt\s*$(.*)", raw, re.M | re.S)
    if not m:
        raise SystemExit(f"❌ 规则文件缺少 '## Prompt' 段：{path}")
    body = m.group(1).strip()

    keep = [s.strip() for s in meta.get("严重度门槛", "高,中").replace("，", ",").split(",") if s.strip()]
    return {
        "name": meta.get("规则名", path.stem),
        "file": path.name,
        "prompt": body,
        "keep_severity": keep,
        "max_tokens": int(meta.get("max_tokens", 2000)),
        "temperature": float(meta.get("temperature", 0.2)),
    }


# ---------------------------------------------------------------- 工具
def cjk_count(t):
    return len(CJK.findall(t))


def read_text(p):
    return open(p, encoding="utf-8").read()


def chapter_num(fname, pattern):
    m = re.match(pattern, fname)
    if not m:
        return 0, fname
    try:
        n = int(m.group(1))
    except Exception:
        return 0, fname
    title = m.group(m.lastindex) if m.lastindex and m.lastindex >= 2 else ""
    return n, title


def list_chapters(book):
    d = book["_chapter_dir"]
    if not os.path.isdir(d):
        return []
    pat = book.get("chapter_file_pattern", r"^第(\d+)章[-\.\s]*(.*)\.md$")
    out = []
    for f in os.listdir(d):
        if not f.endswith(".md"):
            continue
        n, t = chapter_num(f, pat)
        if n > 0:
            out.append((n, f, t))
    out.sort(key=lambda x: x[0])
    return out


def chapter_title(n, t):
    return f"第{n:02d}章 {t}".strip()


def prev_ending(book, n, pat):
    """上一章结尾 600 字。"""
    for nn, f, _ in list_chapters(book):
        if nn == n - 1:
            return read_text(os.path.join(book["_chapter_dir"], f))[-600:]
    return "（本章是第一章，无上一章）"


def setup_text(book, maxlen=1500):
    parts = []
    for label, rel in (book.get("setup_files") or {}).items():
        p = ROOT / rel
        if p.exists():
            t = read_text(p)
            parts.append(f"--- {label} ---\n{t[:maxlen]}")
        else:
            parts.append(f"--- {label} ---\n（文件不存在：{rel}）")
    return "\n\n".join(parts) or "（本书未配置设定文件）"


# ---------------------------------------------------------------- L1
def load_linters(enabled):
    import importlib
    mods = []
    for name in enabled:
        try:
            m = importlib.import_module(f"linters.{name}")
            mods.append((name, m))
        except Exception as e:
            print(f"⚠️  L1 插件 {name} 加载失败: {e}")
    return mods


def run_l1(text, ctx, linters, backup=None, cfg=None):
    """执行所有 L1 检查并自动修复可修项。返回 (新文本, 问题列表, 修复记录)。"""
    problems, fixes = [], []
    cur = text
    for name, mod in linters:
        try:
            for p in mod.check(cur, ctx) or []:
                p.setdefault("linter", name)
                problems.append(p)
        except Exception as e:
            problems.append({"type": name, "desc": f"检查异常: {e}", "severity": "低", "fixable": False})

    for name, mod in linters:
        if not hasattr(mod, "auto_fix"):
            continue
        try:
            new, fx = mod.auto_fix(cur, ctx)
            if new != cur:
                cur = new
                fixes.extend(fx or [])
        except Exception as e:
            fixes.append(f"{name} 修复失败: {e}")

    if fixes and cur != text and backup is not None:
        shutil.copy2(backup, str(backup) + ".bak")
        with open(backup, "w", encoding="utf-8") as f:
            f.write(cur)
    return cur, problems, fixes


# ---------------------------------------------------------------- L2/L3
def _parse_json_obj(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _parse_json_arr(raw):
    m = re.search(r"\[.*\]", raw, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _normalize_problems(d):
    """把 AI 返回的 problems 字段规整成 list[dict]，剔除脏元素。

    AI 常见格式错误：返回字符串、返回 dict、列表里混入字符串/None。
    """
    if not isinstance(d, dict):
        return []
    raw = d.get("problems", [])
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []
    out = []
    for p in raw:
        if not isinstance(p, dict):
            continue
        sev = p.get("severity")
        if sev not in ("高", "中", "低"):
            p["severity"] = "中"
        out.append(p)
    return out


def run_l2(book, fname, text, n, title, llm, rule_names, verbose=False):
    problems = []
    setup = setup_text(book)
    prev = prev_ending(book, n, book.get("chapter_file_pattern", r"^第(\d+)章[-\.\s]*(.*)\.md$"))
    for rn in rule_names:
        rule = load_rule(rn)
        prompt = (rule["prompt"]
                  .replace("{title}", title)
                  .replace("{text}", text)
                  .replace("{prev_ending}", prev)
                  .replace("{setup}", setup)
                  .replace("{genre}", book.get("genre", ""))
                  .replace("{baseline}", book.get("baseline", ""))
                  .replace("{time_baseline_desc}", book.get("time_baseline", "")))
        try:
            raw = llm.chat(prompt, max_tokens=rule["max_tokens"],
                           temperature=rule["temperature"],
                           tag=f"{book['name']}_{n:03d}_{rn}")
            d = _parse_json_obj(raw)
            found = _normalize_problems(d)
            kept = 0
            for p in found:
                if p.get("severity") not in rule["keep_severity"]:
                    continue
                p["rule"] = rule["name"]
                problems.append(p)
                kept += 1
            if verbose:
                print(f"      L2[{rule['name']}] → 原始 {len(found)} 条，保留 {kept} 条")
        except Exception as e:
            problems.append({"type": "扫描失败", "rule": rule["name"],
                             "desc": str(e), "severity": "中", "suggestion": ""})
    return problems


def run_l3(book, text, title, problems, llm, cfg, verbose=False):
    l3 = cfg.get("l3", {})
    if not l3.get("enabled", True) or not problems:
        return []
    instruct = l3.get("instruct", "")
    prompt = (instruct
              .replace("{redline_types}", "、".join(l3.get("redline_types", [])))
              .replace("{setup}", setup_text(book))
              .replace("{text_excerpt}", text[:3000])
              .replace("{problems_json}", json.dumps(problems, ensure_ascii=False)[:3500]))
    try:
        raw = llm.chat(prompt, system=l3.get("system", "你是严格的终审编辑。"),
                       max_tokens=2000, temperature=0.1,
                       tag=f"{book['name']}_L3_{title}")
    except Exception as e:
        return [{"error": f"L3 复核失败: {e}"}]
    arr = _parse_json_arr(raw)
    if not arr:
        return [{"error": "L3 输出无法解析为 JSON 数组"}]
    confirmed = []
    for v in arr:
        if not isinstance(v, dict):
            continue
        if v.get("confirmed") is not True and v.get("confirmed") != "true":
            continue
        i = v.get("index")
        if isinstance(i, str) and i.isdigit():
            i = int(i)
        if isinstance(i, int) and 0 <= i < len(problems):
            orig = dict(problems[i])
            orig["l3_reason"] = v.get("reason", "")
            if v.get("suggestion"):
                orig["suggestion"] = v["suggestion"]
            confirmed.append(orig)
    return confirmed


# ---------------------------------------------------------------- 报告
def write_report(path, book, results, now=None):
    now = now or datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    lines = [f"# 审查报告 · {book['name']}", "", f"生成时间：{now}", ""]
    total_hard = total_sem = 0
    for r in results:
        lines.append(f"## {r['title']}")
        lines.append("")
        if r["fixes"]:
            lines.append("**L1 已自动修复**")
            for f in r["fixes"]:
                lines.append(f"- {f}")
            total_hard += len(r["fixes"])
        if r["l1"]:
            lines.append("**L1 问题（需人工看）**")
            for p in r["l1"]:
                lines.append(f"- [{p.get('severity')}] {p.get('type')}：{p.get('desc')} {p.get('suggestion','')}")
        if r.get("confirmed"):
            lines.append("**L3 确认问题（待处理）**")
            for p in r["confirmed"]:
                lines.append(f"- [{p.get('severity')}] {p.get('type')}｜{p.get('position','')}｜{p.get('desc')}"
                             f"｜建议：{p.get('suggestion','')}")
                total_sem += 1
        elif r.get("l2_count"):
            lines.append(f"**L2 疑似 {r['l2_count']} 条，全部被 L3 判为误报**")
        if not (r["fixes"] or r["l1"] or r.get("confirmed") or r.get("l2_count")):
            lines.append("✓ 无异常")
        lines.append("")
    lines.insert(3, f"合计：自动修复 {total_hard} 项，确认问题 {total_sem} 条。")
    lines.insert(4, "")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path
