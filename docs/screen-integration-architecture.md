# Screen Integration Architecture

Date: 2026-04-10
Status: implementation design for OpenMy screen-context mainline overhaul

## 1. 设计目标

把屏幕能力从“角色 hints 小外挂”升级为 OpenMy 的第二主信源。

新的核心定义：

- 语音回答：我说了什么
- 屏幕回答：我当时在做什么、看什么、处理什么、卡在哪个界面、和哪个系统交互

这两个信源必须在同一条主链内协同工作：

- 场景对齐
- 角色识别
- 蒸馏
- 结构化提取
- 日报
- active_context
- 纠错
- 完成候选 / 状态闭环

## 2. 命名与产品口径

产品内统一使用以下术语：

- 屏幕上下文
- 屏幕信号
- 屏幕记录
- 屏幕证据

不再在用户可见区域出现：

- `Screenpipe`

允许保留第三方名称的位置：

- `README`
- `ACKNOWLEDGEMENTS`
- `NOTICE`
- `THIRD_PARTY_NOTICES.md`

## 3. 模块拆分

新增目录：

- `src/openmy/services/screen_recognition/provider.py`
- `src/openmy/services/screen_recognition/sessionize.py`
- `src/openmy/services/screen_recognition/privacy.py`
- `src/openmy/services/screen_recognition/align.py`
- `src/openmy/services/screen_recognition/enrich.py`
- `src/openmy/services/screen_recognition/summary.py`
- `src/openmy/services/screen_recognition/settings.py`

### 3.1 provider.py

职责：

- 对底层屏幕服务做统一封装
- 负责健康检查、配置判断、可用性探测
- 负责原始查询入口：
  - OCR events
  - activity summary
  - elements
  - memories
- 返回 OpenMy 自己的稳定结构，而不是把 adapter 原样泄漏到上层

### 3.2 sessionize.py

职责：

- 把原始 OCR / element 事件整理成 screen session / activity block
- 聚合同一应用、窗口、域名、连续时段
- 生成：
  - 主应用
  - 主窗口
  - 主域名
  - frame 引用
  - 初始 activity tags

### 3.3 privacy.py

职责：

- 在 OpenMy 本地做第二层隐私策略
- 敏感场景判断
- 内容摘要化 / 脱敏 / 丢弃
- 用户排除规则生效

### 3.4 align.py

职责：

- 把语音 scene 与屏幕 session 做时段对齐
- 解决一对多 / 多对一重叠
- 输出 scene 级对齐结果和置信度

### 3.5 enrich.py

职责：

- 把屏幕证据正式写回 scene
- 不只写 `role_hint`
- 生成 scene 级：
  - tags
  - summary
  - conflict
  - task signal
  - completion candidates

### 3.6 summary.py

职责：

- 把一段屏幕活动压缩成面向人和 LLM 可读的摘要
- 不把整屏 OCR 填回 transcript 主文本
- 输出给 distill / extract / briefing / context 使用

### 3.7 settings.py

职责：

- 屏幕参与策略解释与加载
- 默认值
- 用户开关
- 排除应用 / 域名 / 窗口关键字
- 保留期 / 摘要化策略

## 4. 核心数据模型

### 4.1 新的 scene 级屏幕证据结构

升级 `src/openmy/domain/models.py`：

- 保留兼容字段 `screen_sessions`
- 新增正式字段 `screen_context`

建议结构：

```python
@dataclass
class ScreenFrameRef:
    frame_id: int = 0
    timestamp: str = ""


@dataclass
class ScreenCompletionCandidate:
    kind: str = ""
    label: str = ""
    confidence: float = 0.0
    evidence: str = ""
    source_session_id: str = ""


@dataclass
class ScreenEvidence:
    session_id: str = ""
    app_name: str = ""
    window_name: str = ""
    url_domain: str = ""
    start_time: str = ""
    end_time: str = ""
    summary: str = ""
    tags: list[str] = field(default_factory=list)
    task_signal: str = ""
    sensitive: bool = False
    summary_only: bool = False
    frame_refs: list[ScreenFrameRef] = field(default_factory=list)


@dataclass
class ScreenContext:
    enabled: bool = False
    participation_mode: str = "off"
    aligned: bool = False
    summary: str = ""
    primary_app: str = ""
    primary_window: str = ""
    primary_domain: str = ""
    tags: list[str] = field(default_factory=list)
    sensitive: bool = False
    has_task_signal: bool = False
    evidence_conflict: bool = False
    completion_candidates: list[ScreenCompletionCandidate] = field(default_factory=list)
    evidences: list[ScreenEvidence] = field(default_factory=list)
```

