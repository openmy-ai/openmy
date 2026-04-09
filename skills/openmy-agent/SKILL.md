---
name: openmy-agent
description: OpenMy 的 Agent 执行入口。当 Agent 需要读取用户上下文、纠正错误信息、或处理录音数据时触发。这是操作层 skill，产品全貌见 skills/openmy/SKILL.md。
---

# openmy-agent — Agent 执行入口

> 这是 OpenMy 的**操作层** skill，定义 Agent 怎么调命令。
> 产品是什么、架构怎么分层、信源有哪些 → 见 `skills/openmy/SKILL.md`

---

## 🔴 Agent 必读（每次启动时执行）

### 1. 读取用户上下文

```bash
cd ~/Desktop/周瑟夫的上下文
python3 -m openmy context --level 0
```

输出一句话状态摘要。需要更多细节：

```bash
python3 -m openmy context --level 1    # 完整版
python3 -m openmy context --compact    # Markdown 版（可直接注入 prompt）
```

或直接读文件：
```bash
cat data/active_context.compact.md
```

### 2. 检查 stale loops（每次启动都做）

读取 `data/active_context.json` 中的 `rolling_context.open_loops`。
对于每个 open_loop：

- 检查 `last_seen_at` 距今是否超过 **7 天**
- 如果超过 7 天 → **主动问用户**：

```
"老板，这几个事还在开着，帮你确认一下：
 1. [loop.title] — 上次提到是 [last_seen_at]
 2. [loop.title]
 哪个做完了？哪个不想做了？"
```

用户回答后，**立即调用对应命令**：

```bash
# 做完了
python3 -m openmy correct close-loop "待办标题"

# 不想做了 / 不是正经待办
python3 -m openmy correct reject-loop "待办标题"

# 还在做，只是最近没提
python3 -m openmy correct keep-loop "待办标题"
```

### 3. 对话中纠正

在与用户对话过程中，如果发现 active_context 有误：

```bash
# 两个项目其实是一个
python3 -m openmy correct merge-project "AI思维" "OpenMy"

# 这不是独立项目，只是一次性操作
python3 -m openmy correct reject-project "代理配置"

# 这不是重要决策
python3 -m openmy correct reject-decision "中午改吃河南蒸菜"

# 确认/修正人物信息
python3 -m openmy correct confirm-entity "燕子" --relation partner --display-name "老婆"

# 查看所有纠正历史
python3 -m openmy correct list
```

**纠正一次，永久生效。** 下次 `context` 重新生成时自动应用。

---

## CLI 命令速查

| 命令 | 用途 |
|------|------|
| `openmy status` | 列出所有日期及处理状态 |
| `openmy run YYYY-MM-DD --audio file.m4a` | 全流程：音频预处理（去静音/压缩/切块）→ 转写 → 清洗 → 角色 → 蒸馏 → 提取 → 日报 |
| `openmy run YYYY-MM-DD --skip-transcribe` | 跳过转写，复用已有数据 |
| `openmy extract YYYY-MM-DD` | 单独跑结构化提取（intents + facts） |
| `openmy view YYYY-MM-DD` | 终端查看某天概览 |
| `openmy context` | 生成/查看活动上下文 |
| `openmy context --compact` | 输出 Markdown 压缩版 |
| `openmy context --level 0` | 极简一句话状态 |
| `openmy correct <action> <args>` | 纠正活动上下文 |
| `openmy correct list` | 查看纠正历史 |
| `openmy agent recent` | 最近状态（JSON） |
| `openmy agent day YYYY-MM-DD` | 某天数据（JSON） |

> [!IMPORTANT]
> `openmy run --audio` 会自动执行本地音频预处理（去静音/压缩/切块），
> 然后才送 Gemini 转写。**不要**绕过这个流程直接调转写。

## 角色归因体系

| 层级 | 名称 | 逻辑 |
|------|------|------|
| 1 | 亲口说的 | 文本里有明确对象声明 |
| 2 | 关键词命中 | AI术语/商家用语/宠物指令 |
| 3 | 继承上文 | 前面场景定了角色，后面未切换就继承 |
| 4 | 屏幕佐证 | Screenpipe 检测当时在用什么 App |
| 5 | 不确定 | 以上都不够就标不确定 |

## 常见问题

- **转写太慢**：音频管道会自动切块（默认 10 分钟），不需要手动分段
- **Screenpipe 未检测到**：确认 `curl http://localhost:3030/health` 返回 200
- **蒸馏/提取失败**：确认 `GEMINI_API_KEY` 环境变量已设置
- **纠正没生效**：纠正后需要重跑 `openmy context` 重新生成
