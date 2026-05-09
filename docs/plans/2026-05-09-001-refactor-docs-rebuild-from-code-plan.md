---
title: "refactor: OpenMy 仓库文档从代码重建"
type: refactor
status: active
date: 2026-05-09
---

# OpenMy 仓库文档从代码重建

## Summary

仓库文档严重过时（技术状态停在 Phase 3/4，实际已到 Phase 6 + grounded Q&A）。产品方向没变，README 不动。从当前代码出发，把所有技术状态文档对齐到真实代码，CHANGELOG 补完，版本号升到 0.3.0，多语言 README 同步。三天上线。

---

## Problem Frame

OpenMy 从 2026-04-12（v0.2.0）到 2026-04-18 连续 merge 了约 40 个 commit（First-Run Wizard、音频回放 Phase 1-3、Phase 5 字幕审查、Phase 6 Smart Audio Player V2、grounded context Q&A 等），但 CHANGELOG 停在 0.2.0、STATE.md 停在 Phase 3、ROADMAP.md Phase 6 plans 全未标完成。新用户或贡献者看到仓库文档会以为项目只做到一半。

---

## Requirements

- R1. 所有技术状态文档反映 2026-05-09 的真实代码状态
- R2. CHANGELOG 覆盖 0.2.0 之后全部有意义的变化
- R3. 版本号在 pyproject.toml / README / CHANGELOG 一致升到 0.3.0
- R4. CLAUDE.md / AGENTS.md 的 skill 端点和能力描述与当前代码一致
- R5. 6 个语言 README 与中文 README 同步（至少：版本号、能力列表、安装命令）
- R6. 过时的 .planning/ 文档不再出现在仓库根级可见位置

---

## Scope Boundaries

- README.md 产品方向、用户场景、品牌描述不变
- 不改功能代码
- 不新建 STRATEGY.md（产品方向已在 README 中，ARCHITECTURE.md 已覆盖技术状态）
- docs/plans/ 里的旧 plan 文件保留不动（历史记录）

---

## Context & Research

### Relevant Code and Patterns

- `ARCHITECTURE.md` 已在本次会话写好（从代码扫描生成）
- `CLAUDE.md` / `AGENTS.md` 当前 132 行，内容结构清晰但 skill 端点列表可能漏新增
- `CHANGELOG.md` 当前只有 0.2.0 和 0.1.0-alpha 两个版本条目
- `.planning/STATE.md` 引用 Phase 3 completed，实际 Phase 6 已 merge
- `.planning/ROADMAP.md` Phase 6 plans 全 `[ ]`，实际全部完成
- `pyproject.toml` 版本 `0.2.0`

### 40 个待归档 commits（0.2.0 之后的特性）

按类别整理：

**新功能**：
- First-Run Wizard + hash 路由 + upload dropzone
- 音频回放 Phase 1-3（scene audio ref mapping / local audio delivery / scene playback UI）
- Phase 5 字幕审查 V1（selection-first subtitle review overlay）
- Phase 6 Smart Audio Player V2（Silero VAD + 波形 + 字幕动画）
- Grounded context Q&A + homepage recap cards
- 屏幕识别 + agent_instructions 嵌入 health.check
- 周报/月报聚合触发
- install-skills.sh 改进

**修复**：
- 管线质量（场景过滤 / work_sessions 准确率 / briefing 增强）
- 首次 onboarding 路由修复
- context.query 崩溃修复
- 音频 ref 跨 rerun 保持
- 上下文查询英文意图分类子串误判修复

---

## Key Technical Decisions

- 版本号升到 0.3.0（不是 1.0，因为仍有已知 bug 未修）
- .planning/ 文档 mv 到 .planning/archived/ 而非删除（保留历史可查）
- ARCHITECTURE.md 作为新的技术状态单一 source of truth，替代 STATE/ROADMAP/PROJECT 三文件

---

## Implementation Units

### U1. 归档过时的 .planning/ 文档

**Goal:** 把 STATE.md / ROADMAP.md / PROJECT.md / REQUIREMENTS.md 移到 .planning/archived/，不再让新人第一眼看到过时信息。

**Requirements:** R1, R6

**Dependencies:** None

**Files:**
- Move: `.planning/STATE.md` → `.planning/archived/STATE.md`
- Move: `.planning/ROADMAP.md` → `.planning/archived/ROADMAP.md`
- Move: `.planning/PROJECT.md` → `.planning/archived/PROJECT.md`
- Move: `.planning/REQUIREMENTS.md` → `.planning/archived/REQUIREMENTS.md`

