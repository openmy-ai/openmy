"""阿里百炼实时语音识别 (paraformer-realtime-v2，WebSocket 推流)。

通过 DashScope SDK 的 Recognition 接口实时推流转写：读音频 → 必要时用
ffmpeg 转码到 16kHz/单声道/PCM → 分帧 send_audio_frame 推送 → 回调收终句 →
按 begin_time 排序拼接成带时间戳的 TranscriptionResult。

为何用实时推流而非录音文件识别 (Transcription.async_call)：
后者要求 file_urls 是可公网访问的 URL，把音频 base64 当 data URI 塞进去属于误用，
大文件上传会触发 SSL 卡断、整段跑不完。实时推流接口在真实网络下稳定、时间戳优秀。

非自回归架构，遇到无人声直接返回空，不产生 Whisper 类型的循环幻觉。
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
import wave
from pathlib import Path
from typing import Any

from openmy.providers.base import (
    SpeechToTextProvider,
    TranscriptionResult,
    TranscriptionSegment,
)
from openmy.utils.errors import FriendlyCliError, doc_url

try:
    import dashscope
    from dashscope.audio.asr import (
        Recognition,
        RecognitionCallback,
        RecognitionResult,
    )
except ImportError:  # pragma: no cover - optional dependency
    dashscope = None
    Recognition = None
    RecognitionCallback = object  # 让下面的子类定义在缺 SDK 时也能 import
    RecognitionResult = None

# 16kHz / 16bit / 单声道：每帧 100ms = 16000 * 2 * 0.1 = 3200 字节
_SAMPLE_RATE = 16000
_FRAME_MS = 100
_FRAME_BYTES = int(_SAMPLE_RATE * 2 * _FRAME_MS / 1000)


def _probe_audio(audio_path: Path) -> tuple[int, int, int]:
    """用 ffprobe 探测采样率/声道数/位深(字节)。失败返回全 0。"""
    try:
        out = subprocess.run(
            [
                "ffprobe", "-v", "quiet",
                "-select_streams", "a:0",
                "-show_entries", "stream=sample_rate,channels,bits_per_sample,bits_per_raw_sample,codec_name",
                "-of", "default=noprint_wrappers=1:nokey=0",
                str(audio_path),
            ],
            capture_output=True, text=True, timeout=15,
        )
        fields: dict[str, str] = {}
        for line in out.stdout.splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                fields[k.strip()] = v.strip()
        sample_rate = int(fields.get("sample_rate", "0") or "0")
        channels = int(fields.get("channels", "0") or "0")
        bits = fields.get("bits_per_sample") or fields.get("bits_per_raw_sample") or "0"
        try:
            sample_width = int(bits) // 8
        except ValueError:
            sample_width = 0
        return sample_rate, channels, sample_width
    except Exception:
        return 0, 0, 0


def _to_pcm16k_mono(audio_path: Path) -> tuple[Path, bool]:
    """把任意音频转码成 16kHz/单声道/PCM(s16le) 的 WAV 临时文件。

    若源已是 16kHz/单声道/16bit 的 WAV，直接返回原路径，不转码。
    返回 (路径, 是否为临时文件)。临时文件由调用方在 finally 清理。
    """
    sample_rate, channels, sample_width = _probe_audio(audio_path)
    if (
        audio_path.suffix.lower() == ".wav"
        and sample_rate == _SAMPLE_RATE
        and channels == 1
        and sample_width == 2
    ):
        return audio_path, False

    fd, tmp_name = tempfile.mkstemp(prefix="openmy_bailian_", suffix=".wav")
    import os
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", str(audio_path),
                "-ar", str(_SAMPLE_RATE), "-ac", "1",
                "-c:a", "pcm_s16le", "-f", "wav",
                str(tmp_path),
            ],
            capture_output=True, timeout=300, check=True,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
        tmp_path.unlink(missing_ok=True)
        raise FriendlyCliError(
            "音频转码失败（百炼实时识别需要 16kHz/单声道/PCM）。",
            code="bailian_transcode_failed",
            fix="确认已安装 ffmpeg，或先换一段标准 WAV 音频再重试。",
            doc_url=doc_url("语音转写"),
            message_en=f"Audio transcode to 16kHz mono PCM failed: {e}",
            fix_en="Install ffmpeg or provide a standard WAV file, then retry.",
        ) from e
    return tmp_path, True


def _read_pcm(wav_path: Path) -> bytes:
    """读出 16kHz/单声道/16bit WAV 的裸 PCM 数据。"""
    with wave.open(str(wav_path), "rb") as wf:
        return wf.readframes(wf.getnframes())


class _SentenceCollector(RecognitionCallback):  # type: ignore[misc,valid-type]
    """只采纳终句 (is_sentence_end)，中间结果(partial)丢弃。"""

    def __init__(self) -> None:
        self.sentences: list[dict[str, Any]] = []
        self.errors: list[str] = []

    def on_event(self, result: "RecognitionResult") -> None:  # noqa: F821
        sentence = result.get_sentence()
        if sentence is None:
            return
        if not RecognitionResult.is_sentence_end(sentence):
            return
        text = (sentence.get("text") or "").strip()
        if not text:
            return
        self.sentences.append(
            {
                "text": text,
                "begin_time": sentence.get("begin_time") or 0,
                "end_time": sentence.get("end_time") or 0,
            }
        )

    def on_error(self, result: Any) -> None:
        self.errors.append(str(result))


class BailianSTTProvider(SpeechToTextProvider):
    """阿里百炼实时语音识别 (paraformer-realtime-v2)。

    非自回归架构，从结构上不会产生 Whisper 类型的循环幻觉；
    对无人声音频返回空结果而非捏造文字。

    热词 (vocab_terms)：
        paraformer-realtime-v2 的热词需要预先通过 DashScope 的 VocabularyService
        创建词表、拿到 vocabulary_id，再把该 id 透传给 Recognition。直接传一串词
        是不行的——SDK 不接受即席词列表。

        本 provider 不在每次转写时即席创建词表（即席创建+删除每次都要联网、有配额
        和延迟成本）。注入通路如下：
          1. 预先创建词表，拿到 vocabulary_id：
                 from dashscope.audio.asr import VocabularyService
                 vid = VocabularyService(api_key=KEY).create_vocabulary(
                     target_model="paraformer-realtime-v2",
                     prefix="openmy",
                     vocabulary=[{"text": "深圳湾文化广场", "weight": 4, "lang": "zh"}],
                 )
          2. 把 vid 写进环境变量 OPENMY_BAILIAN_VOCABULARY_ID。
        本 provider 启动转写时会读取该环境变量，若存在则注入 Recognition
        （vocabulary_id=<id>，SDK 通过 kwargs 透传给服务端）。

        vocab_terms（、分隔的词串）本身目前仅用于在缺少 vocabulary_id 时记录到
        provider_metadata，方便排查；它不会自动转成词表。遗留：把 vocab_terms 自动
        编译成词表 id（即席创建+缓存复用）尚未实现，需要时按上面通路手工创建。
    """

    name = "bailian"

    def transcribe(
        self,
        audio_path: Path,
        *,
        vocab_terms: str = "",
        timeout_seconds: int,
        vad_filter: bool = False,
        word_timestamps: bool = False,
    ) -> TranscriptionResult:
        # vad_filter / word_timestamps 本 provider 不直接使用，但会记进 metadata
        # 告知调用方被忽略（与 funasr/gemini 对齐）；timeout_seconds 不适用实时推流。
        del timeout_seconds

        if Recognition is None:
            raise FriendlyCliError(
                "百炼依赖没装好，当前不能用这个转写路线。",
                code="bailian_sdk_missing",
                fix="先运行 `uv pip install dashscope`（或装上 [cloud] 依赖组），再重试。",
                doc_url=doc_url("语音转写"),
                message_en="DashScope SDK is not installed.",
                fix_en="Run `uv pip install dashscope` (or install the [cloud] extra), then retry.",
            )

        if not self.api_key:
            raise FriendlyCliError(
                "缺少百炼的 API key（访问口令）。",
                code="missing_bailian_key",
                fix="把 DASHSCOPE_API_KEY 写进 .env 文件再重试。申请地址：https://bailian.console.aliyun.com/",
                doc_url=doc_url("语音转写"),
                message_en="Missing Bailian/DashScope API key.",
                fix_en="Add DASHSCOPE_API_KEY to .env. Get one at https://bailian.console.aliyun.com/",
            )

        dashscope.api_key = self.api_key

        # 热词注入通路：读取预先创建好的词表 id（见类 docstring）。
        vocabulary_id = (os.environ.get("OPENMY_BAILIAN_VOCABULARY_ID") or "").strip()

        metadata: dict[str, Any] = {
            "provider": self.name,
            "model": self.model,
            # 与 funasr/gemini 对齐：明确告知调用方这两个参数被本 provider 忽略。
            "vad_filter": vad_filter,
            "word_timestamps": word_timestamps,
        }
        if vocabulary_id:
            metadata["vocabulary_id"] = vocabulary_id
        elif vocab_terms:
            # 词表 id 未配置时，记录待编译的热词串，便于排查。
            metadata["vocab_terms_pending"] = vocab_terms

        pcm_path, is_tmp = _to_pcm16k_mono(audio_path)
        try:
            pcm = _read_pcm(pcm_path)
            if not pcm:
                # 空音频：真没内容，按 empty_transcript 契约抛错（上层不重试）。
                raise FriendlyCliError(
                    f"百炼没有返回这段音频的转写结果：{audio_path.name}",
                    code="bailian_empty_transcript",
                    fix="先换一段更短、更清晰的音频试一次。",
                    doc_url=doc_url("语音转写"),
                    message_en=f"Bailian returned no transcript for {audio_path.name} (empty audio).",
                    fix_en="Try a shorter and clearer audio file, then retry.",
                )

            collector = _SentenceCollector()
            rec_kwargs: dict[str, Any] = {
                "model": self.model,
                "format": "pcm",
                "sample_rate": _SAMPLE_RATE,
                "callback": collector,
                "language_hints": ["zh", "en"],
            }
            if vocabulary_id:
                rec_kwargs["vocabulary_id"] = vocabulary_id

            recognition = Recognition(**rec_kwargs)

            total_frames = (len(pcm) + _FRAME_BYTES - 1) // _FRAME_BYTES
            sent_frames = 0
            truncated = False  # 被 silence_timer 提前结束（worker 停了，帧没推完）

            try:
                recognition.start()
                send_start = time.time()
                for offset in range(0, len(pcm), _FRAME_BYTES):
                    try:
                        recognition.send_audio_frame(pcm[offset : offset + _FRAME_BYTES])
                    except Exception:
                        # worker 已被 silence_timer 置停，后续帧无法投递 → 截断。
                        truncated = True
                        break
                    sent_frames += 1
                    # 节流：按帧时长（100ms）推送，扣减已耗时避免漂移，
                    # 让发送侧与服务端识别同步、持续重置 23s silence_timer。
                    # 这是 realtime_test.py 已验证跑通的写法，长音频必须保留。
                    should_elapsed = sent_frames * _FRAME_MS / 1000.0
                    lag = should_elapsed - (time.time() - send_start)
                    if lag > 0:
                        time.sleep(lag)
                if truncated:
                    # worker 已被 silence_timer 停掉，stop() 会抛 InvalidParameter，
                    # 吞掉让流程走到下方 truncated 判断（触发上层重试），不当连接失败。
                    try:
                        recognition.stop()
                    except Exception:
                        pass
                else:
                    recognition.stop()
            except FriendlyCliError:
                raise
            except Exception as e:
                try:
                    recognition.stop()
                except Exception:
                    pass
                # 服务端真实错误（配额/鉴权/模型不存在）优先于宽泛的连接失败。
                if collector.errors:
                    raise FriendlyCliError(
                        "百炼实时识别返回错误。",
                        code="bailian_realtime_error",
                        fix="检查 API key、配额或模型名称，稍后重试。",
                        doc_url=doc_url("语音转写"),
                        message_en=f"Bailian realtime recognition error: {collector.errors[0]}",
                        fix_en="Check API key, quota or model name, then retry.",
                    ) from e
                raise FriendlyCliError(
                    f"百炼实时识别连接失败：{e}",
                    code="bailian_realtime_failed",
                    fix="检查网络连接和 API key，稍后重试。",
                    doc_url=doc_url("语音转写"),
                    message_en=f"Bailian realtime recognition failed: {e}",
                    fix_en="Check network connection and API key, then retry.",
                ) from e

            # 服务端错误优先：先于"截断/空结果"判断真实原因。
            if collector.errors:
                raise FriendlyCliError(
                    "百炼实时识别返回错误。",
                    code="bailian_realtime_error",
                    fix="检查 API key、配额或模型名称，稍后重试。",
                    doc_url=doc_url("语音转写"),
                    message_en=f"Bailian realtime recognition error: {collector.errors[0]}",
                    fix_en="Check API key, quota or model name, then retry.",
                )

            # 截断保护：音频没推完（被 silence_timer 提前结束）绝不当成功，
            # 抛不含 empty_transcript 的错误，触发上层重试。
            if truncated or sent_frames < total_frames:
                raise FriendlyCliError(
                    "百炼实时识别中途被静默超时截断，未推完整段音频。",
                    code="bailian_realtime_truncated",
                    fix="稍后重试；若反复出现请检查网络稳定性。",
                    doc_url=doc_url("语音转写"),
                    message_en=(
                        f"Bailian realtime recognition was truncated by the silence timeout: "
                        f"only {sent_frames}/{total_frames} frames delivered."
                    ),
                    fix_en="Retry later; if it persists, check network stability.",
                )

            ordered = sorted(collector.sentences, key=lambda s: s["begin_time"])
            segments: list[TranscriptionSegment] = []
            text_parts: list[str] = []
            total_duration = 0.0
            for idx, sent in enumerate(ordered, start=1):
                start = (sent["begin_time"] or 0) / 1000.0
                end = (sent["end_time"] or 0) / 1000.0
                segments.append(
                    TranscriptionSegment(
                        id=f"seg_{idx:04d}",
                        text=sent["text"],
                        start=start,
                        end=end,
                    )
                )
                text_parts.append(sent["text"])
                if end > total_duration:
                    total_duration = end

            full_text = "".join(text_parts)
            if not full_text:
                # 整段推完、确认无终句 → 真静音，按 empty_transcript 契约（上层不重试）。
                raise FriendlyCliError(
                    f"百炼没有返回这段音频的转写结果：{audio_path.name}",
                    code="bailian_empty_transcript",
                    fix="先换一段更短、更清晰的音频试一次。",
                    doc_url=doc_url("语音转写"),
                    message_en=f"Bailian returned no transcript for {audio_path.name}.",
                    fix_en="Try a shorter and clearer audio file, then retry.",
                )

            return TranscriptionResult(
                text=full_text,
                language="zh",
                duration_seconds=total_duration,
                segments=segments,
                provider_metadata=metadata,
            )
        finally:
            if is_tmp:
                pcm_path.unlink(missing_ok=True)
