<div align="center">

<img src="docs/images/openmy-banner.png" alt="OpenMy" width="800" />

**一段音频 → 一整天的结构化上下文**

[![Release](https://img.shields.io/github/v/release/openmy-ai/openmy?style=flat-square&color=blue)](https://github.com/openmy-ai/openmy/releases)
[![MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-167%20passed-brightgreen?style=flat-square)]()

[快速开始](#-快速开始) · [English](README.en.md)

</div>

---

## ⚡ 快速开始

```bash
git clone https://github.com/openmy-ai/openmy.git && cd openmy
python3 -m venv .venv && source .venv/bin/activate
pip install .
echo "GEMINI_API_KEY=你的key" > .env
openmy quick-start path/to/your-audio.wav
```

浏览器自动打开 `http://127.0.0.1:8420`，展示你的第一份日报。

缺 FFmpeg / Python 版本不对 / 没配 Key？CLI 会用中文一行说清楚怎么修，不会给你一屏 traceback。

---

## 🧠 不止转写

大多数工具到文字就结束了。OpenMy 继续往下走：

- **场景切分** — 一天的碎碎念切成独立对话段
- **角色识别** — 自动判断在跟谁说话：AI、朋友、商家、自己
- **蒸馏摘要** — 每个场景一到两句话概括
- **结构化提取** — 事件、事实、洞察分桶输出
- **日报生成** — 有摘要、有数据、有时间线
- **活跃上下文** — 跨天累积的项目、待办、人物，7 天没提自动标 stale

**OpenMy 不是更好的转写工具，是转写之后的事。**

---

## 🔬 工作流程

```mermaid
graph LR
    A[🎙️ 音频] --> B[转写]
    B --> C[清洗]
    C --> D[场景切分]
    D --> E[角色识别]
    E --> F[蒸馏摘要]
    F --> G[结构化提取]
    G --> H[日报]
    H --> I[活跃上下文]
    I --> J[🖥️ 工作台]

    style A fill:#6366f1,stroke:#4f46e5,color:#fff
    style J fill:#06b6d4,stroke:#0891b2,color:#fff
```

清洗阶段是纯规则引擎，不调 API。其余阶段使用 Gemini，模型和参数集中在 [`config.py`](src/openmy/config.py)。

---

## 🖥️ 本地工作台

<div align="center">
<img src="docs/images/openmy-quick-start.png" alt="OpenMy 工作台" width="700" />
</div>

打开 `http://127.0.0.1:8420`：概览、日报、摘要时间线、场景表格、图表、校正词典、流程重跑。

所有数据存本地 `data/`，服务默认 `127.0.0.1`，不开外网，不是 SaaS。

---

## 🤖 给 Agent 开发者

OpenMy 的 CLI 是给 Agent 调的，不是给人敲的：

```bash
openmy context --compact      # 输出 Markdown，直接注入 system prompt
openmy agent --recent         # Agent 启动时自动读
openmy correct merge-project "AI思维" "OpenMy"  # 发现上下文有误，一条命令纠正
```

一行命令，你的 Agent 就知道用户最近在做什么、跟谁互动、还差什么。

---

## 📍 路线图

- ~~**v0.1**~~ ✅ 核心管线跑通
- **v0.2** 🟢 当前 — quick-start、前端工作台、纠错词典、结构化提取、活跃上下文
- **v0.3** 🔜 多语言、更智能的跨天上下文、Obsidian 插件
- **v1.0** 📋 稳定 API、插件系统、多 LLM 后端

---

## 🧪 开发

```bash
pip install -e .
python3 -m pytest tests/ -v   # 167 tests，不需要 API key
```

---

## 📂 仓库结构

```
src/openmy/           CLI + 9 个服务模块
  services/
    ingest/            音频导入
    cleaning/          文本清洗（规则引擎）
    segmentation/      场景切分
    roles/             角色识别
    distillation/      蒸馏摘要
    extraction/        结构化提取
    briefing/          日报生成
    context/           活跃上下文
    screen_recognition/  屏幕上下文
app/                  本地 Web 工作台
tests/                167 个测试
```

---

[CONTRIBUTING](CONTRIBUTING.md) · [MIT License](LICENSE) · by [Joseph Zhou](https://github.com/openmy-ai)

<div align="center">

**觉得有用？⭐ 就是最大的支持。**

</div>
