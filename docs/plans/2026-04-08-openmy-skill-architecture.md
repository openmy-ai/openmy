# OpenMy Skill 架构重写

## 目标
在不改任何功能的前提下，把 OpenMy 现有“能跑的命令集合”重新包装成一套符合 `writing-skills` 标准的 Skill 外壳，让未来的 Agent 能更容易发现、触发和正确使用它。

## 审阅结论

### 当前基线问题
1. 仓库里没有正式 `SKILL.md`，Agent 缺少可发现入口。
2. 对外说明仍以 README 和 CLI 帮助为主，强调的是产品/网页，不是 Agent 触发条件。
3. 默认入口不唯一，`run / view / context / correct` 都并列暴露，新 Agent 不知道先做哪一步。
4. 纠偏动作已经能跑，但调用方式还是维护者视角，用户说“这条不重要”时，Agent 还需要自己补一层翻译。

### 这次只做什么
- 新增一套标准 Skill 文档架构
- 把真实命令入口、适用场景、常见误用收拢到一份 `SKILL.md`
- 记录当前无 Skill 时的基线失败点，作为后续继续收口的依据

### 这次不做什么
- 不改 CLI 行为
- 不改 README 文案
- 不改任何功能代码
- 不改 tests

## 目标目录结构

```text
skills/
  openmy-agent/
    SKILL.md
    BASELINE.md
```

## 设计原则
1. `description` 只写“什么时候该用”，不写流程摘要。
2. Skill 默认服务 Agent，不服务终端熟练用户。
3. 默认动作顺序必须清楚：
   - 新音频 → `run`
   - 看某天 → `view`
   - 看最近状态 → `context`
   - 纠偏 → `correct ...` 后再 `context`
4. 文档必须直接承认当前边界：
   - 现在处理的是文件，不是实时麦克风流
   - 纠偏仍然是命令形态，还没有完全收成对话式

## 验收标准
1. 新增 `skills/openmy-agent/SKILL.md`
2. `SKILL.md` 含合法 frontmatter，`name` 只用字母数字连字符，`description` 以 “Use when...” 开头
3. Skill 中明确覆盖四类触发：
   - 新音频导入
   - 某天查看
   - 最近状态查看
   - 误判纠偏
4. 新增 `skills/openmy-agent/BASELINE.md` 记录当前基线失败点
5. 不改 `src/`、`app/`、`tests/` 任何功能代码
