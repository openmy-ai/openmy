<div align="center">

<img src="docs/images/openmy-banner.png" alt="OpenMy Banner" width="800" />

<br />

### 🎙️ 一段音频 → 一整天的结构化上下文

**OpenMy** 是开源的个人上下文引擎。  
录一段音频，自动转写、清洗、切场景、识别对象、蒸馏摘要、生成日报。  
让你的 AI Agent 真正「认识你」。

<br />

[![GitHub release](https://img.shields.io/github/v/release/openmy-ai/openmy?style=flat-square&color=blue)](https://github.com/openmy-ai/openmy/releases)
[![License: MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-167%20passed-brightgreen?style=flat-square)]()

[快速开始](#-30-秒快速开始) · [功能亮点](#-功能亮点) · [前端工作台](#-前端工作台) · [English](README.en.md)

</div>

---

## ⚡ 30 秒快速开始

```bash
git clone https://github.com/openmy-ai/openmy.git && cd openmy
python3 -m venv .venv && source .venv/bin/activate
pip install .
echo "GEMINI_API_KEY=你的key" > .env
openmy quick-start path/to/your-audio.wav
```

就这五步。浏览器会自动打开 `http://127.0.0.1:8420`，展示你的第一份日报。

<details>
<summary>🤔 缺 FFmpeg？Python 版本不对？<b>CLI 会用人话告诉你</b></summary>

```
❌ 缺少 ffmpeg、ffprobe。macOS 可先运行 `brew install ffmpeg`。
❌ 需要 Python 3.10 以上版本。可先运行 `brew install python@3.11`。
❌ 没找到项目根目录 `.env`，也没有检测到 `GEMINI_API_KEY`。先 `cp .env.example .env`，再把 key 填进去。
```

不会给你一屏 traceback。哪里缺什么，一行中文说清楚。

</details>

---

## ✨ 功能亮点

<table>
<tr>
<td width="50%" valign="top">

### 🧠 不止转写，是「理解」

普通转写工具到文字就结束了。OpenMy 继续往下走——

- **场景切分**：把一天的碎碎念切成独立对话段
- **角色识别**：自动判断「在跟谁说话」—— AI、朋友、商家、自己
- **蒸馏摘要**：每个场景用一到两句话概括
- **结构化提取**：分桶输出事件、事实、洞察

</td>
<td width="50%" valign="top">

### 📋 日报 + 活跃上下文

不需要手写日记，也不需要 Notion 模板——

- **每日日报**：自动生成，有摘要、有数据、有时间线
- **活跃上下文**：跨天累积的项目、待办、人物关系
- **自动去重**：相同项目不同叫法？自动合并
- **过期机制**：7 天没提的事自动标记 stale

</td>
</tr>
<tr>
<td width="50%" valign="top">

### 🔧 CLI 就是 Agent 接口

OpenMy 的 CLI 不是给人敲的——是给 Agent 调的。

```bash
openmy context --compact    # 注入 prompt
openmy correct merge-project "AI思维" "OpenMy"
openmy agent --recent       # Agent 启动时自动读
```

让你的 AI Agent 每次开口前，先知道「你是谁、在做什么、还差什么」。

</td>
<td width="50%" valign="top">

### 🖥️ 本地优先，数据在你手里

- 所有数据存本地 `data/` 目录
- 服务默认 `127.0.0.1`，不开放外网
- 不是 SaaS，没有账号，没有上传
- API Key 只在本机调用 Gemini

**你的一天，你说了算。**

</td>
</tr>
</table>

---

## 🖼️ 前端工作台

<div align="center">

<img src="docs/images/openmy-quick-start.png" alt="OpenMy 工作台" width="700" />

</div>

打开 `http://127.0.0.1:8420`，你会看到一个本地工作台：

| 视图 | 说明 |
|------|------|
| 📊 **概览** | 当天统计：场景数、字数、时长、角色分布 |
| 📰 **日报** | AI 生成的结构化日报 |
| 🕐 **摘要时间线** | 按时间顺序展示每个场景的蒸馏摘要 |
| 📋 **表格** | 完整场景列表，可展开查看原文 |
| 📈 **图表** | 角色分布、场景时长的可视化 |
| ✏️ **校正** | 纠错词典管理 + 全局搜索替换 |
| ⚙️ **流程** | 一键重跑管线任意阶段 |

---

## 🔬 工作原理

```mermaid
graph LR
    A[🎙️ 音频文件] --> B[转写]
    B --> C[清洗文本]
    C --> D[场景切分]
    D --> E[角色识别]
    E --> F[蒸馏摘要]
    F --> G[结构化提取]
    G --> H[日报生成]
    H --> I[活跃上下文]
    I --> J[🖥️ 本地工作台]

    style A fill:#6366f1,stroke:#4f46e5,color:#fff
    style J fill:#06b6d4,stroke:#0891b2,color:#fff
```

| 阶段 | 做什么 | 怎么做 |
|------|--------|--------|
| **转写** | 音频 → 带时间戳的文字 | Gemini API |
| **清洗** | 去噪音、修标点、补纠错词 | 纯规则引擎，不调 API |
| **场景切分** | 按时间和话题切场景 | 规则 + 语义 |
| **角色识别** | 判断在跟谁说话 | Gemini + Screenpipe 线索 |
| **蒸馏** | 每场景一句话摘要 | Gemini（角色感知） |
| **提取** | 输出事件 / 事实 / 洞察 | Gemini（JSON schema 约束） |
| **日报** | 生成可读的每日报告 | Gemini |
| **上下文** | 跨天累积项目、人物、待办 | 本地聚合 + 去重 |

---

## 🔌 可选：Screenpipe 屏幕上下文

OpenMy 可以接 [Screenpipe](https://github.com/mediar-ai/screenpipe)，给角色识别加额外线索：

```
"你 09:30 在跟 AI 说话" ← 不止因为内容像，还因为当时屏幕上开着 Cursor
```

- **不装也能正常跑**，全部功能不受影响
- 装了之后角色判断更准
- 通过本地 HTTP 接口（`localhost:3030`）读取，不需要改代码

---

## 🤖 给 Agent 开发者

OpenMy 的核心定位：**让 AI Agent 拥有关于「你」的持久记忆。**

```python
# 你的 Agent 启动时：
import subprocess, json

# 1. 拿到用户的活跃上下文
result = subprocess.run(
    ["openmy", "context", "--compact"],
    capture_output=True, text=True
)
user_context = result.stdout

# 2. 注入到 system prompt
system_prompt = f"""你是用户的助手。以下是用户的近期上下文：
{user_context}
"""
```

一行命令，你的 Agent 就知道用户最近在做什么项目、跟谁互动、有哪些待办。

---

## ⚙️ 配置

所有配置集中在 [`src/openmy/config.py`](src/openmy/config.py)。大多数人第一次用不需要改。

<details>
<summary>可调参数一览</summary>

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `GEMINI_MODEL` | `gemini-3.1-flash-lite-preview` | 全局模型 |
| `TRANSCRIBE_TIMEOUT` | 900s | 转写超时 |
| `EXTRACT_TEMPERATURE` | 0.2 | 提取温度 |
| `DISTILL_TEMPERATURE` | 0.2 | 蒸馏温度 |
| `SCREEN_RECOGNITION_ENABLED` | `True` | Screenpipe 开关 |
| `SCREEN_RECOGNITION_API` | `localhost:3030` | Screenpipe 地址 |

</details>

---

## 🧪 开发与测试

```bash
git clone https://github.com/openmy-ai/openmy.git && cd openmy
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python3 -m pytest tests/ -v   # 167 tests, 0 API key needed
```

测试不依赖真实 API Key。没有 `GEMINI_API_KEY` 也能全绿。

---

## 📍 路线图

| 阶段 | 状态 | 内容 |
|------|------|------|
| ~~v0.1 Alpha~~ | ✅ | 核心管线跑通：转写 → 清洗 → 场景 → 角色 → 蒸馏 → 日报 |
| **v0.2 Beta** | 🟢 **当前** | quick-start 入口、前端工作台、纠错词典、结构化提取、活跃上下文 |
| v0.3 | 🔜 | 多语言支持、更智能的跨天上下文、Obsidian 插件 |
| v1.0 | 📋 | 稳定 API、插件系统、多 LLM 后端 |

> 想参与？看 [CONTRIBUTING.md](CONTRIBUTING.md) 或直接开 Issue 聊。

---

## 🆚 这不是什么

| | OpenMy | 纯转写工具 | 日记 App |
|---|---|---|---|
| 转写 | ✅ | ✅ | ❌ |
| 场景切分 & 角色识别 | ✅ | ❌ | ❌ |
| 结构化提取（事件/事实/洞察） | ✅ | ❌ | ❌ |
| 活跃上下文（给 Agent 用） | ✅ | ❌ | ❌ |
| 数据 100% 本地 | ✅ | 看厂商 | 看厂商 |
| 开源 | ✅ | 少数 | 少数 |

**OpenMy 不是更好的转写工具。它是转写之后的事。**

---

## 📂 仓库结构

```
src/openmy/          核心 Python 包（CLI + 9 个服务模块）
├── services/
│   ├── ingest/          音频导入与预处理
│   ├── cleaning/        文本清洗（规则引擎）
│   ├── segmentation/    场景切分
│   ├── roles/           角色识别
│   ├── distillation/    蒸馏摘要
│   ├── extraction/      结构化提取
│   ├── briefing/        日报生成
│   ├── context/         活跃上下文管理
│   └── screen_recognition/  Screenpipe 集成
app/                 本地 Web 工作台
tests/               167 个自动化测试
docs/                设计文档与截图
```

---

## 🤝 参与贡献

欢迎一起建设！详见 [CONTRIBUTING.md](CONTRIBUTING.md)。

简单来说：Fork → 新分支 → 改代码 + 补测试 → `pytest` 全绿 → 提 PR。

---

## 📄 License

[MIT](LICENSE) · 作者：[周瑟夫 (Joseph Zhou)](https://github.com/openmy-ai)

---

<div align="center">

**如果觉得有用，给个 ⭐ 就是最大的支持。**

</div>
