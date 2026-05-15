"""
视频防抖模块 - 基于 FFmpeg vidstab 的专业级稳定

支持多种预设配置。
两阶段流程：分析 → 稳定
"""

import subprocess
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class StabilizationProfile:
    """防抖配置"""
    name: str
    shakiness: int       # 1-10，越高检测越灵敏
    accuracy: int        # 1-15，越高越精确
    smoothing: int       # 平滑窗口（帧数）
    deshake_iterations: int = 2


# 预设配置
PROFILES = {
    "vlog_action": StabilizationProfile("vlog_action", shakiness=8, accuracy=12, smoothing=30, deshake_iterations=2),
    "documentary": StabilizationProfile("documentary", shakiness=6, accuracy=10, smoothing=20, deshake_iterations=2),
    "cinematic": StabilizationProfile("cinematic", shakiness=4, accuracy=8, smoothing=10, deshake_iterations=1),
    "extreme": StabilizationProfile("extreme", shakiness=10, accuracy=15, smoothing=40, deshake_iterations=3),
}


def stabilize_video(
    input_path: str,
    output_path: str,
    profile: str = "documentary",
    temp_dir: Optional[str] = None,
) -> str:
    """对视频进行防抖处理

    两阶段流程：
    1. vidstabdetect - 分析运动
    2. vidstabtransform - 应用稳定

    Args:
        input_path: 输入视频
        output_path: 输出视频
        profile: 防抖预设 (vlog_action/documentary/cinematic/extreme)
        temp_dir: 临时文件目录
    """
    prof = PROFILES.get(profile, PROFILES["documentary"])

    if temp_dir is None:
        temp_dir = str(Path(output_path).parent / "stab_temp")
    os.makedirs(temp_dir, exist_ok=True)

    transforms_file = os.path.join(temp_dir, "transforms.trf")

    # 阶段1：分析运动
    cmd_detect = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"vidstabdetect=shakiness={prof.shakiness}:accuracy={prof.accuracy}:result={transforms_file}",
        "-f", "null", "-",
    ]
    subprocess.run(cmd_detect, capture_output=True, check=True)

    # 阶段2：应用稳定
    cmd_transform = [
        "ffmpeg", "-y", "-i", input_path,
        "-vf", f"vidstabtransform=input={transforms_file}:smoothing={prof.smoothing}:zoom=5:interpol=bicubic,unsharp=5:5:0.8:3:3:0.4",
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "copy",
        output_path,
    ]
    subprocess.run(cmd_transform, capture_output=True, check=True)

    # 清理临时文件
    if os.path.exists(transforms_file):
        os.remove(transforms_file)

    return output_path
