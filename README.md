# 小说审查系统 (novel-review)

一个**配置驱动、零第三方依赖**的中文网文自动审查工具。

对一本书的多章 Markdown 正文做三级审查，产出结构化报告：

| 层级 | 做什么 | 成本 | 是否改原文 |
| --- | --- | --- | --- |
| **L1 硬扫** | 半角标点→全角、超长段拆分、字数检查、重复词句 | 免费 | 会，但先备份 |
| **L2 语义** | 按你自己的规则逐条挑错（文风、设定、承接、节奏…） | 按模型计费 | 不改 |
| **L3 复核** | 第二次 AI 调用逐条筛误报 | 按模型计费 | 不改 |

设计原则：**引擎与书内容完全解耦**。代码里没有任何书名、人物、题材词。
加一本书 = 加一个 JSON 文件。加一条审查规则 = 加一个 Markdown 文件。**都不用改代码。**

---

## 五分钟跑起来

```bash
git clone https://github.com/vetusmyst-web/novel-review.git
cd novel-review

# 1. 建配置
cp config/config.example.json config/config.json

# 2. 先跑免费的那部分（不需要任何 API key）
python3 cli.py doctor            # 自检
python3 cli.py list-books        # 看有哪些书
python3 cli.py check --book demo # L1 硬扫 demo 书
cat output/report.md             # 看报告
```

到这里你已经能看到 L1 的效果了，**一分钱没花、一个 key 都没填**。

### 想用 L2/L3，再填密钥

在项目根建一个 `.env`（已被 .gitignore 排除，不会提交）：

```
DEEPSEEK_API_KEY=sk-xxxxx
# 或者用豆包（火山方舟）
DOUBAO_API_KEY=xxxxx
```

> 密钥只从环境变量读，代码里不存任何 key，也不会去翻你的 shell 配置文件。

如果你连 key 都不想填，还有 **manual 模式**：只导出拼好的 prompt，
你自己贴到任意 AI 网页版，把 JSON 结果贴回来。

```bash
python3 cli.py review --book demo --n 1 --manual
# prompt 会导出到 output/manual/*.md
```

手动模式的完整流程（不需要任何 API key）：

1. 上一步每条规则会导出一份 prompt，文件名形如 `demo_001_style.md`，
   里面分成【系统提示】和【用户提示】两段。
2. 打开其中一份，**把两个代码块里的内容一起贴给 AI**（豆包网页版、DeepSeek 网页版、
   ChatGPT 都行）。
3. AI 会回一个 JSON，形如：
   ```json
   {"problems": [{"type":"标点","position":"第3段","desc":"用了半角逗号","severity":"低","suggestion":"改成全角"}]}
   ```
4. 拿到 JSON 后，**人工筛一遍**：把确认要改的条目自己改到正文里。
   字数不足、节奏这类需要判断的问题，AI 只给建议，改不改由你定。

> 说明：目前 manual 模式只做到「导出 prompt」这一步，AI 的回复需要你自己看、自己改，
> 不会自动回灌进报告。想要全自动（AI 结果直接写进 `output/report.md` 并做 L3 复核），
> 需要在 `.env` 里配一个 API key。DeepSeek 每章约几分钱，是成本最低的选择。

---

## 常用命令

```bash
python3 cli.py doctor                          # 自检：配置/密钥/书单/规则
python3 cli.py list-books                      # 列出所有书和章节范围
python3 cli.py check  --book <名>              # L1 免费硬扫（自动修复）
python3 cli.py review --book <名>              # 全流程 L1+L2+L3
python3 cli.py review --book <名> --n 3        # 只审第 3 章
python3 cli.py review --book <名> --manual     # 不调 API，只导出 prompt
python3 cli.py review --book <名> --verbose    # 显示每条规则的原始返回数
python3 cli.py verify --book <名>              # 只跑 L3 复核队列
python3 cli.py add-book <名>                   # 从模板新建一本书
python3 cli.py add-rule <名>                   # 从模板新建一条规则
```

---

## 加一本你自己的书

```bash
python3 cli.py add-book 我的书
```

会生成 `config/books/我的书.json` 和目录 `books/我的书/{章节,设定}/`。

把你的章节放进去，文件名需要匹配正则（默认 `第01章-标题.md`），然后改配置：

```json
{
  "name": "我的书",
  "genre": "修仙爽文·扮猪吃虎",
  "chapter_dir": "books/我的书/章节",
  "setup_files": {
    "人物": "books/我的书/设定/人物.md",
    "世界观": "books/我的书/设定/世界观.md"
  },
  "min_chars": 4500,
  "rules": ["style", "consistency", "continuity", "pacing"]
}
```

`setup_files` 里列出的文件内容会被塞进 prompt，让 AI 知道这本书的设定红线。
**这是审查质量的关键 —— 设定写得越清楚，误报越少。**

> 注意：`books/` 目录已在 `.gitignore` 里，你的正文不会被误提交。

---

## 加一条你自己的审查规则

```bash
python3 cli.py add-rule 我的规则
```

