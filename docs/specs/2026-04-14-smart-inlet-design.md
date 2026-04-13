# OpenMy 智能入口设计

**Date:** 2026-04-14
**Status:** Approved
**Scope:** 转写提示词定制 + 多源 Inbox + 设备自动检测

---

## 概述

让 OpenMy 的输入从"用户手动给文件路径"变成"插上设备就自动跑"。
四个模块协同工作，从用户定制到设备检测形成完整链路。

## 模块 1：问卷式 Prompt 定制

### 触发时机
整合进 `openmy-profile-init` skill，首次安装时引导。

### 问卷内容
```
Q1: 你主要录什么？（多选）
  ○ 工作会议 / 头脑风暴
  ○ 个人灵感 / 碎碎念
  ○ 学习笔记 / 听课
  ○ 日常闲聊 / 生活记录

Q2: 你主要说什么语言？
  ○ 中文为主
  ○ 英文为主
  ○ 中英混合

Q3: 有没有经常提到的人名/产品名/术语？
  [填写，逗号分隔] → 写入 vocab.txt
```

### 输出
生成 `~/.openmy/prompt_profile.json`：
```json
{
  "scene_types": ["brainstorm", "personal"],
  "language": "zh",
  "vocab_terms": "OpenMy, Screenpipe, Claude Code",
  "transcription_rules": [
    "完整逐字转写",
    "保留碎片化想法，不要过度整理",
    "中英混杂时保留原语言"
  ]
}
```

### 用户可控性
- 可跳过问卷，使用默认配置
- `openmy skill profile.set --prompt-profile` 随时修改
- 直接编辑 `prompt_profile.json` 也行（高级用户）

---

## 模块 2：转写提示词统一

### 问题
当前只有 Gemini 引擎有 9 条转写规则，其他 5 个引擎裸跑或只传词汇表。

### 方案
新建 `src/openmy/providers/stt/prompt_builder.py`：

```python
def build_transcription_prompt(profile: dict, engine: str) -> dict:
    """根据用户 profile 和引擎能力生成对应格式的 prompt"""

    # 基础规则（所有引擎共享）
    base_rules = generate_rules(profile)
    vocab = profile.get("vocab_terms", "")

    return {
        "gemini": full_prompt(base_rules, vocab),        # 完整 prompt 文本
        "faster-whisper": initial_prompt(base_rules, vocab),  # 精简版
        "groq": initial_prompt(base_rules, vocab),        # 精简版
        "funasr": hotword_list(vocab),                    # hotword 列表
        "deepgram": keyword_list(vocab),                  # keywords
        "dashscope": None,                                # 不支持
    }[engine]
```

### 规则生成逻辑
根据 `scene_types` 生成不同规则：
- `brainstorm` → "保留碎片化想法，不要过度整理"
- `meeting` → "识别多人对话，区分发言者"
- `learning` → "保留术语原文，标注不确定的词"
- `personal` → "保留语气词，不过滤口语化表达"

### 引擎能力矩阵

| 引擎 | 能接受的格式 | 当前状态 | 改后 |
|------|------------|---------|------|
| Gemini | 完整 prompt 文本 | ✅ 9条规则 | ✅ profile 驱动 |
| faster-whisper | initial_prompt 字符串 | ❌ 只有词汇 | ✅ 精简规则+词汇 |
| Groq | prompt 字符串 | ❌ 忽略了 | ✅ 精简规则+词汇 |
| FunASR | hotword 字符串 | ✅ 有词汇 | ✅ 保持 |
| Deepgram | keywords 数组 | ❌ 忽略了 | ✅ 词汇列表 |
| Dashscope | 不支持 | — | — |

---

## 模块 3：多源 Inbox

### 目录结构
```
~/.openmy/inbox/              ← 主入口
~/.openmy/inbox/processed/    ← 处理完的文件移到这里
~/.openmy/inbox.conf          ← 额外监听目录配置
```

### 支持的输入类型

| 类型 | 扩展名 | 处理方式 | 场景类型 |
|------|--------|---------|---------|
| 音频 | .wav .mp3 .m4a .flac .ogg | 现有转写 pipeline | audio |
| 文章链接 | .url .webloc | 抓取正文 → 提取要点 | article |
| 文本笔记 | .txt .md | 直接作为内容 | note |
| 截图 | .png .jpg .jpeg | OCR 提取文字 | screenshot |