### 4.2 tag 体系

首批活动标签：

- development
- communication
- shopping
- merchant
- payment
- logistics
- creator
- writing
- learning
- browsing
- office
- cloud
- finance

### 4.3 中国用户优化词表

首批高优先应用 / 域名 / 页面类型覆盖：

- 淘宝
- 拼多多
- 京东
- 支付宝
- 微信
- 企业微信
- 飞书
- 钉钉
- 小红书
- 抖音
- 哔哩哔哩
- 闲鱼
- 美团
- 饿了么
- 高德地图
- 微信读书
- Notion
- Obsidian
- 公众号后台
- 小红书创作者后台
- 阿里云
- 腾讯云

这些不能只停留在常量表里，而要同时影响：

- role context
- project_hint
- extract enrichment
- completion candidate

## 5. 配置与用户开关

### 5.1 后端配置层

新增配置语义：

- `off`
  - 不参与屏幕查询
  - 主链退化为纯语音
- `summary_only`
  - 允许抓取屏幕结构
  - 高敏感内容只保留摘要 / 标签 / 域名 / 应用
- `full`
  - 允许在通过隐私过滤后参与主链

建议设置模型：

```python
@dataclass
class ScreenContextSettings:
    enabled: bool = True
    participation_mode: str = "summary_only"  # off | summary_only | full
    provider_base_url: str = "http://localhost:3030"
    exclude_apps: list[str] = field(default_factory=list)
    exclude_domains: list[str] = field(default_factory=list)
    exclude_window_keywords: list[str] = field(default_factory=list)
    summary_only_apps: list[str] = field(default_factory=list)
    retention_days: int = 14
```

### 5.2 前端用户层

设置页至少提供：

- 是否启用屏幕上下文
- 屏幕参与模式：
  - 关闭
  - 只保留摘要
  - 参与上下文判断
- 排除应用
- 排除域名
- 排除窗口关键字
- 说明文案：
  - 会记录什么
  - 不会记录什么
  - 如何关闭
  - 如何删除已有数据
  - 保留多久

### 5.3 开关生效原则

- 关闭后，主链继续可跑
- 任何 screen provider 异常都不能打断纯语音主链
- settings 是解释层，provider 是执行层，主链只依赖统一 settings 结果

## 6. 隐私策略

### 6.1 默认保守

默认模式：`summary_only`

原则：

- 先过滤，再入链
- 敏感内容优先摘要化，而不是默认保留

### 6.2 敏感场景识别

首批规则至少覆盖：

- 密码输入框
- API key
- `.env`
- 终端 secret
- 支付页
- 银行卡页
- 验证码页
- 系统设置
- 钥匙串 / 密码管理器
- 云控制台密钥页
- 邮件正文
- 隐私聊天窗口
- 身份号码
- 手机号
- 收货地址
- 订单详情中的个人信息

### 6.3 敏感场景处理策略

处理分层：

- `drop`
  - 完全不进入上游
- `summary_only`
  - 只保留：
    - 时间
    - 应用
    - 域名
    - tags
    - completion signal
- `redact`
  - 允许参与，但文本做本地脱敏

### 6.4 用户排除规则

最少支持三类：

- 按应用排除
- 按域名排除
- 按窗口标题关键字排除

## 7. 数据流

### 7.1 主数据流

```text
screen provider
  -> raw events / elements / activity
  -> privacy filter
  -> sessionize
  -> align to scenes
  -> enrich scenes with screen_context
  -> distill / extract / briefing / active_context
  -> completion candidate generation
```

### 7.2 scene 对齐流

```text
voice scene [time_start, time_end]
  + overlapping screen sessions
  -> aligned screen evidences
  -> scene.screen_context
```

### 7.3 completion candidate 流

```text
screen summary / elements / key phrases
  -> completion rule match
  -> ScreenCompletionCandidate
  -> active_context open loop adjudication input
```

## 8. 主链改造点

### 8.1 roles

文件：

- `src/openmy/services/roles/resolver.py`

改造目标：

- 不再只看 `role_hint`
- 屏幕先定 scene context，再影响角色判断

行为：

- 开发工具 + PR / terminal / editor -> 偏向开发语境
- 微信 / 飞书 / Slack -> 偏向人与人沟通
- 淘宝 / 美团 / 支付宝 / 物流页 -> 偏向商家 / 交易语境
- 如果语音和屏幕冲突 -> 明确标冲突，不硬判

