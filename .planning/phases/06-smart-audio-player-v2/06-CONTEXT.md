# Phase 6: Smart Audio Player V2 — Context

**Gathered:** 2026-04-18
**Status:** Ready for planning
**Source:** CC 工程审查 + Silero VAD 可行性验证

<domain>
## Phase Boundary

将 OpenMy 的音频播放从"静音门控 + 伪时间轴"升级为"AI 人声检测 + 波形可视化 + 字幕动画"。

后端：用 Silero VAD 替换 ffmpeg silenceremove，输出精确的语音段时间戳。
前端：基于真实时间数据构建波形播放器和字幕流动动画。

</domain>

<decisions>
## Implementation Decisions

### 后端 — VAD 引擎选型
- **锁定 Silero VAD**（已验证）：模型 2MB，10 分钟音频 VAD 耗时 1.5s，检测到 67 个语音段（人声仅占 13%）
- 替换 `audio_pipeline.py` 中的 `SILENCE_FILTER`（ffmpeg silenceremove），改用 Silero VAD
- 安装方式：`pip install silero-vad`（已安装验证通过）
- torchaudio.sox 后端不可用，需用 wave + torch 加载 wav（已验证 workaround）

### 后端 — 数据格式
- `transcript.transcription.json` 的每个 chunk 新增 `speech_segments` 字段
- 格式：`[{"start": 0.5, "end": 3.2}, {"start": 5.1, "end": 8.7}]`
- `duration_seconds` 改为 `ffprobe` 探测的真实值（当前硬编码 0.0）
- 保持 schema_version 为 `openmy.transcription.v1`，新增字段向后兼容

### 后端 — 音频切分策略
- 当前逻辑：原始 wav → silenceremove → 按 10 分钟切分 → 转 mp3
- 新逻辑：原始 wav → Silero VAD 标记语音段 → 按 10 分钟切分 → 转 mp3（保留完整音频，标记不切）
- 为什么不切掉静音段：前端需要连续音频来画波形和时间轴，切掉会破坏时间连续性
- VAD 结果写入元数据，前端决定跳不跳过静音

### 前端 — 波形可视化
- 使用 Web Audio API 的 `AudioContext.decodeAudioData` 获取波形数据
- 在 Canvas 上绘制波形，不引入额外库（wavesurfer.js 太重）
- 波形上标记 VAD 语音段（有声 = 亮色，静音 = 暗色/透明）
- 支持拖动波形定位播放位置

### 前端 — 字幕动画
- 文字按句分割，每句映射到 VAD 语音段
- 播放时：当前句高亮、自动滚动、过渡动画（类似卡拉 OK）
- 拖动波形时文字同步跳转
- 无 VAD 数据的老日期：降级为均匀分布（当前行为）

### 前端 — UI 重构
- "显示原文"按钮改名为"显示原文和播放原声"
- 点击展开后：上方波形 + 播放控件，下方字幕式原文流动显示
- 句子列表点击 → 跳到对应 VAD 段播放
- 选中文字 → 查看来源 → 自动定位到对应句的 VAD 段

### Agent's Discretion
- 波形分辨率（每秒采样点数）
- 字幕动画的具体过渡效果（淡入淡出 vs 平滑滚动）
- 波形配色方案

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 后端
- `src/openmy/services/ingest/audio_pipeline.py` — 音频切分和转写主逻辑
- `src/openmy/config.py` — STT_VAD_ENABLED 等配置项
- `src/openmy/providers/stt/gemini.py` — Gemini 转写 provider（返回 duration=0.0 的根源）
- `src/openmy/providers/base.py` — TranscriptionResult / TranscriptionSegment 数据模型

### 前端
- `app/static/modules/subtitle-overlay.js` — 字幕回看核心逻辑
- `app/static/modules/playback.js` — 共享音频播放器
- `app/static/modules/corrections.js` — 选中文字锚点逻辑
- `app/static/modules/state.js` — 全局状态
- `app/static/css/subtitle-overlay.css` — 字幕回看样式
- `app/static/app.js` — 前端入口

### 验证数据
- `data/2026-04-15/transcript.transcription.json` — 现有转写数据样本
- `data/2026-04-15/stt_chunks/` — 现有音频 chunk 文件

</canonical_refs>

<specifics>
## Specific Ideas

### 验证数据（CC 已跑通）

Silero VAD 对 `audio_001_sub_0000.mp3`（10 分钟 chunk）的结果：
- 检测到 67 个语音段
- 有人声：78s（13%）
- 静音/音乐：522s（87%）
- VAD 耗时：1.5s（CPU）
- 模型加载：0.03s

### torchaudio 兼容性

macOS 上 torchaudio.sox 后端缺失，需用以下 workaround：
```python
import wave, struct, torch
with wave.open(tmp_wav, 'rb') as wf:
    samples = struct.unpack(f'<{wf.getnframes()}h', wf.readframes(wf.getnframes()))
wav_tensor = torch.FloatTensor(samples) / 32768.0
```

### 波形数据获取（前端）

```javascript
const response = await fetch(audioUrl);
const arrayBuffer = await response.arrayBuffer();
const audioCtx = new AudioContext();
const audioBuffer = await audioCtx.decodeAudioData(arrayBuffer);
const channelData = audioBuffer.getChannelData(0); // Float32Array
```

</specifics>

<deferred>
## Deferred Ideas

- **Demucs 音乐分离**：可以在 V3 中用 Demucs 做人声/音乐分离再转写，质量更高但需要 GPU
- **词级时间戳**：Whisper 支持但 Gemini 不支持，等换 provider 后再做
- **说话人分离**：Silero VAD 不做 diarization，需要 pyannote 或其他工具
- **流式 VAD（实时录音）**：当前只做离线 pipeline，实时 VAD 后续再加

</deferred>

---

*Phase: 06-smart-audio-player-v2*
*Context gathered: 2026-04-18 via CC engineering review + Silero VAD feasibility test*