### 处理流程
```
新文件到达 inbox/
  → 按扩展名分类
  → 调对应处理链
  → 生成场景数据（统一 schema）
  → 追加到当天时间线
  → 移动到 inbox/processed/
```

### 场景数据扩展
```json
{
  "source_type": "audio|article|note|screenshot",
  "source_file": "原始文件名",
  "captured_at": "2026-04-14T10:30:00+08:00",
  "content": "处理后的文字内容",
  "metadata": {
    "url": "https://...",
    "word_count": 1200,
    "duration_seconds": 180
  }
}
```

### 额外监听目录
`~/.openmy/inbox.conf`：
```
# 每行一个目录路径
~/Library/Mobile Documents/com~apple~VoiceMemos/Recordings/
/Volumes/DJI_MIC/RECORD/
```

### 命令
- `openmy inbox watch` — 前台运行监听（调试用）
- `openmy inbox watch --daemon` — 后台守护进程
- `openmy inbox add <file>` — 手动添加单个文件
- `openmy inbox status` — 查看监听状态和队列

---

## 模块 4：设备自动检测 + 反馈

### 检测机制
macOS 使用 `diskutil` + `fswatch` 监听 `/Volumes/` 变化。
设备插入时自动匹配已知设备签名。

### 已知设备签名表
```json
{
  "devices": [
    {"name": "DJI Mic", "mount_pattern": "DJI*", "audio_path": "RECORD/", "formats": ["wav"]},
    {"name": "Sony ICD", "mount_pattern": "IC RECORDER*", "audio_path": "VOICE/", "formats": ["mp3"]},
    {"name": "Zoom H1n", "mount_pattern": "ZOOM*", "audio_path": "STEREO/", "formats": ["wav"]},
    {"name": "Generic", "mount_pattern": "*", "audio_path": "/", "formats": ["wav", "mp3", "m4a"]}
  ]
}
```

用户可以在 `~/.openmy/devices.json` 添加自定义设备。

### 反馈机制（三个点）

**1. 开始反馈：**
```
macOS 通知：
  标题：OpenMy
  内容：检测到 DJI Mic，发现 3 段新录音，开始处理...
```

**2. 完成反馈：**
```
macOS 通知：
  标题：OpenMy
  内容：3 段录音已处理完成，日报已更新。
  按钮：[查看日报]
```

**3. 错误反馈：**
```
macOS 通知：
  标题：OpenMy
  内容：处理第 2 段时出错：音频文件损坏。
  按钮：[查看详情]
```

### macOS 通知实现
使用 `osascript` 发送通知（零依赖）：
```bash
osascript -e 'display notification "3 段录音已处理" with title "OpenMy"'
```

### 自启动
提供 `openmy inbox install-daemon` 命令，生成 macOS launchd plist：
- 开机自启动
- USB 设备挂载时唤醒
- 崩溃自动重启

---

## 模块 5：实时进度面板（留存关键）

### 为什么必须做

转写一段 20 分钟的录音需要 10-20 分钟。用户盯着一个没反应的终端/Agent，不知道是卡了还是在跑。**用过一次就卸了。**

这不是"加个进度条"能解决的。需要一个实时可视化面板，让用户随时知道：
- 在干什么
- 干到哪了
- 还要多久
- 出了什么问题

### 位置

复用现有 Web UI（8420 端口），新增 `/progress` 页面。所有入口自动跳转：
- `openmy quick-start` → 处理开始后自动打开浏览器
- `inbox watch` 自动处理 → macOS 通知里点"查看"跳转
- Agent 调 skill → 返回面板 URL，Agent 告诉用户"打开这个看进度"

### 面板布局