编辑 `rules/我的规则.md`，格式见 `rules/_template.md`。核心结构：

```markdown
- 规则名: 我的规则
- 严重度门槛: 高,中
- max_tokens: 2000

## Prompt

（你的审查提示词，可以用占位符）

只输出一个 JSON 对象：
{"problems": [{"type":"...","position":"...","desc":"...","severity":"高|中|低","suggestion":"..."}]}
```

可用占位符：

| 占位符 | 内容 |
| --- | --- |
| `{title}` | 章节标题 |
| `{text}` | 本章正文全文 |
| `{prev_ending}` | 上一章结尾 600 字 |
| `{setup}` | setup_files 拼接的设定内容 |
| `{genre}` | 书籍 genre 字段 |
| `{baseline}` | 书籍 baseline 字段 |

把规则名加进书籍配置的 `rules` 数组就生效了，**不用改代码**。

写规则的三个要点：
1. **明确列举要抓什么**，不要只说"检查质量"
2. **明确说宁缺毋滥**，否则 AI 会为了凑数编问题
3. **强制 JSON 输出**，并在 Prompt 里给一个完整例子

---

## 自定义 L1 检查

`linters/` 下每个模块就是一个检查器，接口固定：

```python
NAME = "检查名"
DESC = "说明"

def check(text, ctx):        # 返回问题列表
    return [{"type": "...", "desc": "...", "severity": "低", "fixable": False}]

def auto_fix(text, ctx):     # 可选：支持自动修复
    return new_text, ["修复说明"]
```

在 `config/config.json` 的 `l1.enabled_linters` 数组里加上模块名即可。

---

## 后端配置

`config/config.json` 里可以配多个后端，主后端失败自动降级：

```json
{
  "default_backend": "doubao",
  "fallback_backend": "deepseek",
  "backends": {
    "doubao": {
      "base_url": "https://ark.cn-beijing.volces.com/api/v3",
      "model": "你的接入点ID或模型名",
      "api_key_env": "DOUBAO_API_KEY"
    }
  }
}
```

任何 **OpenAI 兼容接口** 都能接：DeepSeek、火山方舟（豆包）、本地 Ollama、OneAPI 等。
只要改 `base_url` + `model` + `api_key_env` 三项。

---

## 常见问题

**Q：使用这个工具会消耗仓库作者的 API 额度吗？**

不会。本仓库**不含任何 API 密钥**，`config.example.json` 里只有环境变量名（如
`DOUBAO_API_KEY`），没有真实 key，`.gitignore` 已挡住本地的 `config.json` 和 `.env`。

- **L1 硬扫完全不联网**，只用内置的字符串规则，零成本、零额度。
- 想用 L2/L3，必须**自己在本地 `.env` 里填自己的 key**，花的是自己的额度。
- 不想填 key 也能用：加 `--manual` 只导出 prompt，贴到你自己的 AI 网页版。

**Q：`check` 会改我的正文吗？**
会，但第一件事是备份成 `xxx.md.bak`，且只改确定性错误（半角标点、超长段）。
字数不足这类需要人工判断的，只报不改。
想彻底关掉自动修复，把 `config.json` 里 `l1.backup_before_fix` 设为 false 并删掉对应 linter —— 更好的做法是手动改 `linters/punct.py` 的 `auto_fix` 直接 return 原文本。

**Q：报错"缺少 config/config.json"**
执行 `cp config/config.example.json config/config.json`。

**Q：doctor 说没有密钥**
L1 不需要密钥。L2/L3 需要在 `.env` 里填 key，或者用 `--manual` 手动模式。

**Q：AI 老是报一堆不存在的问题**
说明你的 `setup_files` 设定太薄。AI 不知道这本书的规则，只能瞎猜。
把人物红线、世界观铁律写进设定文件，误报会显著下降。

**Q：章节没被识别到**
检查文件名是否匹配 `chapter_file_pattern`。默认是 `第01章-标题.md`。
`python3 cli.py doctor` 会告诉你书里识别到几章。

**Q：能审 txt 或 docx 吗？**
目前只支持 Markdown。先把内容转成 `.md`，一章一个文件。

---

## 目录结构

```
novel-review/
├── cli.py                    # 命令行入口
├── engine.py                 # 审查引擎（L1/L2/L3 编排）
├── llm.py                    # LLM 适配层（多后端 + 降级 + manual）
├── linters/                  # L1 检查器（可插拔）
├── rules/                    # 审查规则（一规则一 .md）
│   └── examples/             # 内置示例规则
├── config/
│   ├── config.example.json   # 全局配置模板
│   └── books/                # 一本书一份配置
├── demo/                     # 示例书（假数据，clone 即可跑）
├── output/                   # 报告、prompt 导出（不提交）
├── state/                    # 队列、进度（不提交）
└── tests/                    # 单元测试
```

## 运行测试

```bash
python3 -m unittest discover -s tests -v
```

## 环境要求

- Python 3.8+（只用标准库，无 pip install）
- 网络（仅 L2/L3 需要）

## 许可

见 LICENSE：仅供个人学习与自用，禁止商业转售。
