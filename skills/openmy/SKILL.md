---
name: openmy
description: Use when Agent needs to understand the user (who they are, what they're doing, what's pending), correct wrong context, or process audio recordings. Triggers on startup context loading, stale loop checking, entity/project corrections, and audio ingestion.
---

# OpenMy — 个人上下文引擎

> OpenMy 是自维护的个人上下文系统。Agent 启动时读它了解用户，对话中发现错误时写回纠正。
>
> **第零铁律：用户永远不碰终端。** CLI 给 Agent 调，前端给用户看。
>
> 产品架构、信源体系、路线图 → 见 `references/architecture.md`

---

## 启动时必做（每次新对话）

### 1. 读取用户上下文

```bash
cd ~/Desktop/周瑟夫的上下文
python3 -m openmy context --level 0       # 一句话摘要
python3 -m openmy context --level 1       # 完整版
python3 -m openmy context --compact       # Markdown（可注入 prompt）
```

或直接读文件：
```bash
cat data/active_context.compact.md
```

### 2. 检查 stale loops

读 `data/active_context.json` → `rolling_context.open_loops`。

对每个 open_loop，检查 `last_seen_at` 是否超过 **7 天**。超过 → 主动问用户：

```
"老板，这几个事还在开着：
 1. [loop.title] — 上次提到是 [last_seen_at]
 哪个做完了？哪个不想做了？"
```

用户回答后立即调用：

```bash
python3 -m openmy correct close-loop "待办标题"     # 做完了
python3 -m openmy correct reject-loop "待办标题"    # 不想做了
```

> 没有 `keep-loop` 命令。用户说"还在做"时不需要操作，保持原样即可。

---

## 对话中纠正

发现 active_context 有误时：

```bash
python3 -m openmy correct merge-project "AI思维" "OpenMy"      # 合并项目
python3 -m openmy correct reject-project "代理配置"             # 不是项目
python3 -m openmy correct reject-decision "中午改吃河南蒸菜"     # 不是决策
python3 -m openmy correct list                                  # 查看纠正历史
```

> `correct` 是自由参数入口（`openmy correct <action> [args...]`），不是 `--flag` 子命令。
> 支持的 action：`typo`、`list`、`close-loop`、`reject-loop`、`merge-project`、`reject-project`、`reject-decision`。

**纠正一次，永久生效。** 下次 `context` 重新生成时自动叠加。

---

## CLI 命令速查

| 命令 | 用途 |
|------|------|
| `openmy status` | 列出所有日期及处理状态 |
| `openmy run YYYY-MM-DD --audio file.m4a` | 全流程：去静音→压缩→切块→转写→清洗→角色→蒸馏→提取→日报 |
| `openmy run YYYY-MM-DD --skip-transcribe` | 跳过转写，复用已有数据 |
| `openmy extract YYYY-MM-DD` | 单独跑结构化提取（intents + facts） |
| `openmy view YYYY-MM-DD` | 终端查看某天概览 |
| `openmy context [--level 0/1] [--compact]` | 生成/查看活动上下文 |
| `openmy correct <action> <args>` | 纠正活动上下文（action 见上方列表） |
| `openmy agent --recent` | 最近状态（Level 0） |
| `openmy agent --day YYYY-MM-DD` | 某天数据 |

## 不要做什么

- **不要**绕过 `openmy run --audio` 直接调转写。音频必须经过本地去静音/压缩/切块预处理
- **不要**直接改 `active_context.json`。所有修正走 `correct` 命令（append-only）
- **不要**改 `scenes.json`、`meta.json` 等原始证据文件。它们是不可变事实
- **不要**在 SKILL.md 里擅自修改产品定位和愿景描述。先给老板看草案和 diff

## 常见问题

| 问题 | 解法 |
|------|------|
| 转写太慢 | 音频管道自动切块（默认 10 分钟），不需要手动分段 |
| Screenpipe 未检测到 | `curl http://localhost:3030/health` 返回 200 |
| 蒸馏/提取失败 | 确认 `GEMINI_API_KEY` 环境变量 |
| 纠正没生效 | 纠正后重跑 `openmy context` |

## 测试

```bash
cd ~/Desktop/周瑟夫的上下文
python3 -m pytest tests/ -v    # 131 tests
```
