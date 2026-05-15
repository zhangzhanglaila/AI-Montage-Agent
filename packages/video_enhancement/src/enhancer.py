"""
视频增强模块 - 降噪/锐化/胶片颗粒

纯 FFmpeg 实现，无外部依赖。
"""

import subprocess
from dataclasses import dataclass


@dataclass
class DenoiseConfig:
    """降噪配置"""
    temporal_strength: float = 0.5   # 时间降噪 (0-1)
    spatial_strength: float = 0.3    # 空间降噪 (0-1)
    chroma_strength: float = 0.5     # 色度降噪 (0-1)

    def to_ffmpeg_filter(self) -> str:
        ls = self.spatial_strength * 8
        cs = self.chroma_strength * 6
        lt = self.temporal_strength * 6
        ct = self.chroma_strength * self.temporal_strength * 4
        return f"hqdn3d={ls:.1f}:{cs:.1f}:{lt:.1f}:{ct:.1f}"


@dataclass
class SharpenConfig:
    """锐化配置"""
    amount: float = 0.4     # 锐化强度 (0-1)
    radius: float = 1.5     # 半径

    def to_ffmpeg_filter(self) -> str:
        lx = max(3, min(23, int(self.radius * 2) * 2 + 1))
        la = self.amount * 2.0
        ca = la * 0.5
        return f"unsharp={lx}:{lx}:{la:.2f}:{lx}:{lx}:{ca:.2f}"


@dataclass
class FilmGrainConfig:
    """胶片颗粒配置"""
    grain_type: str = "fine"     # fine/medium/coarse/35mm/16mm
    intensity: float = 0.3       # 强度 (0-1)

    def to_ffmpeg_filter(self) -> str:
        grain_params = {
            "fine": 8, "medium": 12, "coarse": 18,
            "35mm": 10, "16mm": 15, "8mm": 22,
        }
        strength = int(grain_params.get(self.grain_type, 8) * self.intensity)
        return f"noise=c0s={strength}:c0f=t+u:allf=t+u"


def enhance_video(
    input_path: str,
    output_path: str,
    denoise: bool = False,
    sharpen: bool = False,
    film_grain: bool = False,
    denoise_config: DenoiseConfig = None,
    sharpen_config: SharpenConfig = None,
    grain_config: FilmGrainConfig = None,
) -> str:
    """对视频进行增强处理

    Args:
        input_path: 输入视频
        output_path: 输出视频
        denoise: 是否降噪
        sharpen: 是否锐化
        film_grain: 是否添加胶片颗粒
        denoise_config: 降噪配置
        sharpen_config: 锐化配置
        grain_config: 胶片颗粒配置

    Returns:
        输出视频路径
    """
    filters = []

    if denoise:
        cfg = denoise_config or DenoiseConfig()
        filters.append(cfg.to_ffmpeg_filter())

    if sharpen:
        cfg = sharpen_config or SharpenConfig()
        filters.append(cfg.to_ffmpeg_filter())

    if film_grain:
        cfg = grain_config or FilmGrainConfig()
        filters.append(cfg.to_ffmpeg_filter())

    if not filters:
        import shutil
        shutil.copy2(input_path, output_path)
        return output_path

    vf = ",".join(filters)
    cmd = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        output_path,
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    return output_path
