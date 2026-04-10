# Screen Integration Audit

Date: 2026-04-10
Status: pre-implementation audit for screen-context mainline overhaul

## 1. 目标

本审计只回答两个问题：

1. 当前 OpenMy 仓库里，屏幕能力到底真实进到了哪些主链。
2. 上游屏幕系统已经提供了哪些能力，哪些能力 OpenMy 还没有吃到。

结论先写在前面：

- 当前仓库里，屏幕信号只真正进了两条浅链：
  - 角色归因的低权重侧证
  - 日报里的 App 列表 / 使用时长补充
- README 已经把 OpenMy 定义成“语音 + 屏幕等个人原始信号”的个人上下文引擎，但代码主链还没有兑现这句话。
- 当前最大缺口不是“少一个接口”，而是缺少一条完整的屏幕上下文总线：
  - 没有统一 provider
  - 没有隐私语义层
  - 没有 scene 级屏幕证据模型
  - 没有蒸馏 / 提取 / active_context / 完成候选的系统性接入

## 2. 当前仓库真实接入点

### 2.1 adapter 已有能力

文件：`src/openmy/adapters/screen_recognition/client.py`

当前已实现接口：

- `is_available()` -> `GET /health`
- `search_ocr()` -> `GET /search?content_type=ocr`
- `activity_summary()` -> `GET /activity-summary`
- `search_elements()` -> `GET /elements`
- `get_memories()` -> `GET /memories`

当前问题：

- adapter 能力比主链实际使用范围大得多。
- `search_elements()` 和 `get_memories()` 在当前 OpenMy 主链里没有真正消费。
- `search_ocr()` 只返回裁切后的 `text[:200]`，适合轻提示，但还不够支撑“结构化屏幕证据”。

### 2.2 角色链真实用法

文件：`src/openmy/services/roles/resolver.py`
函数：`resolve_roles()`

真实调用路径：

1. `tag_all_scenes()` 先做纯语音角色归因
2. 如果存在 `screen_client`
3. 调用 `openmy.services.screen_recognition.hints.enrich_with_hints()`

文件：`src/openmy/services/screen_recognition/hints.py`

当前只做了这些事：

- `sessionize(events)`：按 `app_name + window_name` 和时间间隔做简单聚合
- `get_role_hint()`：只给 `ai / interpersonal / merchant` 三个角色桶做提示
- `apply_hints()`：
  - 如果语音角色已高置信，则不改
  - 如果语音和屏幕一致，给一点加分
  - 如果语音不确定，用屏幕做低置信 fallback
  - 如果冲突，只是 `needs_review = True`

结论：

- 屏幕目前不是“场景语境判定器”，只是“角色侧证加分器”。
- 语义粒度只有三类，远小于用户要求的开发 / 社交 / 购物 / 物流 / 支付 / 创作 / 学习 / 云平台等上下文。

### 2.3 日报链真实用法

文件：`src/openmy/services/briefing/generator.py`
函数：`generate_briefing()`

真实调用：

- `_get_screenpipe_apps()`：按时段查询 OCR 事件，提取 App 名单
- `_get_screenpipe_app_usage()`：优先走 `activity_summary()`，降级走 OCR 计数

屏幕目前进入日报的方式：

- `TimeBlock.apps_used`
- `DailyBriefing.work_sessions`
- `DailyBriefing.screen_recognition_available`

当前问题：

- 日报里的“屏幕”主要还是应用使用信息。
- 还没有回答：
  - 当时在处理什么任务
  - 语音里说的事有没有屏幕证据
  - 哪些待办已经出现完成证据
  - 哪些项目在屏幕上持续推进

### 2.4 CLI / 运行管线真实用法

文件：`src/openmy/cli.py`

- `get_screen_client()` 会创建 `ScreenRecognitionClient`
- `cmd_briefing()` 把 client 传给 `generate_briefing()`
- 角色链路也能拿到 client

文件：`src/openmy/commands/run.py`

真实接入点：

- `roles` 阶段：`_resolve_roles(..., screen_client=screen_client)`
- `briefing` 阶段：`cmd_briefing()`

