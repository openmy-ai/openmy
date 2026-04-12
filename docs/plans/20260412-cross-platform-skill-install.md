# Cross-Platform Skill Installation

> Codex 执行计划。CC 出品，2026-04-12。
> 参考来源：obra/superpowers 仓库的跨平台安装架构。

## 背景

OpenMy 的 `skills/` 目录放在项目根目录，但四大 AI 编码平台都不自动扫描这个路径。导致新机器上 Agent 读不到 Skill 文件，输出"装机报告"式的回复。

需要做的事：让 Clone 仓库的人（或 Agent）能一键把 Skills 装到自己的编码工具里。

## 任务清单（按顺序执行）

### Task 1: 创建 `.codex/INSTALL.md`

创建文件 `.codex/INSTALL.md`，内容如下：

```markdown
# Installing OpenMy Skills for Codex

Enable OpenMy skills in Codex via native skill discovery. Clone and symlink.

## Prerequisites

- Git

## Installation

1. **Clone the OpenMy repository (if not already cloned):**
   ```bash
   git clone https://github.com/openmy-ai/openmy.git ~/.codex/openmy
   ```

2. **Create the skills symlink:**
   ```bash
   mkdir -p ~/.agents/skills
   ln -s ~/.codex/openmy/skills ~/.agents/skills/openmy
   ```

   **Windows (PowerShell):**
   ```powershell
   New-Item -ItemType Directory -Force -Path "$env:USERPROFILE\.agents\skills"
   cmd /c mklink /J "$env:USERPROFILE\.agents\skills\openmy" "$env:USERPROFILE\.codex\openmy\skills"
   ```

3. **Restart Codex** (quit and relaunch the CLI) to discover the skills.

## If You Already Have the Repo Locally

If you cloned OpenMy somewhere else (e.g. for development), just symlink from there:

```bash
mkdir -p ~/.agents/skills
ln -s /path/to/your/openmy/skills ~/.agents/skills/openmy
```

## Verify

```bash
ls -la ~/.agents/skills/openmy
```

You should see a symlink pointing to the OpenMy skills directory.

## Updating

```bash
cd ~/.codex/openmy && git pull
```

Skills update instantly through the symlink.

## Uninstalling

```bash
rm ~/.agents/skills/openmy
```

Optionally delete the clone: `rm -rf ~/.codex/openmy`.
```

验证：文件存在且 Markdown 格式正确。

---

### Task 2: 创建 `gemini-extension.json`

创建文件 `gemini-extension.json`（项目根目录），内容如下：

```json
{
  "name": "openmy",
  "description": "Personal context engine skills: process audio, manage context, correct transcripts, review daily status",
  "version": "0.2.0",
  "contextFileName": "GEMINI.md"
}
```

验证：JSON 合法。

---

### Task 3: 创建项目级 `GEMINI.md`

创建文件 `GEMINI.md`（项目根目录），内容如下：

```markdown
@./skills/openmy/SKILL.md
@./skills/openmy/references/routing-rules.md
```

就这两行，不多不少。这个文件的作用是让 Gemini CLI / Antigravity 在项目内工作时自动引用核心 Skill。

验证：文件存在，只有两行。

---

### Task 4: 创建 `CLAUDE.md`

创建文件 `CLAUDE.md`（项目根目录），内容如下：

```markdown
# OpenMy — Project Instructions

OpenMy is a **personal context engine**. It processes existing audio recordings into structured daily context.
It is NOT a recording app, NOT a note app, NOT a generic chat wrapper.

## Communication Rules (MANDATORY)

When presenting results to users:
- Talk like a human assistant, not a developer tool.
- Use plain language. Avoid jargon like "LLM", "provider", "API" unless you explain them immediately.
- Never show raw file paths. Say "your profile is saved" instead of a full path.
- Never dump JSON. Read it and summarize it in plain language.
- Never ask users to type terminal commands. Run the commands yourself.
- Never tell users to open a terminal or check logs. All status updates happen in the chat.
- Never go silent. If a command takes more than 30 seconds, give an update.
- End with a question or suggestion, not a status dump.

## What OpenMy Is NOT

- It is NOT a microphone recording tool. Do not focus on microphone setup, device listing, or live recording.
- When users mention a device (DJI Mic, phone, etc.), assume they mean **existing recordings already saved on disk**.
- Do NOT start live recording unless the user explicitly says they want to record NOW.

## First-Time Setup Flow

1. Start with `openmy skill health.check --json`
2. Auto-detect profile (timezone, language) — do NOT ask the user, just set it
3. Ask which STT engine to use — this is the ONE question you must ask
4. Initialize vocab with `openmy skill vocab.init --json`
5. Help locate the first audio file
6. Process it with `openmy skill day.run`
7. Present results in plain language

## API Keys Are Optional

Local engines (`faster-whisper`, `funasr`) work without any key.
`GEMINI_API_KEY` is only needed for distillation/extraction — and even then, the agent can do it manually.
**Never tell the user they must configure an API key before processing audio.**

## Full Skill Reference

For the complete routing map, action contracts, and sub-skill documentation, see:
- `skills/openmy/SKILL.md` — Router skill with all rules
- `skills/openmy/references/action-contracts.md` — Stable command boundary
- `skills/openmy/references/routing-rules.md` — When to use which sub-skill

## Build & Test

```bash
pip install -e .
uvx ruff check .
python3 -m pytest tests/ -v
```
```

验证：文件存在，Markdown 格式正确。

---

### Task 5: 创建 `AGENTS.md` 作为 `CLAUDE.md` 的 symlink

```bash
cd /path/to/openmy   # 项目根目录
ln -s CLAUDE.md AGENTS.md
```

