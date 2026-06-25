# OpenMy macOS 原生前端

OpenMy 的 macOS 原生壳：用 SwiftUI 写界面，通过本机 HTTP 对接现有 Python 后端（`localhost:8420`）。
它本身不做转写、不存数据，所有处理与任务控制都复用后端接口。

## 前置条件

- macOS 14 及以上
- Swift 6.0 工具链（Xcode 16 或对应命令行工具）
- **后端必须在 `localhost:8420` 运行**。前端只是壳，后端没起来时界面会停在「正在连接 OpenMy…」。
  后端启动方式见仓库根目录的 OpenMy 文档（`openmy view` 会拉起服务与 Web UI）。

## 目录结构

| 路径 | 说明 |
|------|------|
| `Sources/OpenMyKit` | 可测核心：数据模型、`APIClient`、视图模型状态机、设计系统（`Theme`） |
| `Sources/OpenMyApp` | SwiftUI 视图与应用入口 |
| `Tests/OpenMyKitTests` | 单元测试（XCTest），覆盖 API 解码与视图模型状态机 |
| `scripts/build-app.sh` | 打包成可双击运行的 `OpenMy.app` |

设计原则：纯逻辑（解码、状态机、过滤、文案映射）放进 `OpenMyKit` 并写测试；纯 SwiftUI 视图不写单测。

## 构建与测试

```bash
swift build          # 编译
swift test           # 运行全部单元测试
```

## 打包成 App

```bash
bash scripts/build-app.sh        # 产出 build/OpenMy.app
open build/OpenMy.app            # 启动（需后端已在 localhost:8420 运行）
```

脚本会编译 release 版二进制，组装标准 `.app` bundle（`Contents/MacOS` + `Info.plist`），并复制可执行文件进去。

## 启动后

- 首次使用会进入引擎选择（onboarding），选好转写引擎后进入主界面。
- 主界面左侧是已处理日期列表，右侧是日报详情。
- 把录音文件拖到右侧空白区即可开始处理，进度面板会实时显示四个阶段（转写 / 清洗 / 场景切分 / 蒸馏），并支持暂停、继续、取消、跳过。

## 设计系统

视图统一通过 `import OpenMyKit` 取设计 token 和复用组件：

- `Theme.Spacing` / `Theme.Radius` / `Theme.Palette` / `Theme.Typography`：间距、圆角、颜色、字体 token
- `.omCard()` / `.omSection()`：卡片与区块容器样式修饰符
- `OMBadge` / `OMMetric` / `OMErrorText`：可复用小组件

新增视图样式时优先用这些 token 与组件，不要散落硬编码的间距和圆角。
