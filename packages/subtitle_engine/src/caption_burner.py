"""
字幕压制模块 - 将字幕烧录到视频中

支持多种字幕风格：tiktok/youtube/minimal/karaoke/bold/cinematic
支持 SRT/VTT/Whisper JSON 格式
"""

import json
import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Any, List, Optional


class CaptionStyle(str, Enum):
    TIKTOK = "tiktok"
    YOUTUBE = "youtube"
    MINIMAL = "minimal"
    KARAOKE = "karaoke"
    BOLD = "bold"
    CINEMATIC = "cinematic"


@dataclass
class CaptionSegment:
    start: float
    end: float
    text: str
    words: Optional[List[Dict[str, Any]]] = None


@dataclass
class StyleConfig:
    fontsize: int = 48
    fontcolor: str = "white"
    fontfile: Optional[str] = None
    borderw: int = 2
    bordercolor: str = "black"
    shadowcolor: str = "black@0.5"
    shadowx: int = 2
    shadowy: int = 2
    box: bool = False
    boxcolor: str = "black@0.6"
    boxborderw: int = 10
    x_expr: str = "(w-text_w)/2"
    y_expr: str = "h-100"
    line_spacing: int = 10


STYLE_CONFIGS: Dict[CaptionStyle, StyleConfig] = {
    CaptionStyle.TIKTOK: StyleConfig(
        fontsize=64, fontcolor="white",
        borderw=4, bordercolor="black",
        shadowx=0, shadowy=0, box=False,
        x_expr="(w-text_w)/2",
        y_expr="(h-text_h)*0.75",
    ),
    CaptionStyle.YOUTUBE: StyleConfig(
        fontsize=42, fontcolor="white",
        borderw=2, bordercolor="black",
        shadowx=2, shadowy=2,
        box=True, boxcolor="black@0.7", boxborderw=8,
        x_expr="(w-text_w)/2",
        y_expr="h-80",
    ),
    CaptionStyle.MINIMAL: StyleConfig(
        fontsize=36, fontcolor="white",
        borderw=1, bordercolor="black@0.5",
        shadowx=1, shadowy=1, box=False,
        x_expr="(w-text_w)/2",
        y_expr="h-60",
    ),
    CaptionStyle.KARAOKE: StyleConfig(
        fontsize=56, fontcolor="yellow",
        borderw=3, bordercolor="black",
        shadowx=0, shadowy=0, box=False,
        x_expr="(w-text_w)/2",
        y_expr="(h-text_h)/2",
    ),
    CaptionStyle.BOLD: StyleConfig(
        fontsize=72, fontcolor="white",
        borderw=5, bordercolor="black",
        shadowx=3, shadowy=3, box=False,
        x_expr="(w-text_w)/2",
        y_expr="(h-text_h)*0.6",
    ),
    CaptionStyle.CINEMATIC: StyleConfig(
        fontsize=38, fontcolor="white@0.9",
        borderw=0, box=True,
        boxcolor="black@0.4", boxborderw=12,
        shadowx=0, shadowy=0,
        x_expr="(w-text_w)/2",
        y_expr="h*0.85",
    ),
}


def parse_srt(srt_path: Path) -> List[CaptionSegment]:
    segments = []
    content = srt_path.read_text(encoding="utf-8")
    pattern = re.compile(
        r"(\d+)\s*\n"
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*"
        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*\n"
        r"(.*?)(?=\n\n|\n*$)",
        re.DOTALL,
    )
    for match in pattern.finditer(content):
        start = int(match.group(2)) * 3600 + int(match.group(3)) * 60 + int(match.group(4)) + int(match.group(5)) / 1000
        end = int(match.group(6)) * 3600 + int(match.group(7)) * 60 + int(match.group(8)) + int(match.group(9)) / 1000
        text = match.group(10).strip().replace("\n", " ")
        segments.append(CaptionSegment(start=start, end=end, text=text))
    return segments


def parse_vtt(vtt_path: Path) -> List[CaptionSegment]:
    segments = []
    content = vtt_path.read_text(encoding="utf-8")
    lines = content.split("\n")
    i = 0
    while i < len(lines) and "-->" not in lines[i]:
        i += 1
    pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})")
    while i < len(lines):
        match = pattern.match(lines[i].strip())
        if match:
            start = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3)) + int(match.group(4)) / 1000
            end = int(match.group(5)) * 3600 + int(match.group(6)) * 60 + int(match.group(7)) + int(match.group(8)) / 1000
            i += 1
            text_lines = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i].strip())
                i += 1
            segments.append(CaptionSegment(start=start, end=end, text=" ".join(text_lines)))
        i += 1
    return segments


def parse_whisper_json(json_path: Path) -> List[CaptionSegment]:
    data = json.loads(json_path.read_text(encoding="utf-8"))
    segments = []
    for seg in data.get("segments", []):
        segments.append(CaptionSegment(
            start=seg["start"], end=seg["end"],
            text=seg["text"].strip(),
            words=seg.get("words"),
        ))
    return segments


