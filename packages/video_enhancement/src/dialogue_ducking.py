"""
对话闪避 - VAD 检测人声，自动压低 BGM 音量

使用 webrtcvad 或 FFmpeg silencedetect 检测人声时间段，
在有人声时自动压低 BGM 音量，无人声时恢复。

用法：
    from packages.video_enhancement.src.dialogue_ducking import duck_audio
    duck_audio("video.mp4", "bgm.mp3", "output.mp4")
"""

import subprocess
import json
import re
from pathlib import Path
from typing import List, Tuple
from dataclasses import dataclass


@dataclass
class VoiceSegment:
    """人声时间段"""
    start: float  # 秒
    end: float    # 秒


def detect_voice_segments_ffmpeg(video_path: str, threshold_db: float = -30.0, min_duration: float = 0.3) -> List[VoiceSegment]:
    """
    使用 FFmpeg silencedetect 检测有声段（反向：有声 = 有人声）

    Args:
        video_path: 视频/音频路径
        threshold_db: 静音阈值（dB），低于此值视为静音
        min_duration: 最小静音时长（秒）

    Returns:
        人声时间段列表
    """
    cmd = [
        "ffmpeg", "-i", video_path,
        "-af", f"silencedetect=noise={threshold_db}dB:d={min_duration}",
        "-f", "null", "-"
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    stderr = result.stderr

    # 解析 silencedetect 输出
    silence_starts = []
    silence_ends = []

    for line in stderr.split("\n"):
        if "silence_start:" in line:
            match = re.search(r"silence_start:\s*([\d.]+)", line)
            if match:
                silence_starts.append(float(match.group(1)))
        elif "silence_end:" in line:
            match = re.search(r"silence_end:\s*([\d.]+)", line)
            if match:
                silence_ends.append(float(match.group(1)))

    # 获取视频总时长
    duration_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        video_path
    ]
    dur_result = subprocess.run(duration_cmd, capture_output=True, text=True)
    total_duration = float(dur_result.stdout.strip()) if dur_result.stdout.strip() else 0

    # 反转：有声段 = 总时长 - 静音段
    voice_segments = []
    current_pos = 0.0

    for i in range(len(silence_starts)):
        silence_start = silence_starts[i]
        silence_end = silence_ends[i] if i < len(silence_ends) else total_duration

        # 静音之前的有声段
        if silence_start > current_pos:
            voice_segments.append(VoiceSegment(start=current_pos, end=silence_start))

        current_pos = silence_end

    # 最后一段
    if current_pos < total_duration:
        voice_segments.append(VoiceSegment(start=current_pos, end=total_duration))

    return voice_segments


def detect_voice_segments_simple(video_path: str, energy_threshold: float = 0.02) -> List[VoiceSegment]:
    """
    简单的能量检测（不依赖 webrtcvad）

    Args:
        video_path: 音频路径
        energy_threshold: 能量阈值

    Returns:
        人声时间段列表
    """
    try:
        import librosa
        import numpy as np

        y, sr = librosa.load(video_path, sr=16000)

        # 计算短时能量
        frame_length = int(0.025 * sr)  # 25ms 帧
        hop_length = int(0.010 * sr)    # 10ms 跳步

        rms = librosa.feature.rms(y=y, frame_length=frame_length, hop_length=hop_length)[0]
        rms_normalized = rms / (rms.max() + 1e-8)

        # 检测有声段
        is_voice = rms_normalized > energy_threshold

        # 合并连续有声帧为段
        segments = []
        in_voice = False
        voice_start = 0

        for i, v in enumerate(is_voice):
            t = i * hop_length / sr
            if v and not in_voice:
                in_voice = True
                voice_start = t
            elif not v and in_voice:
                in_voice = False
                if t - voice_start > 0.2:  # 最短 0.2 秒
                    segments.append(VoiceSegment(start=voice_start, end=t))

        if in_voice:
            segments.append(VoiceSegment(start=voice_start, end=len(y) / sr))

        return segments

    except ImportError:
        return []