```
┌─────────────────────────────────────────┐
│  OpenMy — 正在处理 DJI_0042.wav         │
│                                          │
│  ████████████░░░░░░░  60%  12:30 / 20:00│
│                                          │
│  ✅ 1/4 转写    02:30  "检测到 3 段对话"  │
│  ✅ 2/4 清洗    01:15  "去掉 47% 噪音"   │
│  🔄 3/4 场景切分 进行中...               │
│  ⬜ 4/4 蒸馏    等待中                   │
│                                          │
│  📋 实时日志（最新 3 条）                 │
│  10:32:15  切分第 2 个场景，时长 4:20     │
│  10:31:42  发现角色切换，标记新场景       │
│  10:31:10  清洗完成，保留 1,247 字        │
│                                          │
│  [暂停]  [取消]  [跳过当前步骤]           │
└─────────────────────────────────────────┘
```

### 前端 UI 设计要求

1. **阶段可视化**：每个阶段独立显示，完成了打勾 ✅，在跑的转圈 🔄，没开始的灰着 ⬜
2. **人话结果**：不是"完成"，是"去掉了 47% 噪音"、"检测到 3 段对话"
3. **预估剩余时间**：根据文件大小和引擎速度算 ETA
4. **实时日志滚动**：最新日志在上面，出错立刻变红
5. **可操作按钮**：暂停 / 取消 / 跳过当前步骤（比如蒸馏卡了可以跳过，先看转写结果）
6. **自动刷新**：1 秒轮询 `/api/pipeline/jobs/{job_id}`，不用手动刷

### 后端改动

**现有基础设施**：`JobRunner` 已经有 `set_step()`、`log()`、`add_artifact()`。

需要扩展的字段：
```python
# 在 job payload 里新增：
{
    "steps": [
        {
            "name": "transcribe",
            "label": "转写",
            "status": "done|running|pending|skipped",
            "started_at": "...",
            "finished_at": "...",
            "duration_seconds": 150,
            "result_summary": "检测到 3 段对话",  # 人话
        },
        ...
    ],
    "progress_pct": 60,          # 总进度百分比
    "eta_seconds": 450,          # 预估剩余秒数
    "source_file": "DJI_0042.wav",
    "source_size_bytes": 52428800,
    "can_pause": true,
    "can_skip": true,
}
```

新增 API：
- `POST /api/pipeline/jobs/{job_id}/pause` — 暂停
- `POST /api/pipeline/jobs/{job_id}/resume` — 恢复
- `POST /api/pipeline/jobs/{job_id}/skip` — 跳过当前步骤
- `POST /api/pipeline/jobs/{job_id}/cancel` — 取消

### Pipeline 阶段定义

| # | 阶段 | 说明 | 典型耗时 |
|---|------|------|---------|
| 1 | 转写 | 音频 → 文字 | 文件时长 × 0.3~1.0 |
| 2 | 清洗 | 去噪、去重复、纠错 | 5~15 秒 |
| 3 | 场景切分 | 按话题/角色分段 | 10~30 秒 |
| 4 | 蒸馏 | 生成摘要和要点 | 15~60 秒 |

ETA 算法：
- 转写阶段：根据 `source_size_bytes / 引擎历史速率`
- 后续阶段：根据 `转写产出字数 × 历史系数`
- 首次运行没有历史数据时显示"预估中…"

---

## 不做的事

- **不做实时录音** — OpenMy 处理已有录音，不是录音 App
- **不做云同步** — 数据留本地，用户自己选是否用 iCloud
- **不做 Android** — 先把 macOS + iPhone 做透
- **不做 Windows 设备检测** — Windows 用户先用手动 inbox add

---

## 实现顺序

1. **进度面板前端** + JobRunner steps 扩展（用户留存关键，第一优先）
2. prompt_builder.py + profile 问卷（无新依赖，改现有代码）
3. inbox watch（用已有 watchdog 依赖）
4. 设备检测 + macOS 通知（新功能，但零依赖）
5. Siri 快捷指令（文档 + .shortcut 文件，不是代码）
6. inbox.conf + devices.json 自定义（配置文件）

## 测试策略

- 单元测试：prompt_builder 各引擎输出格式
- 单元测试：inbox 文件类型检测和路由
- 集成测试：inbox watch → 处理 → 场景生成
- 手动验证：DJI Mic 插拔 → 通知 → 处理
- **单元测试：JobRunner steps 字段正确流转**
- **单元测试：进度百分比和 ETA 计算**
- **浏览器测试：进度面板轮询刷新 + 暂停/取消操作**
- **端到端：从 inbox 投入文件到进度面板显示完成**
