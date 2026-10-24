#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm.py —— LLM 适配层（多后端 + 自动降级 + manual 模式）
========================================================
设计要点：
  - 只用标准库 urllib，不依赖 requests
  - 任意 OpenAI 兼容接口都能接（DeepSeek / 豆包火山方舟 / 本地 Ollama / OneAPI）
  - 主后端失败自动降级到备用后端
  - manual 模式：不调 API，把拼好的 prompt 存成文件，供人工贴到网页版 AI

配置文件里的后端格式（config/config.json）：
  "backends": {
    "doubao": {
      "base_url": "https://ark.cn-beijing.volces.com/api/v3",
      "model": "doubao-lite-32k",
      "api_key_env": "DOUBAO_API_KEY"
    }
  }
api_key_env 填环境变量名，代码去 os.environ 里取，绝不写死密钥。
"""
import os
import json
import time
import urllib.request
import urllib.error


class LLMError(Exception):
    pass


def _load_env_file(path):
    """极简 .env 解析（KEY=VALUE，# 注释），不依赖 python-dotenv。"""
    if not os.path.exists(path):
        return
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
    except Exception:
        pass


def load_env(project_root):
    """加载项目根的 .env（若存在），不覆盖已有环境变量。"""
    _load_env_file(os.path.join(project_root, ".env"))


class LLM:
    def __init__(self, cfg, project_root=".", manual=False, verbose=False):
        self.cfg = cfg
        self.manual = manual
        self.verbose = verbose
        self.project_root = project_root
        self.backends = cfg.get("backends", {})
        self.default = cfg.get("default_backend", "")
        self.fallback = cfg.get("fallback_backend", "")
        self.timeout = cfg.get("request_timeout", 300)
        self.manual_dir = os.path.join(project_root, cfg.get("manual_dir", "output/manual"))
        self.calls = 0

    # ---------- 对外主接口 ----------
    def chat(self, prompt, system="你是一位严格的中文小说审稿编辑。",
             max_tokens=2000, temperature=0.2, tag="prompt"):
        """发起一次对话。返回正文字符串。manual 模式下写文件并返回占位提示。"""
        if self.manual:
            return self._save_manual(prompt, system, tag)

        order = []
        if self.default:
            order.append(self.default)
        if self.fallback and self.fallback not in order:
            order.append(self.fallback)
        if not order:
            raise LLMError("配置里没有可用的 backend（default_backend 为空）")

        errors = []
        for name in order:
            b = self.backends.get(name)
            if not b or not b.get("enabled", True):
                continue
            try:
                out = self._call_openai_compatible(b, prompt, system, max_tokens, temperature)
                self.calls += 1
                if self.verbose:
                    print(f"      [{name}] ok, {len(out)} 字")
                return out
            except Exception as e:
                errors.append(f"{name}: {e}")
                if self.verbose:
                    print(f"      [{name}] 失败: {e}")
                continue
        raise LLMError("所有后端都失败 -> " + " | ".join(errors))

    # ---------- 具体请求 ----------
    def _call_openai_compatible(self, b, prompt, system, max_tokens, temperature):
        base = b["base_url"].rstrip("/")
        url = base if base.endswith("/chat/completions") else base + "/chat/completions"
        key = os.environ.get(b.get("api_key_env", ""), "")
        if not key:
            raise LLMError(f"环境变量 {b.get('api_key_env')} 未设置")
        payload = {
            "model": b["model"],
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url, data=data, method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}",
            },
        )
        last = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    body = json.loads(r.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"].strip()
            except urllib.error.HTTPError as e:
                detail = ""
                try:
                    detail = e.read().decode("utf-8")[:300]
                except Exception:
                    pass
                last = f"HTTP {e.code} {detail}"
                # 429 / 5xx 重试，4xx 直接放弃
                if e.code in (429, 500, 502, 503, 504):
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError(last)
            except Exception as e:
                last = str(e)
                time.sleep(1.0 * (attempt + 1))
        raise LLMError(last or "未知错误")

    # ---------- manual 模式 ----------
    def _save_manual(self, prompt, system, tag):
        os.makedirs(self.manual_dir, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in tag)[:80]
        path = os.path.join(self.manual_dir, safe + ".md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("# 手动模式 Prompt\n\n")
            f.write("把下面【系统提示】和【用户提示】分别贴到 AI 网页版。\n\n")
            f.write("## 系统提示\n\n```\n" + system + "\n```\n\n")
            f.write("## 用户提示\n\n```\n" + prompt + "\n```\n\n")
            f.write("## 期望输出格式\n\n见用户提示末尾要求（严格 JSON）。\n")
        return json.dumps({"manual": True, "prompt_file": path}, ensure_ascii=False)


def main():
    """自检：打印后端配置与 key 是否就位。"""
    import sys
    root = os.path.dirname(os.path.abspath(__file__))
    cfg_path = os.path.join(root, "config", "config.json")
    if not os.path.exists(cfg_path):
        print("❌ 没有 config/config.json（请从 config.example.json 复制一份）")
        sys.exit(1)
    load_env(root)
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    print("后端状态：")
    for name, b in cfg.get("backends", {}).items():
        env = b.get("api_key_env", "")
        has = "✅" if os.environ.get(env) else "❌"
        print(f"  {has} {name}: model={b.get('model')} key_env={env}")
    print(f"\n默认后端: {cfg.get('default_backend')} / 备用: {cfg.get('fallback_backend')}")


if __name__ == "__main__":
    main()
