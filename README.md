# OpenMy

把一段音频，变成可浏览的日报和结构化上下文。

![OpenMy quick start screenshot](docs/images/openmy-quick-start.png)

[English](README.en.md)

## 30 秒快速开始

### 1. clone

```bash
git clone https://github.com/openmy-ai/openmy.git
cd openmy
```

### 2. 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
```

### 3. 只配一个 API key

```bash
cp .env.example .env
```

把 `.env` 里的 `your-gemini-api-key` 换成你自己的 Gemini key。

如果你已经有 key，也可以一条命令：

```bash
echo "GEMINI_API_KEY=你的key" > .env
```

### 4. 一条命令处理音频并打开日报

```bash
openmy quick-start path/to/your-audio.wav
```

这个命令会自动：

1. 检查 Python 和 FFmpeg
2. 读取项目根目录 `.env`
3. 转写音频
4. 清洗文本、切场景、角色归因、蒸馏摘要
5. 生成日报和结构化提取
6. 启动本地 Web 页面
7. 自动打开浏览器到 `http://127.0.0.1:8420`

你不需要先读代码，不需要手动 export 环境变量，也不需要自己记日期格式。

## 这是什么

OpenMy 是一个“个人上下文引擎”：

- 输入：一段音频
- 输出：日报、时间线、结构化事件、活跃上下文
- 适合：复盘一天在说什么、做什么、和谁互动、有哪些待办和事实

它不是纯转写工具。OpenMy 会在转写之后继续做清洗、场景切分、角色识别、摘要和提取，让结果变成可浏览、可消费的数据。

## 你会看到什么

跑完 `openmy quick-start` 后，浏览器会打开一份本地日报页面，里面包括：

- 当天摘要
- 时间线
- 事件 / 事实 / 洞察卡片
- 日报视图
- 角色和场景统计

## 依赖自检

OpenMy 会在命令启动时尽量用人话告诉你缺什么。

### Python 版本

- 要求：`Python 3.10+`
- 如果版本不对，CLI 会直接提示怎么装
- macOS 常用命令：

```bash
brew install python@3.11
```

### FFmpeg

音频导入依赖 `ffmpeg` 和 `ffprobe`。

- macOS：

```bash
brew install ffmpeg
```

- Ubuntu / Debian：

```bash
sudo apt install ffmpeg
```

如果没装，`openmy quick-start` 会直接告诉你怎么补，不会给一串难懂的 subprocess 报错。

## 常用命令

```bash
openmy --help
openmy status
openmy view 2026-04-10
openmy run 2026-04-10 --audio path/to/audio.wav
openmy quick-start path/to/audio.wav
```

说明：

- `quick-start` 面向第一次使用的人
- `run` 适合你已经知道日期和输入参数时单独控制
- `view` 适合在终端快速看某天结果

## 流程长什么样

```text
Audio
  → Transcribe
  → Clean
  → Scene Split
  → Role Resolve
  → Distill
  → Briefing
  → Extract
  → Active Context
  → Web Report
```

默认打开的是本机网页：

- 地址：`http://127.0.0.1:8420`
- 默认只绑定本机，不会自动开放到局域网

## 配置说明

默认配置在 [`src/openmy/config.py`](src/openmy/config.py)。

大多数人第一次使用时不用改它。先配 `.env`，然后直接跑 `openmy quick-start` 就够了。

如果你之后想调参数，常见会改的是：

- Gemini 模型
- 转写 / 音频管线超时
- 提取 / 蒸馏温度

## 可选：Screenpipe 屏幕上下文

OpenMy 可以接 Screenpipe，为语音结果补充“当时在看什么 App / 页面”的上下文。

- 不装也能正常跑日报
- 装了之后，会在角色归因和摘要上提供额外线索
- 默认通过本地 HTTP 接口读取，不要求你改业务代码

## 开发与测试

```bash
python3 -m pytest tests
```

当前测试默认不依赖真实 API key；在没有 `GEMINI_API_KEY` 的环境里也应该能全绿。

## 仓库结构

```text
src/openmy/        核心 Python 包
app/               本地日报 Web 页面
tests/             自动化测试
docs/images/       README 截图
skills/            项目技能与补充说明
```

## License

[MIT](LICENSE)