def load_captions(caption_path: str) -> List[CaptionSegment]:
    path = Path(caption_path)
    suffix = path.suffix.lower()
    if suffix == ".srt":
        return parse_srt(path)
    elif suffix == ".vtt":
        return parse_vtt(path)
    elif suffix == ".json":
        return parse_whisper_json(path)
    else:
        raise ValueError(f"不支持的字幕格式: {suffix}")


def escape_ffmpeg_text(text: str) -> str:
    text = text.replace("\\", "\\\\")
    text = text.replace("'", "\\'")
    text = text.replace(":", "\\:")
    text = text.replace("%", "\\%")
    return text


class CaptionBurner:
    def __init__(self, style: CaptionStyle = CaptionStyle.YOUTUBE, custom_config: Optional[StyleConfig] = None):
        self.style = style
        self.config = custom_config or STYLE_CONFIGS[style]

    def _build_drawtext_filter(self, segment: CaptionSegment, config: StyleConfig) -> str:
        text = escape_ffmpeg_text(segment.text)
        parts = [
            f"drawtext=text='{text}'",
            f"fontsize={config.fontsize}",
            f"fontcolor={config.fontcolor}",
            f"borderw={config.borderw}",
            f"bordercolor={config.bordercolor}",
            f"x={config.x_expr}",
            f"y={config.y_expr}",
            f"enable='between(t,{segment.start:.3f},{segment.end:.3f})'",
        ]
        if config.fontfile:
            parts.append(f"fontfile={config.fontfile}")
        if config.shadowx or config.shadowy:
            parts.append(f"shadowcolor={config.shadowcolor}")
            parts.append(f"shadowx={config.shadowx}")
            parts.append(f"shadowy={config.shadowy}")
        if config.box:
            parts.append("box=1")
            parts.append(f"boxcolor={config.boxcolor}")
            parts.append(f"boxborderw={config.boxborderw}")
        return ":".join(parts)

    def _build_karaoke_filters(self, segment: CaptionSegment, config: StyleConfig) -> List[str]:
        if not segment.words:
            return [self._build_drawtext_filter(segment, config)]
        filters = []
        base_text = escape_ffmpeg_text(segment.text)
        base_parts = [
            f"drawtext=text='{base_text}'",
            f"fontsize={config.fontsize}", "fontcolor='gray'",
            f"borderw={config.borderw}", f"bordercolor={config.bordercolor}",
            f"x={config.x_expr}", f"y={config.y_expr}",
            f"enable='between(t,{segment.start:.3f},{segment.end:.3f})'",
        ]
        filters.append(":".join(base_parts))
        for word_data in segment.words:
            word_text = escape_ffmpeg_text(word_data.get("word", "").strip())
            if not word_text:
                continue
            word_start = word_data.get("start", segment.start)
            word_end = word_data.get("end", segment.end)
            word_parts = [
                f"drawtext=text='{word_text}'",
                f"fontsize={config.fontsize}", f"fontcolor={config.fontcolor}",
                f"borderw={config.borderw}", f"bordercolor={config.bordercolor}",
                f"x={config.x_expr}", f"y={config.y_expr}",
                f"enable='between(t,{word_start:.3f},{word_end:.3f})'",
            ]
            filters.append(":".join(word_parts))
        return filters

    def _build_filter_chain(self, segments: List[CaptionSegment]) -> str:
        filters = []
        if self.style == CaptionStyle.KARAOKE:
            for seg in segments:
                filters.extend(self._build_karaoke_filters(seg, self.config))
        else:
            for seg in segments:
                filters.append(self._build_drawtext_filter(seg, self.config))
        return ",".join(filters)

    def burn(
        self, video_path: str, caption_path: str,
        output_path: Optional[str] = None,
        codec: str = "libx264", crf: int = 23, preset: str = "medium",
    ) -> str:
        video = Path(video_path)
        if not video.exists():
            raise FileNotFoundError(f"视频不存在: {video_path}")
        if not Path(caption_path).exists():
            raise FileNotFoundError(f"字幕不存在: {caption_path}")
        if output_path is None:
            output_path = str(video.parent / f"{video.stem}_captioned.mp4")

        segments = load_captions(caption_path)
        if not segments:
            raise ValueError("没有字幕段")

        filter_chain = self._build_filter_chain(segments)
        cmd = [
            "ffmpeg", "-y", "-i", str(video),
            "-vf", filter_chain,
            "-c:v", codec, "-crf", str(crf), "-preset", preset,
            "-c:a", "copy", output_path,
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path


def burn_captions(
    video_path: str, caption_path: str,
    style: str = "youtube", output_path: Optional[str] = None,
) -> str:
    try:
        caption_style = CaptionStyle(style.lower())
    except ValueError:
        caption_style = CaptionStyle.YOUTUBE
    burner = CaptionBurner(style=caption_style)
    return burner.burn(video_path, caption_path, output_path)