**注意：** 这是一个 **symbolic link**，不是复制。学 Superpowers 的做法：一份内容，两个入口（Codex 读 AGENTS.md，Claude Code 读 CLAUDE.md），永远不会不同步。

验证：
```bash
file AGENTS.md
# 应该输出: AGENTS.md: symbolic link to CLAUDE.md
```

---

### Task 6: 创建 `scripts/install-skills.sh`

创建文件 `scripts/install-skills.sh`，内容如下：

```bash
#!/usr/bin/env bash
set -euo pipefail

# OpenMy Skill Installer
# Detects installed AI coding tools and symlinks OpenMy skills into them.
# Usage: bash scripts/install-skills.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
SKILLS_SRC="$PROJECT_ROOT/skills"

echo "🔍 Detecting installed AI coding tools..."
echo ""

installed=0
skipped=0

link_skills() {
  local platform="$1"
  local target_dir="$2"

  mkdir -p "$target_dir"

  for skill_dir in "$SKILLS_SRC"/openmy*; do
    [ -d "$skill_dir" ] || continue
    local skill_name
    skill_name="$(basename "$skill_dir")"
    local link_path="$target_dir/$skill_name"

    if [ -L "$link_path" ]; then
      echo "  ✅ $skill_name (already linked)"
    elif [ -d "$link_path" ]; then
      echo "  ⚠️  $skill_name (directory exists, not a link — skipped)"
      ((skipped++))
    else
      ln -s "$skill_dir" "$link_path"
      echo "  🔗 $skill_name → linked"
      ((installed++))
    fi
  done
}

# Claude Code
if [ -d "$HOME/.claude" ]; then
  echo "📎 Claude Code detected"
  link_skills "Claude Code" "$HOME/.claude/skills"
  echo ""
else
  echo "⏭  Claude Code — not installed (~/.claude not found)"
fi

# Codex (uses ~/.agents/skills per native skill discovery)
if [ -d "$HOME/.codex" ]; then
  echo "📦 Codex detected"
  # Codex native discovery uses ~/.agents/skills/
  link_skills "Codex" "$HOME/.agents/skills"
  echo ""
else
  echo "⏭  Codex — not installed (~/.codex not found)"
fi

# Gemini CLI / Antigravity
if [ -d "$HOME/.gemini" ]; then
  echo "💎 Gemini CLI / Antigravity detected"
  link_skills "Gemini" "$HOME/.gemini/skills"
  echo ""
else
  echo "⏭  Gemini CLI / Antigravity — not installed (~/.gemini not found)"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if [ $installed -gt 0 ]; then
  echo "✅ Done — linked $installed skill(s)"
elif [ $skipped -gt 0 ]; then
  echo "⚠️  Done — $skipped skill(s) skipped (directories already exist)"
else
  echo "✅ All skills already in place"
fi
echo "💡 Restart your AI tool to pick up the changes"
```

然后设置可执行权限：
```bash
chmod +x scripts/install-skills.sh
```

验证：`bash scripts/install-skills.sh` 能正常运行（至少检测到 Gemini）。

---

### Task 7: 修改 `README.md` — 补安装命令

在 README.md 中找到 `### Install Skills for Your Agent` 这一段（约第 134 行），把现有内容替换为以下内容（保留原有的 skill 目录列表，在前面加上安装方式）：

```markdown
### Install Skills for Your Agent

#### 一键安装（所有平台）

```bash
bash scripts/install-skills.sh
```

自动检测你安装了哪些 AI 工具（Claude Code / Codex / Gemini CLI / Antigravity），把 Skills 链接过去。

#### 分平台安装

**Codex** — 告诉 Codex：
> Fetch and follow instructions from https://raw.githubusercontent.com/openmy-ai/openmy/refs/heads/main/.codex/INSTALL.md

**Gemini CLI** —
```bash
gemini extensions install https://github.com/openmy-ai/openmy
```

**Claude Code** — 克隆仓库后 CLAUDE.md 自动生效，或手动链接：
```bash
bash scripts/install-skills.sh
```

#### Skill 目录
```

然后保留原有的 skill 目录列表不变。

验证：README.md 格式正确，新增内容在正确位置。

---

### Task 8: 修改 `skills/openmy/SKILL.md` — 加强 frontmatter description

把 frontmatter 的 description 从：

```yaml
description: Router skill for OpenMy tasks. Use it to choose the right sub-skill, enforce command boundaries, and apply onboarding or follow-up patterns.
```

改为：

```yaml
description: >
  Use when the task involves OpenMy data, audio processing, transcription,
  daily context, corrections, vocabulary, profile setup, onboarding, or
  first-time setup. Routes to the correct sub-skill and enforces
  communication style (plain language, no jargon, no file paths).
```

验证：YAML frontmatter 仍然合法。

---

### Task 9: 更新 `.gitignore`

确认 `.gitignore` 里没有排除 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md`、`gemini-extension.json`。如果有，去掉。

验证：`git status` 能看到新增的文件。

---

## 完成标准

1. 所有文件创建完毕
2. `AGENTS.md` 是 `CLAUDE.md` 的 symlink（`file AGENTS.md` 确认）
3. `scripts/install-skills.sh` 可执行
4. `python3 -m pytest tests/ -v` 全绿（确认没有破坏现有功能）
5. `uvx ruff check .` 通过
6. `git diff --stat` 显示新增文件列表合理

## 不要做的事

- **不要移动 `skills/` 目录**——它是 OpenMy 文档的一部分
- **不要修改任何 Python 代码**——这次只改 Markdown 和 Shell
- **不要修改 `.env` 或 `.env.example`**
- **不要修改任何测试文件**
- **AGENTS.md 不要复制内容，必须是 symlink**