未接入：

- `distill`
- `extract`
- `context consolidate`
- `open loop close candidate`
- `active_context` 生成

### 2.5 前端 / Web 服务真实状态

文件：`app/server.py`

当前问题：

- 仍存在旧导入：`from openmy.adapters.screenpipe.client import ScreenpipeClient`
- 这与当前 adapter 实际路径 `openmy.adapters.screen_recognition.client` 不一致
- 启动日志仍显示“Screenpipe 已连接（hints 模式）”

文件：`app/index.html`

当前产品文案问题：

- 日报卡片里仍把能力直接显示为 `Screenpipe`

文件：`src/openmy/services/briefing/cli.py`

当前 CLI 文案问题：

- 多处直接向用户输出 `Screenpipe 已连接 / 未检测到`

结论：

- 产品层口径还没有内化为 OpenMy 自有能力。
- 用户当前也没有看到明确的“屏幕上下文参与策略”开关。

## 3. 当前没有进入的主链

以下链路当前基本还是纯语音：

### 3.1 蒸馏

文件：`src/openmy/services/distillation/distiller.py`

当前 prompt 只吃：

- scene 原文
- `role_info`

没有吃：

- 屏幕摘要
- 主应用 / 主窗口 / 主域名
- 场景标签
- 冲突信息

### 3.2 结构化提取

文件：`src/openmy/services/extraction/extractor.py`

当前提取 prompt 只吃：

- transcript 文本
- scene catalog（只用于 `source_scene_id`）

没有吃：

- scene 级屏幕证据
- 完成候选
- 屏幕支持的项目归属
- 屏幕摘要产生的动作上下文

### 3.3 active_context / consolidation

文件：`src/openmy/services/context/consolidation.py`

当前聚合主要吃：

- `daily_briefing.json`
- `*.meta.json`
- `scenes.json` 的语音角色字段

当前闭环逻辑：

- `_auto_close_loops()` 只靠 `intent.status in DONE_STATUSES`
- 没有屏幕完成证据候选

### 3.4 纠错 / 闭环 / 状态闭环

当前没有正式能力把这些屏幕证据升格为闭环候选：

- 已提交
- 已保存
- 已发送
- 已下单
- 已付款
- 已合并
- 已发布
- 已导出

## 4. README 口径与实现不一致点

文件：`README.md`

当前文档口径：

- OpenMy 是“录音、屏幕等个人原始信号”的个人上下文引擎
- repo tree 已把 `screen_recognition/` 标为“屏幕上下文”

当前实现现实：

- 屏幕不是主信源
- 屏幕没有进入蒸馏 / 提取 / active_context 主链
- 屏幕没有形成隐私语义层和用户开关
- 屏幕没有成为完成证据来源

结论：

- README 描述的是目标产品定义
- 现有代码只完成了非常早期的 hints 接线

## 5. 上游屏幕系统研究结论

审计仓库：`https://github.com/mediar-ai/screenpipe`

本次重点看的不是 README，而是实际服务端、录制、OCR、隐私与配置代码。

### 5.1 它怎么抓取屏幕

上游关键实现：

- `crates/screenpipe-engine/src/paired_capture.rs`
- `crates/screenpipe-screen/src/core.rs`
- `crates/screenpipe-a11y/src/tree/*`

结论：

- 不是单纯截图 OCR。
- 它会把截图和可访问性树结合起来做 paired capture。
- 当 accessibility 信息不足时，再用 OCR 做补充。
- 时间序列上是持续捕捉的 frame / element / content 记录。

### 5.2 它怎么做 OCR

关键实现：

- `crates/screenpipe-screen/src/apple.rs`
- `crates/screenpipe-screen/src/tesseract.rs`

结论：

- macOS 侧使用 Apple Vision OCR
- 其他环境可走 Tesseract
- 会保留 bbox / frame 级信息，适合以后做 frame 引用和定位

### 5.3 它怎么组织查询能力

关键 API：

- `/search`
- `/activity-summary`
- `/elements`
- `/memories`

OpenMy 当前只真正用了：

