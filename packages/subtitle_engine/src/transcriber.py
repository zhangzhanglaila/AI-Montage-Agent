"""
语音转字幕模块 - 使用 Whisper 自动生成字幕

支持 openai-whisper 和 faster-whisper 两种后端。
输出 SRT/VTT/JSON 格式字幕文件。
"""

import json
import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any


def extract_audio(video_path: str, audio_path: str, sample_rate: int = 16000) -> str:
    """从视频中提取音频"""
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vn", "-acodec", "pcm_s16le",
        "-ar", str(sample_rate), "-ac", "1",
        audio_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return audio_path


def transcribe_whisper(
    audio_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """使用 openai-whisper 转录音频"""
    try:
        import whisper

        model = whisper.load_model(model_size)
        result = model.transcribe(
            audio_path,
            language=language,
            word_timestamps=True,
        )
        return result
    except ImportError:
        raise ImportError("请安装 openai-whisper: pip install openai-whisper")


def transcribe_faster_whisper(
    audio_path: str,
    model_size: str = "base",
    language: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """使用 faster-whisper 转录音频"""
    try:
        from faster_whisper import WhisperModel

        model = WhisperModel(model_size, device="cpu")
        segments, info = model.transcribe(audio_path, language=language, word_timestamps=True)

        result_segments = []
        for seg in segments:
            words = []
            if seg.words:
                for w in seg.words:
                    words.append({"word": w.word, "start": w.start, "end": w.end})
            result_segments.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
                "words": words,
            })
        return result_segments
    except ImportError:
        raise ImportError("请安装 faster-whisper: pip install faster-whisper")


def segments_to_srt(segments: List[Dict[str, Any]]) -> str:
    """将转录段落转为 SRT 格式"""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = _format_srt_time(seg["start"])
        end = _format_srt_time(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{i}\n{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def segments_to_vtt(segments: List[Dict[str, Any]]) -> str:
    """将转录段落转为 WebVTT 格式"""
    lines = ["WEBVTT\n"]
    for seg in segments:
        start = _format_vtt_time(seg["start"])
        end = _format_vtt_time(seg["end"])
        text = seg["text"].strip()
        lines.append(f"{start} --> {end}\n{text}\n")
    return "\n".join(lines)


def segments_to_whisper_json(segments: List[Dict[str, Any]]) -> str:
    """将转录段落转为 Whisper JSON 格式"""
    return json.dumps({"segments": segments}, ensure_ascii=False, indent=2)


def _format_srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _format_vtt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


class Transcriber:
    """语音转字幕"""

    def __init__(self, backend: str = "whisper", model_size: str = "base"):
        self.backend = backend
        self.model_size = model_size

    def transcribe(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        output_format: str = "srt",
        language: Optional[str] = None,
    ) -> str:
        """转录音频/视频并生成字幕文件

        Args:
            input_path: 输入音频或视频文件
            output_path: 输出字幕文件路径
            output_format: 输出格式 (srt/vtt/json)
            language: 语言代码 (如 zh/en/ja)，None 为自动检测

        Returns:
            输出字幕文件路径
        """
        input_file = Path(input_path)

        # 如果是视频，先提取音频
        if input_file.suffix.lower() in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
            audio_path = str(input_file.parent / f"{input_file.stem}_audio.wav")
            extract_audio(input_path, audio_path)
            cleanup_audio = True
        else:
            audio_path = input_path
            cleanup_audio = False

        try:
            # 转录
            if self.backend == "faster_whisper":
                raw_segments = transcribe_faster_whisper(audio_path, self.model_size, language)
            else:
                result = transcribe_whisper(audio_path, self.model_size, language)
                raw_segments = result.get("segments", [])

            # 转换格式
            if output_format == "srt":
                content = segments_to_srt(raw_segments)
                suffix = ".srt"
            elif output_format == "vtt":
                content = segments_to_vtt(raw_segments)
                suffix = ".vtt"
            elif output_format == "json":
                content = segments_to_whisper_json(raw_segments)
                suffix = ".json"
            else:
                raise ValueError(f"不支持的格式: {output_format}")

            # 写入文件
            if output_path is None:
                output_path = str(input_file.parent / f"{input_file.stem}_subtitles{suffix}")

            Path(output_path).write_text(content, encoding="utf-8")
            return output_path

        finally:
            if cleanup_audio and Path(audio_path).exists():
                Path(audio_path).unlink()
