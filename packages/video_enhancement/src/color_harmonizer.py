"""
颜色协调器 - 镜头间色彩一致性

使用直方图匹配实现镜头间色彩平滑过渡，
避免混剪时色彩跳变。

用法：
    from packages.video_enhancement.src.color_harmonizer import harmonize_clips
    harmonize_clips(["shot1.mp4", "shot2.mp4"], ["out1.mp4", "out2.mp4"])
"""

import subprocess
import json
from pathlib import Path
from typing import List, Optional


def get_video_histogram(video_path: str, sample_seconds: float = 2.0) -> dict:
    """获取视频的平均直方图统计"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = float(result.stdout.strip()) if result.stdout.strip() else 0

    # 从视频中间取样
    seek = max(0, duration / 2 - sample_seconds / 2)

    # 使用 FFmpeg 的 histogram 滤镜获取色彩统计
    cmd = [
        "ffmpeg", "-ss", str(seek), "-t", str(sample_seconds),
        "-i", video_path,
        "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG",
        "-f", "null", "-"
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

    # 解析 Y/U/V 平均值
    y_vals, u_vals, v_vals = [], [], []
    for line in result.stderr.split("\n"):
        if "YAVG" in line:
            parts = line.split("=")
            if len(parts) == 2:
                try:
                    y_vals.append(float(parts[1].strip()))
                except ValueError:
                    pass

    return {
        "y_avg": sum(y_vals) / len(y_vals) if y_vals else 128,
        "duration": duration,
    }


def harmonize_clips(
    input_paths: List[str],
    output_paths: List[str],
    strength: float = 0.5,
) -> List[str]:
    """
    对一组镜头进行色彩协调

    使用第一个镜头作为参考色调，后续镜头向其靠拢。

    Args:
        input_paths: 输入视频路径列表
        output_paths: 输出视频路径列表
        strength: 协调强度 (0.0 ~ 1.0)

    Returns:
        输出文件路径列表
    """
    if not input_paths:
        return []

    print(f"  色彩协调: {len(input_paths)} 个镜头, 强度={strength}")

    # 获取所有镜头的亮度统计
    histograms = []
    for path in input_paths:
        hist = get_video_histogram(path)
        histograms.append(hist)

    # 计算平均亮度作为参考
    avg_y = sum(h["y_avg"] for h in histograms) / len(histograms)

    # 对每个镜头应用色彩校正
    for i, (in_path, out_path) in enumerate(zip(input_paths, output_paths)):
        current_y = histograms[i]["y_avg"]
        diff = avg_y - current_y

        if abs(diff) < 2:  # 差异太小，跳过
            if in_path != out_path:
                subprocess.run(["ffmpeg", "-y", "-i", in_path, "-c", "copy", out_path],
                               capture_output=True)
            continue

        # 调整亮度和对比色
        adjustment = diff * strength
        brightness = adjustment / 255.0  # FFmpeg eq 的 brightness 范围是 -1 到 1

        cmd = [
            "ffmpeg", "-y",
            "-i", in_path,
            "-vf", f"eq=brightness={brightness:.4f}:saturation=1.0",
            "-c:v", "libx264", "-crf", "23", "-preset", "medium",
            "-c:a", "copy",
            out_path
        ]
        subprocess.run(cmd, capture_output=True, timeout=120)

    print(f"  色彩协调完成")
    return output_paths


def harmonize_single(
    reference_path: str,
    target_path: str,
    output_path: str,
    strength: float = 0.5,
) -> str:
    """
    将目标视频的色彩向参考视频靠拢

    Args:
        reference_path: 参考视频路径
        target_path: 目标视频路径
        output_path: 输出路径
        strength: 协调强度

    Returns:
        输出文件路径
    """
    ref_hist = get_video_histogram(reference_path)
    tgt_hist = get_video_histogram(target_path)

    diff = ref_hist["y_avg"] - tgt_hist["y_avg"]

    if abs(diff) < 2:
        if target_path != output_path:
            subprocess.run(["ffmpeg", "-y", "-i", target_path, "-c", "copy", output_path],
                           capture_output=True)
        return output_path

    adjustment = diff * strength
    brightness = adjustment / 255.0

    cmd = [
        "ffmpeg", "-y",
        "-i", target_path,
        "-vf", f"eq=brightness={brightness:.4f}:saturation=1.0",
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
        "-c:a", "copy",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=120)

    return output_path
