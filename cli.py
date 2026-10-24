#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
cli.py —— 命令行入口
====================
  python3 cli.py doctor                     自检
  python3 cli.py list-books                 列出所有书
  python3 cli.py add-book <书名>             从模板新建一本书的配置
  python3 cli.py check  --book <书名>        L1 免费硬扫（自动修复）
  python3 cli.py review --book <书名>        全流程 L1+L2+L3
  python3 cli.py review --book <书名> --n 3  只审第3章
  python3 cli.py review --book <书名> --manual   不调 API，只导出 prompt
  python3 cli.py verify --book <书名>        只跑 L3 复核队列
  python3 cli.py add-rule <规则名>           从模板新建一条规则
"""
import os
import sys
import json
import shutil
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import engine
from llm import LLM, LLMError, load_env

ROOT = engine.ROOT


# ------------------------------------------------------------------ 工具
def _paths(cfg):
    o = cfg.get("output", {})
    return {k: str(ROOT / v) for k, v in o.items()}


def _save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_json(path, default):
    if os.path.exists(path):
        try:
            return json.load(open(path, encoding="utf-8"))
        except Exception:
            pass
    return default


def _make_llm(cfg, manual=False, verbose=False):
    load_env(str(ROOT))
    return LLM(cfg, project_root=str(ROOT), manual=manual, verbose=verbose)


# ------------------------------------------------------------------ 命令
def cmd_doctor(args):
    print("=" * 52)
    print(" 小说审查系统 · 自检")
    print("=" * 52)
    ok = True

    print(f"\n[1] Python: {sys.version.split()[0]}", end="")
    print("  ✅" if sys.version_info >= (3, 8) else "  ❌ 需要 3.8+")
    ok &= sys.version_info >= (3, 8)

    cfg_path = engine.CONFIG_DIR / "config.json"
    print(f"\n[2] 配置文件 config/config.json: ", end="")
    if cfg_path.exists():
        print("✅")
        cfg = json.load(open(cfg_path, encoding="utf-8"))
    else:
        print("❌ 缺失")
        print("    修复： cp config/config.example.json config/config.json")
        return 1

    load_env(str(ROOT))
    print("\n[3] 后端与密钥：")
    any_key = False
    for name, b in (cfg.get("backends") or {}).items():
        env = b.get("api_key_env", "")
        has = bool(os.environ.get(env))
        any_key |= has
        flag = "✅" if has else ("⏸ 已禁用" if not b.get("enabled", True) else "❌ 未设置")
        print(f"    {name:10s} model={b.get('model','?'):28s} {env:20s} {flag}")
    if not any_key:
        print("    ⚠️  没有任何可用密钥 —— L1 仍可运行，L2/L3 需要密钥")
        print("    在项目根创建 .env，写入：DOUBAO_API_KEY=你的key")

    print("\n[4] 规则文件：")
    rules = sorted(p.stem for p in (engine.RULES_DIR).glob("*.md") if not p.name.startswith("_"))
    ex = sorted(p.stem for p in (engine.RULES_DIR / "examples").glob("*.md"))
    print(f"    rules/:          {', '.join(rules) or '（无）'}")
    print(f"    rules/examples/: {', '.join(ex) or '（无）'}")

    print("\n[5] 书单：")
    books = engine.list_books()
    if not books:
        print("    ❌ 没有可用书籍配置")
        ok = False
    for name, b in books.items():
        d = b.get("_chapter_dir", "")
        exists = os.path.isdir(d)
        chs = len(engine.list_chapters(b)) if exists else 0
        print(f"    {'✅' if exists else '❌'} {name}: {chs} 章")
        for rn in b.get("rules", []):
            try:
                engine.load_rule(rn)
            except SystemExit:
                print(f"        ❌ 规则缺失: {rn}")
                ok = False
        for label, rel in (b.get("setup_files") or {}).items():
            if not (ROOT / rel).exists():
                print(f"        ⚠️  设定文件不存在: {label} → {rel}")
        if not exists:
            ok = False

    print("\n[6] 输出目录：")
    for k in ("output", "state"):
        print(f"    {k}/ {'✅' if (ROOT / k).is_dir() else '❌'}")

    print("\n" + ("✅ 自检通过" if ok else "⚠️ 自检发现问题，见上"))
    return 0 if ok else 1


def cmd_list_books(args):
    books = engine.list_books()
    if not books:
        print("（没有书）新增：python3 cli.py add-book <书名>")
        return
    print("📚 可用书：")
    for name, b in books.items():
        chs = engine.list_chapters(b)
        print(f"  - {name}  [{b.get('genre','')}]  {len(chs)} 章")
        if chs:
            print(f"      范围：第{chs[0][0]}章 ~ 第{chs[-1][0]}章")


def cmd_add_book(args):
    name = args.name
    dst = engine.BOOKS_DIR / f"{name}.json"
    if dst.exists():
        print(f"❌ 已存在：{dst}")
        return 1
    tpl = engine.BOOKS_DIR / "_template.json"
    cfg = json.load(open(tpl, encoding="utf-8"))
    cfg["name"] = name
    for k in list(cfg.keys()):
        if isinstance(cfg[k], str) and "书名" in cfg[k]:
            cfg[k] = cfg[k].replace("书名", name)
    _save_json(str(dst), cfg)
    ch = ROOT / "books" / name / "章节"
    st = ROOT / "books" / name / "设定"
    os.makedirs(ch, exist_ok=True)
    os.makedirs(st, exist_ok=True)
    print(f"✅ 已创建书籍配置：{dst}")
    print(f"   章节目录：{ch}")
    print(f"   设定目录：{st}")
    print("   下一步：编辑该 json，填 genre / rules / setup_files")
    return 0


def cmd_add_rule(args):
    name = args.name
    dst = engine.RULES_DIR / f"{name}.md"
    if dst.exists():
        print(f"❌ 已存在：{dst}")
        return 1
    shutil.copy2(engine.RULES_DIR / "_template.md", dst)
    print(f"✅ 已创建规则模板：{dst}")
    print("   编辑后，把它加进书籍配置的 rules 数组即可生效（不用改代码）")
    return 0


def _review_common(args, deep):
    cfg = engine.load_config()
    book = engine.load_book(args.book)
    pat = book.get("chapter_file_pattern", r"^第(\d+)章[-\.\s]*(.*)\.md$")
    chapters = engine.list_chapters(book)
    if not chapters:
        print(f"❌ [ {args.book} ] 章节目录里没有匹配的章节：{book['_chapter_dir']}")
        print(f"   文件名需匹配：{pat}")
        return 1
    if args.n:
        chapters = [c for c in chapters if c[0] == args.n]
        if not chapters:
            print(f"❌ 没有第 {args.n} 章")
            return 1

    linters = engine.load_linters(cfg.get("l1", {}).get("enabled_linters", []))
    manual = getattr(args, "manual", False)
    llm = _make_llm(cfg, manual=manual, verbose=args.verbose) if deep else None
    auth = json.load(open(engine.CONFIG_DIR / "config.json", encoding="utf-8"))
    auth_book = dict(book)

    if deep and not manual:
        if not any(os.environ.get(b.get("api_key_env", ""))
                   for b in (cfg.get("backends") or {}).values() if b.get("enabled", True)):
            print("❌ 没有可用的 API 密钥，无法跑 L2/L3。")
            print("   方案一：在项目根建 .env 写入 DOUBAO_API_KEY=... / DEEPSEEK_API_KEY=...")
            print("   方案二：加 --manual，只导出 prompt 文本，手动贴到网页版 AI")
            return 1

    print(f"📖 [ {book['name']} ] 共 {len(chapters)} 章待审{'(含 L2/L3 语义审查)' if deep else '(仅 L1 免费硬扫)'}")

    results = []
    for n, fname, t in chapters:
        path = os.path.join(book["_chapter_dir"], fname)
        title = engine.chapter_title(n, t)
        text = engine.read_text(path)
        ctx = {"book_cfg": book, "chapter": n, "root": str(ROOT)}

        new_text, problems, fixes = engine.run_l1(text, ctx, linters, backup=path, cfg=cfg)
        l1_issues = [p for p in problems if not p.get("fixable")]
        r = {"chapter": n, "file": fname, "title": title,
             "fixes": fixes, "l1": l1_issues, "confirmed": [], "l2_count": 0}

        if deep:
            l2 = engine.run_l2(auth_book, fname, new_text, n, title, llm,
                               auth_book.get("rules", []), verbose=args.verbose)
            r["l2_count"] = len(l2)
            if l2 and not manual:
                r["confirmed"] = engine.run_l3(auth_book, new_text, title, l2, llm, auth, verbose=args.verbose)
                _save_json(_paths(auth)["queue_file"],
                           [{"book": book["name"], "chapter": n, "problems": l2}])
            elif l2:
                r["confirmed"] = l2  # manual 模式：直接把疑似问题当结果展示

        results.append(r)
        mark = []
        if fixes:
            mark.append(f"🛠 {len(fixes)} 项自动修复")
        if r["l1"]:
            mark.append(f"⚠️ {len(r['l1'])} 项硬伤")
        if r["l2_count"]:
            mark.append(f"🔍 {r['l2_count']} 条疑似")
        if r["confirmed"]:
            mark.append(f"❗ {len(r['confirmed'])} 条确认")
        print(f"  {title}  {' | '.join(mark) if mark else '✓ 无异常'}")

    rep = engine.write_report(_paths(auth)["report_file"], book, results)
    _save_json(_paths(auth)["confirmed_file"],
               [{"book": book["name"], "chapter": r["chapter"], "title": r["title"],
                 "issues": r["confirmed"]} for r in results if r["confirmed"]])
    print(f"\n📄 报告：{rep}")
    if manual:
        print(f"📝 手动模式 prompt 已导出到：{ROOT / auth.get('manual_dir','output/manual')}")
    return 0


def cmd_check(args):
    return _review_common(args, deep=False)


def cmd_review(args):
    return _review_common(args, deep=True)


def cmd_verify(args):
    cfg = engine.load_config()
    book = engine.load_book(args.book)
    q = _load_json(_paths(cfg)["queue_file"], [])
    items = [x for x in q if x.get("book") == book["name"] and x.get("problems")]
    if not items:
        print("✅ 待复核队列为空")
        return 0
    llm = _make_llm(cfg, verbose=args.verbose)
    total = 0
    for it in items:
        n = it["chapter"]
        fname = next((f for nn, f, _ in engine.list_chapters(book) if nn == n), None)
        if not fname:
            print(f"⚠️  找不到第 {n} 章文件，跳过")
            continue
        text = engine.read_text(os.path.join(book["_chapter_dir"], fname))
        title = engine.chapter_title(n, next(t for nn, f, t in engine.list_chapters(book) if nn == n))
        conf = engine.run_l3(book, text, title, it["problems"], llm, cfg, verbose=args.verbose)
        print(f"  {title}: {len(it['problems'])} 条疑似 → 确认 {len(conf)} 条")
        total += len(conf)
    print(f"\n✅ 复核完成，确认 {total} 条问题")
    return 0


# ------------------------------------------------------------------ 入口
def build_parser():
    p = argparse.ArgumentParser(
        prog="cli.py",
        description="小说审查系统 —— L1 免费硬扫 / L2 语义扫描 / L3 二次复核",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("doctor", help="自检：配置/密钥/书单/规则").set_defaults(func=cmd_doctor)
    sub.add_parser("list-books", help="列出所有书").set_defaults(func=cmd_list_books)

    a = sub.add_parser("add-book", help="新建一本书的配置")
    a.add_argument("name")
    a.set_defaults(func=cmd_add_book)

    a = sub.add_parser("add-rule", help="新建一条审查规则")
    a.add_argument("name")
    a.set_defaults(func=cmd_add_rule)

    for name, fn, hlp in (("check", cmd_check, "L1 免费硬扫（自动修标点/分段）"),
                          ("review", cmd_review, "全流程 L1+L2+L3")):
        a = sub.add_parser(name, help=hlp)
        a.add_argument("--book", required=True)
        a.add_argument("--n", type=int, default=0, help="只审第 N 章")
        a.add_argument("--manual", action="store_true", help="不调 API，导出 prompt 文本")
        a.add_argument("--verbose", action="store_true")
        a.set_defaults(func=fn)

    a = sub.add_parser("verify", help="只跑 L3 复核队列")
    a.add_argument("--book", required=True)
    a.add_argument("--verbose", action="store_true")
    a.set_defaults(func=cmd_verify)
    return p


def main():
    ap = build_parser()
    args = ap.parse_args()
    if not getattr(args, "cmd", None):
        ap.print_help()
        return 0
    try:
        return args.func(args) or 0
    except KeyboardInterrupt:
        print("\n中断")
        return 130
    except LLMError as e:
        print(f"❌ LLM 调用失败：{e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
