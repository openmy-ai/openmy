<div align="center">

<img src="docs/images/openmy-banner.png" alt="OpenMy" width="800" />

**面向多 Agent 的个人上下文引擎**

把录音、屏幕等个人原始信号处理成可被 Agent 调用、可纠正、可跨天积累的上下文状态。默认推荐 Gemini provider，但系统本体不绑定单一模型供应商。

[![Release](https://img.shields.io/github/v/release/openmy-ai/openmy?style=flat-square&color=blue)](https://github.com/openmy-ai/openmy/releases)
[![MIT](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![Tests](https://img.shields.io/badge/tests-167%20passed-brightgreen?style=flat-square)]()

[English](README.en.md)

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

> 依赖：Python 3.10+、FFmpeg、一个可用的 provider key。默认推荐 Gemini，直接填 `GEMINI_API_KEY` 即可。

### Provider 配置

- 默认推荐：`GEMINI_API_KEY`
- 更通用的配置名：
  - `OPENMY_STT_PROVIDER`
  - `OPENMY_STT_MODEL`
  - `OPENMY_STT_API_KEY`
  - `OPENMY_LLM_PROVIDER`
  - `OPENMY_LLM_MODEL`
  - `OPENMY_LLM_API_KEY`
- 阶段级模型覆盖：
  - `OPENMY_EXTRACT_MODEL`
  - `OPENMY_DISTILL_MODEL`

---

## 🔬 处理流程

```mermaid
graph TD
    A["🎙️ 音频文件"] --> B["转写"]
    B --> C["清洗"]
    C --> D["场景切分"]
    D --> E["角色识别"]
    E --> F["蒸馏摘要"]
    F --> G["结构化提取"]
    G --> H["日报生成"]
    H --> I["活跃上下文"]
    I --> J["🖥️ 每日报告"]

    style A fill:#6366f1,stroke:#4f46e5,color:#fff
    style J fill:#06b6d4,stroke:#0891b2,color:#fff
```

### 每一步做什么

**转写** — 音频转成带时间戳的逐字文本。

**清洗** — 去掉口语噪音（嗯、啊、重复词），修标点，应用纠错词典。纯规则，不调 API。

**场景切分** — 按时间间隔和话题转换，把一整天的文本切成独立的对话段落。

**角色识别** — 判断每段对话在跟谁说话：AI 助手、朋友、商家、宠物、自言自语。结合屏幕上下文提高准确率。

**蒸馏摘要** — 每个场景压缩成一到两句话，保留核心信息，感知角色身份。

**结构化提取** — 从全天内容中分桶提取三类信息：
- 🚀 **事件** — 做了什么、打算做什么
- 📌 **事实** — 确认的信息、数据、结论
- ⚡ **洞察** — 想法、判断、灵感

**日报生成** — 汇总当天所有场景，生成有摘要、有时间线、有统计的每日报告。

**活跃上下文** — 跨天累积项目进展、人物关系、待办事项。7 天没再提到的自动标记过期。

---

## 🤖 接给 Agent

OpenMy 的核心资产不是某个 CLI 壳子，而是稳定的上下文状态和动作契约。

当前推荐的稳定入口：

```bash
openmy skill status.get --json
openmy skill day.get --date 2026-04-08 --json
openmy skill context.get --json
openmy skill day.run --date 2026-04-08 --audio path/to/audio.wav --json
```

兼容入口 `openmy agent` 仍然保留，但后续会逐步退到兼容别名。

---

## 🖼️ 输出效果

<div align="center">
<img src="docs/images/openmy-quick-start.png" alt="OpenMy 报告" width="700" />
</div>

生成的报告包含 7 个视图：

- **概览** — 当天统计：场景数、字数、语音时长、角色分布
- **日报** — 结构化的每日摘要
- **摘要时间线** — 按时间排列每个场景的蒸馏结果
- **场景表格** — 完整场景列表，可展开查看原文
- **图表** — 角色分布和场景时长可视化
- **校正** — 纠错词典管理，支持全局搜索替换
- **流程** — 重跑管线任意阶段

---

## 📍 路线图

- ~~**v0.1**~~ ✅ 核心管线跑通
- **v0.2** 🟢 当前 — quick-start、报告工作台、纠错词典、结构化提取、活跃上下文
- **v0.3** 🔜 多语言、跨天上下文增强、Obsidian 插件
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
src/openmy/
  commands/          CLI / skill 入口
  providers/         STT / LLM provider 边界
  services/
    ingest/            音频导入与预处理
    cleaning/          文本清洗（规则引擎）
    segmentation/      场景切分
    roles/             角色识别
    distillation/      蒸馏摘要
    extraction/        结构化提取
    briefing/          日报生成
    context/           活跃上下文
    screen_recognition/  屏幕上下文
  adapters/
    transcription/    旧转写兼容壳
app/                  报告页面
tests/                自动化测试
```

---

[CONTRIBUTING](CONTRIBUTING.md) · [MIT License](LICENSE) · by [Joseph Zhou](https://github.com/openmy-ai)

<div align="center">

**觉得有用？⭐ 就是最大的支持。**

</div>