**Approach:**
- `mkdir -p .planning/archived && git mv .planning/{STATE,ROADMAP,PROJECT,REQUIREMENTS}.md .planning/archived/`
- 保留 .planning/phases/ 和 .planning/codebase/ 不动（历史 plan 细节，不影响新人导航）

**Test expectation:** none -- 纯文件搬移

**Verification:** `.planning/` 根级只剩 config.json + phases/ + codebase/ + archived/

---

### U2. CHANGELOG 补完 0.3.0

**Goal:** 把 0.2.0 之后约 40 个 commit 归档到 CHANGELOG 的 [0.3.0] 条目。

**Requirements:** R2, R3

**Dependencies:** None

**Files:**
- Modify: `CHANGELOG.md`

**Approach:**
- 在 `## [0.2.0]` 之前插入 `## [0.3.0] - 2026-05-09`
- 按 Features / Fixes / Internal 三类整理
- 功能条目用用户能感受到的语言写（不用 commit message 原文）
- Internal 包含文档重建、worktree 清理等工程治理工作

**Patterns to follow:**
- 现有 CHANGELOG 的 Features / Fixes 分类风格

**Test expectation:** none -- 文档更新

**Verification:** `## [0.3.0]` 条目存在，覆盖了核心功能变化

---

### U3. pyproject.toml + README 版本号升级

**Goal:** 版本号从 0.2.0 升到 0.3.0，保持一致。

**Requirements:** R3

**Dependencies:** U2（CHANGELOG 先写好确认版本号）

**Files:**
- Modify: `pyproject.toml`（version 字段）
- Modify: `README.md`（如果有硬编码版本号）

**Approach:**
- pyproject.toml: `version = "0.3.0"`
- README 用 shield badge 从 GitHub release 动态取版本，可能不用改——确认一下

**Test expectation:** none -- 配置变更

**Verification:** `grep version pyproject.toml` 显示 0.3.0

---

### U4. CLAUDE.md / AGENTS.md 对齐当前代码

**Goal:** 确保 Agent 读到的项目说明反映当前能力（skill 端点、CLI 命令、通信规则）。

**Requirements:** R4

**Dependencies:** None

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`

**Approach:**
- 逐节对比当前 CLAUDE.md 内容和实际代码
- 重点检查：skill 端点清单是否覆盖 18 个 handle_*、CLI 命令是否覆盖 parser.py 的子命令、First-Run Wizard 流程是否记录
- 不改通信规则（已经写得很好）
- 如果 CLAUDE.md 和 AGENTS.md 内容完全一致，考虑让 AGENTS.md 引用 CLAUDE.md 避免双份维护

**Patterns to follow:**
- 现有 CLAUDE.md 的段落风格（给 Agent 读的，不是给人读的）

**Test scenarios:**
- 对比 skill_dispatch.py 的 handle_* 函数列表和文档里的 skill 端点列表
- 对比 parser.py 的 add_parser 列表和文档里的 CLI 命令列表

**Verification:** 文档里列出的每个 skill 端点和 CLI 命令在代码中都存在

---

### U5. 多语言 README 同步

**Goal:** 6 个语言 README（en / fr / it / ja / ko）至少在版本号、能力列表、安装命令上与中文 README 一致。

**Requirements:** R5

**Dependencies:** U3（版本号先定）

**Files:**
- Modify: `README.en.md`
- Modify: `README.fr.md`
- Modify: `README.it.md`
- Modify: `README.ja.md`
- Modify: `README.ko.md`

**Approach:**
- 先 diff 中文 README 与英文 README，找出结构性差异
- 版本号、badge、安装命令直接同步
- 能力列表如果有差异，按中文版更新
- 不做全文重新翻译——只同步结构变化

**Test scenarios:**
- `scripts/check_readme_sync.py` 如果存在就跑一次看结果

**Verification:** `python scripts/check_readme_sync.py` 通过（如果该脚本存在）

---

## Risks & Dependencies

| Risk | Mitigation |
|------|------------|
| 多语言 README 翻译质量 | 只同步结构变化，不做大段重新翻译 |
| CHANGELOG 遗漏重要变化 | 逐条 git log 核对 |

---

## Sources & References

- 已写好的 `ARCHITECTURE.md`（本次会话产出）
- `docs/cleanup/worktree-audit-2026-05-09.md`（codex 产出的 worktree 审计）
- git log `18b543a..7ab7419`（待归档 commits）