### 8.2 distill

文件：

- `src/openmy/services/distillation/distiller.py`

改造目标：

- prompt 在不污染 transcript 的前提下吃 `screen_context.summary`

示例：

- “当时正在 Cursor 修改 OpenMy 的屏幕上下文模块”
- “当时在淘宝退款页处理售后”
- “当时在飞书和人对接需求”

### 8.3 extraction

文件：

- `src/openmy/services/extraction/extractor.py`

改造目标：

- 把 scene catalog 升级为 voice + screen 并行目录
- 屏幕补：
  - 对象
  - 动作上下文
  - 完成证据
  - 项目归属

新增 enrich 输出建议：

- `screen_evidence`
- `completion_candidates`
- `project_support`

### 8.4 briefing

文件：

- `src/openmy/services/briefing/generator.py`

改造目标：

- 从 App 使用统计升级为“今天主要处理了什么”

新增输出方向：

- 语音与屏幕共同支持的高置信工作项
- 已出现完成证据的事项
- 仍停留在口头计划的事项
- 主要切换的平台 / 业务页 / 工作区

### 8.5 active_context

文件：

- `src/openmy/services/context/consolidation.py`
- `src/openmy/services/context/active_context.py`

改造目标：

- 让 rolling_context 吃到屏幕支持的项目、完成候选、今日主工作区

新增方向：

- 今天主工作区
- 今日高置信项目
- 待闭环候选

## 9. 完成候选机制

### 9.1 目标

屏幕不直接自动关任务，但可以生成“高置信度完成候选”。

### 9.2 首批完成信号

- 提交成功
- 发布成功
- 保存成功
- 已发送
- 已下单
- 已付款
- 已合并
- 已导出
- 已上传
- 任务已关闭

### 9.3 产出位置

- 写入 `scene.screen_context.completion_candidates`
- 聚合进 active_context 时，作为 open loop 裁决输入

### 9.4 决策原则

- 有屏幕证据，不等于自动完成
- 进入 `candidate` 层
- 后续可以：
  - 规则半自动关闭
  - Agent 询问确认

## 10. 前端改造点

文件：

- `app/index.html`
- `app/payloads.py`
- `app/server.py`

需要补的 UI / API：

- 设置页增加屏幕上下文策略区域
- 日报 / 活跃上下文改成展示“屏幕语境”而不是单纯 App 时长
- API 暴露 settings 状态和屏幕证据摘要
- 所有产品可见文案去掉 `Screenpipe`

注意：

- 当前 `app/index.html` 有未提交脏改动，必须采用最小定点追加，不得覆盖现有工作

## 11. 测试计划

先写红灯测试：

- `tests/unit/test_screen_provider.py`
- `tests/unit/test_screen_privacy.py`
- `tests/unit/test_screen_sessionize.py`
- `tests/unit/test_screen_align.py`
- `tests/unit/test_screen_enrich.py`
- `tests/unit/test_screen_roles.py`
- `tests/unit/test_screen_extract.py`
- `tests/unit/test_screen_briefing.py`
- `tests/unit/test_screen_settings.py`
- `tests/unit/test_screen_product_copy.py`

测试覆盖目标：

- provider 健康检查 / 降级
- 隐私过滤
- session 聚合
- scene 对齐
- enrich 行为
- 角色受屏幕语境影响
- 提取 / 日报吃到屏幕摘要
- 用户开关生效
- 产品文案清理

## 12. 迁移计划

### Phase 1

- 落 audit / architecture 文档
- 写红灯测试

### Phase 2

- 实现 provider + settings + privacy + sessionize + align

### Phase 3

- 升级 scene 数据模型
- 实现 enrich + summary

### Phase 4

- 改 roles / distill / extract / briefing / context

### Phase 5

- 加 completion candidates
- 加前端设置和产品文案清理

### Phase 6

- 跑一条真实 voice + screen 端到端
- 再跑一次关闭屏幕参与的纯语音退化验收

## 13. 验收标准映射

本方案对应用户验收项如下：

- 场景里有屏幕证据 -> `screen_context`
- 角色吃到屏幕 -> `roles resolver`
- 日报不是应用时长统计 -> `briefing`
- 提取有屏幕增强 -> `extract`
- active_context 吃到屏幕支持项目和完成候选 -> `context consolidate`
- 关闭屏幕仍能跑 -> `settings + provider degrade`
- 敏感场景拦截 -> `privacy`
- 产品文案清理 -> `app/*`, `briefing/cli.py`, `resolver.py`
