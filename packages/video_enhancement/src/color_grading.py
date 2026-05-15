"""
视频调色模块 - 基于 FFmpeg 滤镜的色彩分级

纯 FFmpeg 实现，无外部依赖。
支持 17 种预设调色风格，可控制强度。
"""

import re
import subprocess
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Dict, Optional


class ColorGradePreset(str, Enum):
    NONE = "none"
    NEUTRAL = "neutral"
    NATURAL = "natural"
    WARM = "warm"
    COOL = "cool"
    GOLDEN_HOUR = "golden_hour"
    BLUE_HOUR = "blue_hour"
    TEAL_ORANGE = "teal_orange"
    CINEMATIC = "cinematic"
    BLOCKBUSTER = "blockbuster"
    VIBRANT = "vibrant"
    DESATURATED = "desaturated"
    HIGH_CONTRAST = "high_contrast"
    FILMIC_WARM = "filmic_warm"
    VINTAGE = "vintage"
    NOIR = "noir"
    DOCUMENTARY = "documentary"


# FFmpeg 滤镜链定义
PRESET_FILTERS: Dict[str, str] = {
    "none": "",
    "neutral": "colorlevels=rimin=0.0625:gimin=0.0625:bimin=0.0625:rimax=0.92:gimax=0.92:bimax=0.92",
    "natural": "eq=saturation=1.02:contrast=1.01",
    "warm": "eq=contrast=1.05:brightness=0.05:saturation=1.1",
    "cool": "eq=contrast=1.05:brightness=-0.05:saturation=1.1",
    "golden_hour": "colortemperature=5500,colorbalance=rs=0.12:gs=0.06:bs=-0.1,curves=m='0 0.05 0.5 0.5 1 1',eq=saturation=1.1",
    "blue_hour": "colortemperature=9000,colorbalance=rs=-0.08:gs=0:bs=0.12,curves=m='0 0 0.5 0.48 1 0.95',eq=saturation=0.9",
    "teal_orange": "colorbalance=rs=-0.1:gs=-0.05:bs=0.15:rm=0.05:gm=0:bm=-0.05:rh=0.1:gh=0.05:bh=-0.1",
    "cinematic": "colorbalance=rs=-0.1:gs=-0.05:bs=0.15:rm=0.05:gm=0:bm=-0.05:rh=0.1:gh=0.05:bh=-0.1,curves=m='0 0 0.25 0.22 0.5 0.5 0.75 0.78 1 1'",
    "blockbuster": "colorbalance=rs=-0.12:gs=-0.06:bs=0.18:rm=0.06:gm=0:bm=-0.06:rh=0.12:gh=0.06:bh=-0.12,curves=m='0 0 0.2 0.15 0.5 0.5 0.8 0.85 1 1',eq=contrast=1.1",
    "vibrant": "eq=saturation=1.25:contrast=1.1,unsharp=3:3:0.4",
    "desaturated": "eq=saturation=0.75:contrast=1.05",
    "high_contrast": "eq=contrast=1.3:brightness=0.02,curves=m='0 0 0.15 0.05 0.5 0.5 0.85 0.95 1 1'",
    "filmic_warm": "colorbalance=rs=0.08:gs=0.04:bs=-0.08,curves=m='0 0 0.25 0.22 0.5 0.5 0.75 0.78 1 1',eq=saturation=0.92",
    "vintage": "curves=m='0 0.05 0.5 0.5 1 0.95',eq=saturation=0.8,colorbalance=rs=0.1:gs=0.05:bs=-0.05",
    "noir": "eq=saturation=0.3:contrast=1.4,curves=m='0 0 0.2 0.1 0.5 0.5 0.8 0.9 1 1'",
    "documentary": "eq=saturation=1.0:contrast=1.02,unsharp=3:3:0.3",
}

# 风格模板映射
STYLE_TO_PRESET: Dict[str, str] = {
    "dynamic": "vibrant",
    "calm": "natural",
    "intense": "cinematic",
    "emotional": "filmic_warm",
    "action": "blockbuster",
    "documentary": "documentary",
    "vintage": "vintage",
    "noir": "noir",
}


@dataclass
class ColorGradeConfig:
    preset: str = "cinematic"
    intensity: float = 1.0
    lut_path: Optional[str] = None

    def __post_init__(self):
        self.intensity = max(0.0, min(1.0, self.intensity))


def build_color_grade_filter(config: ColorGradeConfig) -> str:
    """构建 FFmpeg 调色滤镜链"""
    filters = []

    if config.lut_path and Path(config.lut_path).exists():
        if config.intensity < 1.0:
            filters.append(
                f"split[a][b];[a]lut3d={config.lut_path}[graded];"
                f"[b][graded]blend=all_expr='A*{1-config.intensity}+B*{config.intensity}'"
            )
        else:
            filters.append(f"lut3d={config.lut_path}")
        return ",".join(f for f in filters if f)

    preset_filter = PRESET_FILTERS.get(config.preset, "")
    if not preset_filter:
        return ""

    if config.intensity < 1.0 and "eq=" in preset_filter:
        preset_filter = _scale_eq_intensity(preset_filter, config.intensity)

    return preset_filter


def _scale_eq_intensity(filter_str: str, intensity: float) -> str:
    """按强度缩放 eq 滤镜参数"""
    def scale_param(match):
        param = match.group(1)
        value = float(match.group(2))
        if param in ("saturation", "contrast"):
            scaled = 1.0 + (value - 1.0) * intensity
            return f"{param}={scaled:.2f}"
        elif param == "brightness":
            scaled = value * intensity
            return f"{param}={scaled:.3f}"
        return match.group(0)

    return re.sub(r"(saturation|contrast|brightness)=([\d.]+)", scale_param, filter_str)


def apply_color_grade(
    input_path: str,
    output_path: str,
    preset: str = "cinematic",
    intensity: float = 1.0,
) -> str:
    """对视频应用调色"""
    config = ColorGradeConfig(preset=preset, intensity=intensity)
    vf = build_color_grade_filter(config)

    if not vf:
        import shutil
        shutil.copy2(input_path, output_path)
        return output_path

    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path