- `/health`
- `/search`（OCR）
- `/activity-summary`

OpenMy 还没吃到但有价值的：

- `/elements`：适合做按钮 / 状态词 / 页面结构级判断
- `/memories`：适合以后做跨日屏幕记忆桥接

### 5.4 它已有的隐私 / 排除机制

关键代码：

- `crates/screenpipe-config/src/recording.rs`
- `crates/screenpipe-config/src/defaults.rs`
- `screenpipe-a11y/src/tree/macos.rs`
- `screenpipe-a11y/src/tree/windows.rs`
- `screenpipe-a11y/src/tree/linux.rs`
- `screenpipe-a11y/src/incognito/*`
- `screenpipe-engine/src/drm_detector.rs`

已存在能力：

- `ignoredWindows`
- `includedWindows`
- `ignoredUrls`
- `ignoreIncognitoWindows`
- `pauseOnDrmContent`
- `usePiiRemoval`
- 默认忽略部分系统 UI
- 默认避开一批密码管理器 / 安全工具 / keychain
- 支持隐身 / 无痕窗口跳过
- DRM 内容暂停采集

### 5.5 它已有的 PII 脱敏

关键代码：

- `crates/screenpipe-core/src/pii_removal.rs`

已覆盖内容包括但不限于：

- email
- phone
- credit card
- JWT
- private key
- cloud / SaaS token
- env secret
- password 相关模式

结论：

- 上游已经有“通用 PII removal”
- 但这不等于 OpenMy 的“产品级敏感语义策略”

### 5.6 上游能力的边界

上游已经做了：

- 通用 PII 红线
- 部分系统级排除
- 无痕 / DRM / 密码管理器规避

上游没有替 OpenMy 做的：

- 中国业务应用 / 域名 / 页面类型语义识别
- “支付 / 物流 / 售后 / 创作后台 / 云密钥页 / 地址手机号 / 隐私聊天”的产品级规则层
- “只保留摘要，不保留明文”的 OpenMy 本地策略层
- “完成证据候选”的任务闭环能力

## 6. 当前最大缺口

### 6.1 缺少统一总线

当前所有屏幕逻辑几乎都在 `hints.py`。

结果：

- 难以复用
- 无法做 privacy first
- 无法进入多条主链

### 6.2 缺少 scene 级正式模型

当前 `Scene` 里只有：

- `screen_sessions: list[ScreenSession]`

缺少正式表达：

- 主应用 / 主窗口 / 主域名
- 活动标签
- 敏感场景命中
- 冲突证据
- 高置信任务信号
- 完成候选
- frame 引用

### 6.3 缺少用户级策略开关

当前只有配置常量：

- `SCREEN_RECOGNITION_ENABLED`
- `SCREEN_RECOGNITION_API`

缺少：

- 用户可见状态
- “关闭记录 / 仅记录不参与 / 参与提取”的语义拆分
- 排除应用 / 域名 / 窗口关键字的配置入口

### 6.4 缺少屏幕摘要层

当前要么：

- 只看 App 名
- 要么取 OCR 原文

缺少中间层：

- 面向 scene 的可读屏幕摘要
- 面向提取 / 蒸馏的并行证据文本

## 7. 这轮改造需要补什么

本轮需要补的是“正式主链能力”，不是再堆几个 helper。

必须新增并接入：

- `provider.py`
- `sessionize.py`
- `privacy.py`
- `align.py`
- `enrich.py`
- `summary.py`
- `settings.py`

并把屏幕信号接进：

- roles
- distill
- extract
- briefing
- active_context
- completion candidate
- product settings

## 8. 本轮实现准则

- 不把整屏 OCR 粘进 transcript 主文本
- 屏幕以并行证据源进入 scene / extract / briefing / context
- 默认保守，先过滤敏感场景再入链
- 保持纯语音模式可运行
- 产品层统一改成“屏幕上下文 / 屏幕记录 / 屏幕证据”
- `Screenpipe` 只留在 README 致谢、NOTICE、第三方声明

## 9. 对应实现文档

下一份正式方案见：

- `docs/screen-integration-architecture.md`