def duck_audio(
    video_path: str,
    bgm_path: str,
    output_path: str,
    duck_level_db: float = -12.0,
    attack_ms: int = 200,
    release_ms: int = 500,
) -> str:
    """
    对话闪避：检测视频中的人声，有人声时压低 BGM

    Args:
        video_path: 输入视频（含原始音频）
        bgm_path: BGM 音频文件
        output_path: 输出视频路径
        duck_level_db: 闪避时 BGM 降低的分贝数（负值，如 -12 表示降低 12dB）
        attack_ms: 闪避攻击时间（毫秒）
        release_ms: 闪避释放时间（毫秒）

    Returns:
        输出文件路径
    """
    print(f"  对话闪避: {video_path} + {bgm_path}")

    # 检测人声段
    print("  检测人声段...")
    voice_segments = detect_voice_segments_ffmpeg(video_path)

    if not voice_segments:
        print("  未检测到人声，使用简单能量检测...")
        voice_segments = detect_voice_segments_simple(video_path)

    if not voice_segments:
        print("  未检测到人声，直接混合音频")
        _mix_without_ducking(video_path, bgm_path, output_path)
        return output_path

    print(f"  检测到 {len(voice_segments)} 个人声段")

    # 构建 FFmpeg 的 sidechaincompress 滤镜
    # 当原始音频有信号时，压缩 BGM 音量
    attack_s = attack_ms / 1000.0
    release_s = release_ms / 1000.0

    # 使用 FFmpeg 的 sidechaincompress 实现闪避
    # 原始音频作为 sidechain 信号，BGM 作为被压缩信号
    filter_complex = (
        f"[0:a]aresample=44100[voice];"
        f"[1:a]aresample=44100[bgm];"
        f"[bgm][voice]sidechaincompress="
        f"threshold=0.02:ratio=20:attack={attack_s * 1000}:release={release_s * 1000}:"
        f"level_sc=1[ducked];"
        f"[voice][ducked]amix=inputs=2:duration=shortest:dropout_transition=2[audio_out]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", bgm_path,
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[audio_out]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        print(f"  sidechaincompress 失败，使用手动音量控制...")
        _duck_with_volume_filter(video_path, bgm_path, output_path, voice_segments, duck_level_db)
    else:
        print(f"  对话闪避完成: {output_path}")

    return output_path


def _mix_without_ducking(video_path: str, bgm_path: str, output_path: str):
    """不闪避，直接混合"""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", bgm_path,
        "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=shortest:dropout_transition=2[audio]",
        "-map", "0:v:0",
        "-map", "[audio]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True, timeout=300)


def _duck_with_volume_filter(
    video_path: str,
    bgm_path: str,
    output_path: str,
    voice_segments: List[VoiceSegment],
    duck_level_db: float,
):
    """使用 volume 滤镜手动实现闪避"""
    # 构建 BGM 的音量表达式：有人声时降低音量
    duck_linear = 10 ** (duck_level_db / 20.0)  # dB 转线性

    # 构建条件表达式
    conditions = []
    for seg in voice_segments:
        conditions.append(f"between(t,{seg.start:.3f},{seg.end:.3f})")

    if conditions:
        # 任何一个条件为真时闪避
        expr = "+".join(conditions)
        volume_expr = f"if(gt({expr},0),{duck_linear},1.0)"
    else:
        volume_expr = "1.0"

    filter_complex = (
        f"[1:a]volume='{volume_expr}'[bgm_ducked];"
        f"[0:a][bgm_ducked]amix=inputs=2:duration=shortest:dropout_transition=2[audio]"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-i", bgm_path,
        "-filter_complex", filter_complex,
        "-map", "0:v:0",
        "-map", "[audio]",
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        output_path
    ]

    subprocess.run(cmd, capture_output=True, check=True, timeout=300)
    print(f"  对话闪避完成: {output_path}")
