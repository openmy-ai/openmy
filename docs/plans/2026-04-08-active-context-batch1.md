# Active Context Batch 1 实施计划

日期：2026-04-08

## 目标

做出第四层的第一版“总状态卡”：

- 读取现有每日数据
- 兼容新目录格式和老根目录格式
- 生成 `data/active_context.json`
- 生成 `data/active_context.compact.md`
- 在 CLI 中新增 `context` 命令

## 这版故意不做的事

- 不改现有 `status/view/clean/roles/distill/briefing/run/correct`
- 不做复杂的长期衰减逻辑
- 不做人工纠错事件流
- 不做多 Agent 私有游标
- 不做图谱和复杂主题推断

## 数据来源

第一版同时支持两套来源：

1. 新格式：
   - `data/YYYY-MM-DD/scenes.json`
   - `data/YYYY-MM-DD/daily_briefing.json`
2. 老格式：
   - `YYYY-MM-DD.scenes.json`
   - `YYYY-MM-DD.meta.json`
   - `YYYY-MM-DD.md`

## 实现拆分

### 1. 数据模型校验

基于现有 `src/daytape/services/context/active_context.py`：

- 补往返序列化测试
- 确保 `save/load/from_dict/to_json` 可用

### 2. 汇总器 consolidation

新建 `src/daytape/services/context/consolidation.py`，负责：

- 扫描所有可用日期
- 同时兼容新旧路径
- 提取这些高信号内容：
  - 高频互动人物
  - 最近项目
  - 未闭环事项
  - 最近决定
  - 今日重点
  - 基础质量指标
- 生成 `ActiveContext`
- 追加写入 `data/active_context_updates.jsonl`

第一版尽量只用明确字段，不做重推理：

- `key_people_registry`：来自 `scene.role.addressed_to`
- `open_loops`：优先读 `daily_briefing.todos_open`，缺失时回退 `meta.todos`
- `recent_decisions`：优先读 `daily_briefing.decisions`，缺失时回退 `meta.decisions`
- `today_focus`：优先读 `daily_briefing.key_events`，缺失时回退 `meta.events`
- `active_projects`：优先从明确事件/决定文本里提取，不做复杂主题模型

### 3. 展示器 renderer

新建 `src/daytape/services/context/renderer.py`：

- `render_level0(ctx)`：一句话摘要 + 待办数 + 最近变化
- `render_level1(ctx)`：给 CLI 和 Agent 看的压缩文本
- `render_compact_md(ctx)`：保存为 Markdown 文件

### 4. CLI 接入

修改 `src/daytape/cli.py`：

- 新增 `context` 子命令
- 支持：
  - `daytape context`
  - `daytape context --level 0`
  - `daytape context --compact`

## TDD 顺序

1. `test_active_context.py`
   - 先测模型序列化往返
2. `test_consolidation.py`
   - 先测新格式数据
   - 再测老格式回退
   - 再测 `context_seq` 递增和 updates 日志
3. `test_renderer.py`
   - 先测 level0 / level1 / compact 输出
4. `test_cli.py`
   - 补 `context` 命令测试

## 验证命令

```bash
cd /Users/zhousefu/Desktop/周瑟夫的上下文
python3 -m pytest tests/unit/test_active_context.py -v
python3 -m pytest tests/unit/test_consolidation.py -v
python3 -m pytest tests/unit/test_renderer.py -v
python3 -m pytest tests/unit/test_cli.py -v
python3 -m pytest tests -v
python3 -m daytape context
python3 -m daytape context --level 0
python3 -m daytape context --compact
python3 -m json.tool data/active_context.json
```

## 改动边界

只允许修改这些区域：

- `src/daytape/services/context/`
- `src/daytape/cli.py`
- `tests/unit/`
- `docs/plans/2026-04-08-active-context-batch1.md`

不碰：

- `handoff.md`
- 前端
- 现有 briefing / roles / server 行为
