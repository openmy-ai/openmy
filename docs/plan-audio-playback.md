# 音频回听功能 — Codex 执行计划

## 目标

让用户在查看转写结果时，能直接听到对应的原始录音。特别是纠错的时候，选中一个词就能听到那一段录音。

## 现状

### 已有的数据
- `stt_chunks/` 目录下有切好的 mp3 音频片段（每段约 10 分钟）
- `transcript.transcription.json` 里每个 chunk 有：
  - `chunk_id` — 唯一标识
  - `chunk_path` — 音频文件路径
  - `time_label` — 开始时间（如 "10:55"）
  - `segments[].text` — 对应的转写文本
  - `segments[].start / end` — segment 级别的时间偏移（秒）
- 但 `words` 数组为空 — Gemini 转写没开 `word_timestamps`

### 缺什么
1. **scene → chunk 映射**：scenes.json 的每个 scene 没有关联到 chunk_id
2. **word 级别时间戳**：当前为空，需要开启或换引擎
3. **音频播放 API**：后端没有提供音频文件的 HTTP 端点
4. **前端播放器**：没有音频播放 UI

## 分阶段实施

### 第一阶段：scene 级别回听（必做）

让用户在每个场景旁边点一下就能听到对应录音。

#### 1.1 建立 scene → chunk 映射

**文件**：`src/openmy/services/segmentation/segmenter.py`

- 场景切分时，根据 scene 的文本内容匹配 `transcript.transcription.json` 里的 chunk
- 匹配逻辑：scene.text 的前 50 字在哪个 chunk.text 里出现 → 关联该 chunk_id
- 在 scene 对象里新增字段：
  ```json
  {
    "audio_ref": {
      "chunk_id": "chunk_0001",
      "chunk_path": "stt_chunks/audio_001_sub_0000.mp3",
      "offset_seconds": 0
    }
  }
  ```

#### 1.2 后端音频 API

**文件**：`app/server.py` 或新建 `app/audio_api.py`

- `GET /api/audio/{date}/{chunk_id}` — 返回对应的 mp3 文件
- 支持 HTTP Range 请求（浏览器播放需要）
- 从 `data/{date}/stt_chunks/` 目录读取

#### 1.3 前端播放器

**文件**：`app/static/app.js` + `app/static/style.css`

- 每个 scene 卡片加一个播放按钮 🔊
- 点击后加载对应音频，用 HTML5 `<audio>` 播放
- 播放时高亮当前 scene 卡片
- 播放控制：播放/暂停、进度条、播放速度（0.5x / 1x / 1.5x / 2x）

---

### 第二阶段：纠错时选词回听（核心交互）

选中转写文本中的一个词，自动播放那个词附近的录音。

#### 2.1 开启 word 级别时间戳

**文件**：`src/openmy/services/transcription/` 相关

- 转写配置里把 `word_timestamps` 改为 `true`
- Gemini 转写如果不支持 word timestamps，检查是否有替代方案
- 如果用 faster-whisper 本地转写，它原生支持 word timestamps
- 时间戳写入 `transcript.transcription.json` 的 `segments[].words[]`：
  ```json
  {"word": "充电器", "start": 2.4, "end": 2.9}
  ```

#### 2.2 纠错 UI 增加音频联动

**文件**：`app/static/app.js`

- 用户在转写文本中选中一个词（或双击一个词）
- 系统根据该词的位置，找到对应的 chunk + 时间偏移
- 自动播放该时间点前后 3 秒的录音
- 如果有 word timestamps → 精确定位到该词
- 如果没有 word timestamps → 定位到该词所在 chunk 的开头

#### 2.3 纠错面板

- 选中词 → 弹出小面板：
  - 🔊 播放按钮（播放该词前后 3 秒）
  - 当前识别结果（只读）
  - 输入框：填写正确的词
  - 保存按钮 → 调用已有的 correction API
- 播放时文本高亮当前播放位置

---

### 第三阶段：质量标记联动（加分项）

- 被标记为 `music_lyrics` / `low_quality_garbled` 的 scene，卡片上显示警告图标
- 点击警告图标可以直接听录音验证：这段到底是垃圾还是被误杀了
- 用户可以手动标记"这段其实有用" → 翻转 `usable_for_downstream`

## 技术约束

1. **音频文件不要复制** — 直接从 `stt_chunks/` 读取，不要额外复制
2. **兼容现有数据** — 旧数据没有 `audio_ref` 字段时，播放按钮灰掉，不报错
3. **不要破坏现有 pipeline** — 音频映射是附加信息，不影响转写、蒸馏、日报流程
4. **前端不依赖新框架** — 用原生 HTML5 Audio API，不引入新依赖

## 验收标准

1. 打开 `localhost:8420`，看到每个 scene 有播放按钮
2. 点播放，能听到对应的录音片段
3. 在纠错模式下，选中一个词，能听到那个词附近的录音
4. 被标记为垃圾的 scene，能听录音验证
5. 旧数据（没有音频映射的）不会报错，只是播放按钮不可用

## 优先级

**第一阶段是最小可用版本，必须先做完。** 第二阶段是核心交互，做完才算"真正可用"。第三阶段是锦上添花。
