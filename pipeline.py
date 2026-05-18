"""
真正的 Montage Pipeline
输入：视频文件 + BGM
输出：混剪视频
"""

import subprocess
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

# 添加项目路径
import sys
sys.path.insert(0, str(Path(__file__).parent))

from packages.core_types.models import (
    Shot, Beat, TimelineEntry, HighlightScore,
    BeatAnalysis, MotionData, MusicSegment
)


class ShotDetector:
    """镜头检测 - 使用 FFmpeg scene detect"""

    def __init__(self, cache_dir: str = "cache/shots"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def detect(self, video_path: str, threshold: float = 0.3, video_index: int = 0) -> List[Shot]:
        """检测镜头并切割"""
        print(f"  检测镜头: {video_path}")

        if not Path(video_path).exists():
            print(f"  文件不存在: {video_path}")
            return []

        # 获取视频时长
        try:
            duration = self._get_duration(video_path)
        except Exception as e:
            print(f"  获取时长失败: {e}")
            return []

        if duration <= 0:
            print(f"  视频时长为0: {video_path}")
            return []

        # 使用 FFmpeg 检测场景变化
        scenes = self._detect_scenes(video_path, threshold)

        # 如果没检测到场景变化，整个视频作为一个镜头
        if not scenes:
            scenes = [(0.0, duration)]

        # 切割视频
        shots = []
        for i, (start, end) in enumerate(scenes):
            if end - start < 0.1:
                continue

            shot_path = self.cache_dir / f"shot_{i:04d}.mp4"

            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", video_path,
                "-to", str(end - start),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                str(shot_path)
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, timeout=30)
                if result.returncode != 0 or not shot_path.exists():
                    print(f"  镜头切割失败: shot_{i:04d}")
                    continue
            except subprocess.TimeoutExpired:
                print(f"  镜头切割超时: shot_{i:04d}")
                continue

            shots.append(Shot(
                shot_id=video_index * 10000 + i,
                start_time=start,
                end_time=end,
                duration=end - start,
                file_path=str(shot_path),
                source_video=video_path,
            ))

        # 如果切割全部失败，直接复制原视频作为单镜头
        if not shots and duration > 0:
            print(f"  切割失败，使用原视频作为单镜头")
            shots.append(Shot(
                shot_id=video_index * 10000,
                start_time=0.0,
                end_time=duration,
                duration=duration,
                file_path=video_path,
                source_video=video_path,
            ))

        print(f"  检测到 {len(shots)} 个镜头")
        return shots

    def _detect_scenes(self, video_path: str, threshold: float) -> List[tuple]:
        """使用 FFmpeg 检测场景变化"""
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-"
        ]

        result = subprocess.run(cmd, capture_output=True)

        # 解析时间点（用 bytes 处理避免编码问题）
        import re
        stderr_text = result.stderr.decode('utf-8', errors='ignore') if result.stderr else ""
        times = []
        for line in stderr_text.split('\n'):
            if 'pts_time' in line:
                match = re.search(r'pts_time:(\d+\.?\d*)', line)
                if match:
                    times.append(float(match.group(1)))

        # 生成场景列表
        scenes = []
        for i in range(len(times)):
            start = times[i]
            end = times[i + 1] if i + 1 < len(times) else self._get_duration(video_path)
            scenes.append((start, end))

        # 添加第一个场景
        if scenes and scenes[0][0] > 0:
            scenes.insert(0, (0.0, scenes[0][0]))

        return scenes

    def _get_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True)
        return float(result.stdout.decode('utf-8', errors='ignore').strip())


class MotionAnalyzer:
    """运动分析 - 使用 OpenCV 光流"""

    def analyze(self, shot_path: str) -> MotionData:
        """分析镜头运动"""
        try:
            import cv2

            cap = cv2.VideoCapture(shot_path)
            if not cap.isOpened():
                return MotionData()

            # 读取第一帧
            ret, prev_frame = cap.read()
            if not ret:
                return MotionData()

            prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)

            magnitudes = []
            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # 计算光流
                flow = cv2.calcOpticalFlowFarneback(
                    prev_gray, gray,
                    None, 0.5, 3, 15, 3, 5, 1.2, 0
                )

                # 计算运动幅度
                magnitude = np.sqrt(flow[..., 0]**2 + flow[..., 1]**2)
                magnitudes.append(np.mean(magnitude))

                prev_gray = gray

            cap.release()

            if not magnitudes:
                return MotionData()

            avg_magnitude = np.mean(magnitudes)
            shake = np.std(magnitudes)

            return MotionData(
                magnitude=float(avg_magnitude),
                shake=float(shake)
            )

        except ImportError:
            # 如果没有 OpenCV，返回默认值
            return MotionData(magnitude=0.5, shake=0.1)


class BeatAnalyzer:
    """节拍分析 - 使用 librosa"""

    def analyze(self, audio_path: str) -> BeatAnalysis:
        """分析 BGM"""
        print(f"  分析 BGM: {audio_path}")

        try:
            import librosa

            # 加载音频
            y, sr = librosa.load(audio_path, sr=22050)
            duration = len(y) / sr

            # 检测节拍 + onset 强度
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

            # 如果没有检测到节拍，生成默认节拍
            if len(beat_times) == 0:
                print("  警告: 未检测到节拍，使用默认节拍")
                beat_interval = 0.5  # 120 BPM
                beat_times = np.arange(0, duration, beat_interval)

            # 计算 onset 强度（用于区分强拍/弱拍）
            onset_env = librosa.onset.onset_strength(y=y, sr=sr)
            onset_times = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr)

            # 计算能量
            rms = librosa.feature.rms(y=y)[0]
            rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
            rms_normalized = (rms - rms.min()) / (rms.max() - rms.min() + 1e-8)

            # 为每个节拍分类强/弱拍
            # 强拍：onset 强度高于中位数 + 能量高于中位数
            onset_at_beats = []
            for bt in beat_times:
                idx = np.argmin(np.abs(onset_times - bt))
                onset_at_beats.append(onset_env[idx])

            onset_median = np.median(onset_at_beats) if onset_at_beats else 0
            energy_median = np.median(rms_normalized)

            # 找高潮段
            threshold = np.percentile(rms_normalized, 80)
            drops = []
            in_drop = False
            drop_start = 0

            for i, (t, e) in enumerate(zip(rms_times, rms_normalized)):
                if e > threshold and not in_drop:
                    in_drop = True
                    drop_start = t
                elif e <= threshold and in_drop:
                    in_drop = False
                    if t - drop_start > 1.0:
                        drops.append({"start": drop_start, "end": t})

            # 生成能量曲线
            energy_curve = [
                {"time": float(t), "energy": float(e)}
                for t, e in zip(rms_times[::100], rms_normalized[::100])
            ]

            # 创建节拍对象（区分强拍/弱拍）
            beats = []
            for i, t in enumerate(beat_times):
                onset_val = onset_at_beats[i] if i < len(onset_at_beats) else 0

                # 获取该时刻的能量
                e_idx = np.argmin(np.abs(rms_times - t))
                energy_val = rms_normalized[e_idx]

                # 分类：onset 强度高 + 能量高 = 强拍
                is_strong = (onset_val > onset_median * 1.2) or (energy_val > energy_median * 1.3)

                beat_type = "strong" if is_strong else "normal"
                strength = min(float(onset_val / (onset_median + 1e-8)), 2.0) / 2.0

                beats.append(Beat(
                    time=float(t),
                    strength=strength,
                    beat_type=beat_type,
                ))

            return BeatAnalysis(
                beats=beats,
                tempo=float(tempo),
                energy_curve=energy_curve,
                drops=drops,
                segments=[],
                duration=duration
            )

        except ImportError:
            # 如果没有 librosa，返回模拟数据
            print("  警告: librosa 未安装，使用模拟节拍")
            return self._mock_analysis()

    def _mock_analysis(self) -> BeatAnalysis:
        """模拟分析结果"""
        beats = [
            Beat(time=i * 0.5, strength=0.8, beat_type="normal")
            for i in range(20)
        ]
        return BeatAnalysis(
            beats=beats,
            tempo=120.0,
            energy_curve=[],
            drops=[],
            segments=[],
            duration=10.0
        )


class HighlightScorer:
    """高光评分 - 5 维评分系统

    维度：运动幅度(0.25)、镜头多样性(0.20)、人脸情感(0.25)、镜头运动(0.15)、音频(0.15)
    """

    def __init__(self):
        self.weights = {
            "motion": 0.25,
            "shot_diversity": 0.20,
            "face_emotion": 0.25,
            "camera_movement": 0.15,
            "audio": 0.15,
        }

    def score(self, shot: Shot, motion: MotionData) -> float:
        """计算高光分数（5 维）"""
        w = self.weights

        # 1. 运动幅度（sigmoid 归一化）
        motion_score = self._sigmoid(motion.magnitude, center=3.0, scale=1.0)

        # 2. 镜头时长多样性（1-3 秒最佳）
        duration_score = self._duration_score(shot.duration)

        # 3. 人脸情感（如果有 action 信息）
        face_score = self._face_emotion_score(shot)

        # 4. 镜头运动（shake + zoom）
        camera_score = self._camera_movement_score(motion)

        # 5. 音频能量（如果可用）
        audio_score = self._audio_score(shot)

        total = (
            w["motion"] * motion_score +
            w["shot_diversity"] * duration_score +
            w["face_emotion"] * face_score +
            w["camera_movement"] * camera_score +
            w["audio"] * audio_score
        )

        return min(max(total, 0.0), 1.0)

    def _sigmoid(self, x: float, center: float = 3.0, scale: float = 1.0) -> float:
        """Sigmoid 归一化"""
        import math
        return 1.0 / (1.0 + math.exp(-scale * (x - center)))

    def _duration_score(self, duration: float) -> float:
        """时长分数（1-3 秒最佳）"""
        if 1.0 <= duration <= 3.0:
            return 1.0
        elif duration < 1.0:
            return duration
        else:
            return max(0.3, 1.0 - (duration - 3.0) * 0.1)

    def _face_emotion_score(self, shot: Shot) -> float:
        """人脸情感分数（基于 action 信息）"""
        if not shot.actions:
            return 0.5  # 默认中性

        # 情感权重映射
        emotion_weights = {
            "angry": 0.9, "fear": 0.8, "surprise": 0.7,
            "sad": 0.6, "happy": 0.5, "disgust": 0.4, "neutral": 0.1,
        }

        # 从 actions 中提取情感
        for action in shot.actions:
            action_lower = action.lower() if isinstance(action, str) else ""
            for emotion, weight in emotion_weights.items():
                if emotion in action_lower:
                    return weight

        return 0.3  # 无情感信息

    def _camera_movement_score(self, motion: MotionData) -> float:
        """镜头运动分数（shake + zoom 复合）"""
        shake_score = min(motion.shake / 3.0, 1.0) * 0.4
        zoom_score = min(abs(motion.zoom - 1.0) / 0.5, 1.0) * 0.3
        direction_score = min(
            (abs(motion.direction_x) + abs(motion.direction_y)) / 5.0, 1.0
        ) * 0.3
        return shake_score + zoom_score + direction_score

    def _audio_score(self, shot: Shot) -> float:
        """音频能量分数"""
        # 如果 shot 有额外的音频信息，使用它
        # 否则基于时长估算
        if shot.duration < 0.5:
            return 0.2
        elif shot.duration > 10:
            return 0.4
        return 0.6


class BeatSyncEngine:
    """卡点同步引擎 - 支持强弱拍分类 + 转场效果"""

    # 转场类型映射
    TRANSITION_TYPES = ["cut", "fade", "dissolve", "wipe", "flash", "zoom", "blur"]

    def sync(
        self,
        shots: List[Shot],
        beats: List[Beat],
        style: str = "dynamic"
    ) -> List[TimelineEntry]:
        """将镜头与节拍同步（去重约束已在选择阶段完成）"""
        if not shots or not beats:
            return []

        # 保持输入顺序（已经是交替排列的）
        sorted_shots = shots

        # 获取风格参数
        params = self._get_style_params(style)

        timeline = []
        beat_idx = 0

        for i, shot in enumerate(sorted_shots):
            if beat_idx >= len(beats):
                break

            # 获取当前节拍
            beat = beats[beat_idx]

            # 获取当前节拍
            beat = beats[beat_idx]

            # 根据高光分数 + 拍类型决定时长和速度
            if shot.highlight_score > 0.7:
                duration = params["fast"]
            elif shot.highlight_score > 0.4:
                duration = params["medium"]
            else:
                duration = params["slow"]

            # 强拍：慢动作（强调高光镜头）；弱拍：快速（紧凑节奏）
            speed_factor = 1.0
            if beat.beat_type == "strong":
                speed_factor = params.get("slow_speed", 0.5) if shot.highlight_score > 0.6 else 0.7
            else:
                speed_factor = params.get("fast_speed", 1.5)

            # 量化到节拍
            beat_interval = beats[1].time - beats[0].time if len(beats) > 1 else 0.5
            duration = round(duration / beat_interval) * beat_interval

            # 选择转场类型
            transition_type = self._pick_transition(beat, shot, style)
            transition_duration = 0.5 if transition_type != "cut" else 0.0

            # 创建时间线条目
            entry = TimelineEntry(
                shot_id=shot.shot_id,
                shot_path=shot.file_path or "",
                start_time=beat.time,
                end_time=beat.time + duration,
                duration=duration,
                beat_time=beat.time,
                speed_factor=speed_factor,
                transition_type=transition_type,
                transition_duration=transition_duration
            )

            timeline.append(entry)

            # 跳过相应的节拍（用 round 替代 int 避免截断导致重叠）
            beats_to_skip = max(1, round(duration / beat_interval))
            beat_idx += beats_to_skip

        # 按时间排序
        timeline.sort(key=lambda x: x.start_time)

        return timeline

    def _get_style_params(self, style: str) -> Dict[str, float]:
        """获取风格参数"""
        params = {
            "dynamic": {"fast": 1.0, "medium": 1.5, "slow": 2.5, "slow_speed": 0.7, "fast_speed": 1.2},
            "calm": {"fast": 1.5, "medium": 2.5, "slow": 4.0, "slow_speed": 0.8, "fast_speed": 1.1},
            "intense": {"fast": 0.5, "medium": 1.0, "slow": 1.5, "slow_speed": 0.5, "fast_speed": 1.5},
        }
        return params.get(style, params["dynamic"])

    def _pick_transition(self, beat: Beat, shot: Shot, style: str) -> str:
        """根据拍类型和风格选择转场效果"""
        import random

        # 强拍用更有冲击力的转场
        if beat.beat_type == "strong":
            if style == "intense":
                return random.choice(["flash", "zoom", "cut"])
            elif style == "calm":
                return random.choice(["fade", "dissolve"])
            else:
                return random.choice(["cut", "fade", "flash"])

        # 弱拍用平滑转场
        if style == "intense":
            return "cut"
        elif style == "calm":
            return random.choice(["dissolve", "fade"])
        else:
            return random.choice(["cut", "dissolve"])


class VideoRenderer:
    """视频渲染器"""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def render(
        self,
        timeline: List[TimelineEntry],
        bgm_path: str,
        output_path: str
    ) -> str:
        """渲染最终视频（支持转场效果）"""
        print(f"  渲染视频...")

        # 收集有效的镜头（按时间排序）
        valid_entries = [e for e in timeline if e.shot_path and Path(e.shot_path).exists()]
        if not valid_entries:
            raise ValueError("没有有效的镜头文件")

        temp_files = []

        # Step 1: 截取到时间线时长 + 调整速度 + 复制到短路径
        import shutil
        prepared = []
        for idx, entry in enumerate(valid_entries):
            # 先截取到时间线指定的时长
            trimmed_path = self.output_dir / f"trim_{idx}.mp4"
            self._trim_video(entry.shot_path, str(trimmed_path), entry.duration)
            temp_files.append(trimmed_path)

            if entry.speed_factor != 1.0:
                temp_path = self.output_dir / f"speed_{idx}.mp4"
                self._adjust_speed(str(trimmed_path), str(temp_path), entry.speed_factor)
                temp_files.append(temp_path)
                prepared.append(str(temp_path))
            else:
                prepared.append(str(trimmed_path))

        # Step 2: 检查是否有非 cut 转场
        has_transitions = any(
            getattr(e, "transition_type", "cut") != "cut" and getattr(e, "transition_duration", 0) > 0
            for e in valid_entries
        )

        if has_transitions and len(prepared) > 1:
            # 使用 xfade 滤镜应用转场
            concat_video = self._render_with_transitions(prepared, valid_entries)
        else:
            # 简单拼接（无转场或全部是 cut）
            concat_video = self._render_concat(prepared)

        temp_files.append(concat_video)

        # Step 3: 添加 BGM
        cmd = [
            "ffmpeg", "-y",
            "-i", str(concat_video),
            "-i", bgm_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        # 清理临时文件
        for f in temp_files:
            Path(f).unlink(missing_ok=True)

        print(f"  输出: {output_path}")
        return output_path

    def _render_concat(self, video_paths: List[str]) -> str:
        """简单拼接（无转场）"""
        concat_file = self.output_dir / "concat.txt"
        with open(concat_file, 'w') as f:
            for path in video_paths:
                f.write(f"file '{Path(path).resolve().as_posix()}'\n")

        concat_video = self.output_dir / "concat.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(concat_video)
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        concat_file.unlink(missing_ok=True)
        return str(concat_video)

    def _render_with_transitions(self, video_paths: List[str], entries: List[TimelineEntry]) -> str:
        """使用 xfade 滤镜渲染带转场的视频"""
        # 获取每个视频的时长
        durations = []
        for path in video_paths:
            dur = self._get_duration(path)
            durations.append(dur)

        # 构建 xfade 滤镜链
        # xfade 需要累加偏移量：offset = 前面所有视频时长之和 - 转场时长之和
        filter_parts = []
        cumulative_offset = 0.0
        current_label = "[0:v]"

        for i in range(1, len(video_paths)):
            entry = entries[i] if i < len(entries) else entries[-1]
            trans_type = getattr(entry, "transition_type", "cut")
            trans_dur = getattr(entry, "transition_duration", 0.5)

            if trans_type == "cut" or trans_dur <= 0:
                # 硬切：直接 concat
                cumulative_offset += durations[i - 1]
                filter_parts.append(f"{current_label}[{i}:v]concat=n=2:v=1[out{i}]")
                current_label = f"[out{i}]"
            else:
                # xfade 转场
                offset = sum(durations[:i]) - trans_dur * i
                if offset < 0:
                    offset = sum(durations[:i]) * 0.8

                # 映射转场类型到 xfade
                xfade_map = {
                    "fade": "fade", "dissolve": "dissolve",
                    "wipe": "wipeleft", "flash": "fadeblack",
                    "zoom": "circlecrop", "blur": "fadeblack",
                }
                xfade_type = xfade_map.get(trans_type, "fade")

                filter_parts.append(
                    f"{current_label}[{i}:v]xfade=transition={xfade_type}:"
                    f"duration={trans_dur}:offset={offset:.3f}[out{i}]"
                )
                current_label = f"[out{i}]"

        filter_complex = ";".join(filter_parts)

        # 构建 FFmpeg 输入和命令
        concat_video = self.output_dir / "concat.mp4"
        cmd = ["ffmpeg", "-y"]
        for path in video_paths:
            cmd.extend(["-i", path])
        cmd.extend([
            "-filter_complex", filter_complex,
            "-map", current_label,
            "-c:v", "libx264", "-crf", "23", "-preset", "medium",
            str(concat_video)
        ])

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            # 回退到简单拼接
            print(f"  xfade 失败，回退到简单拼接")
            return self._render_concat(video_paths)

        return str(concat_video)

    def _get_duration(self, video_path: str) -> float:
        """获取视频时长"""
        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        try:
            return float(result.stdout.strip())
        except ValueError:
            return 2.0

    def _trim_video(self, input_path: str, output_path: str, duration: float):
        """截取视频到指定时长"""
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)

    def _adjust_speed(self, input_path: str, output_path: str, speed: float):
        """调整视频速度"""
        pts = 1.0 / speed
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", f"setpts={pts}*PTS",
            "-an",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)


class MontagePipeline:
    """混剪 Pipeline - 真正的端到端流程"""

    def __init__(self, cache_dir: str = "cache", output_dir: str = "output"):
        self.cache_dir = cache_dir
        self.output_dir = output_dir

        self.shot_detector = ShotDetector(f"{cache_dir}/shots")
        self.motion_analyzer = MotionAnalyzer()
        self.beat_analyzer = BeatAnalyzer()
        self.scorer = HighlightScorer()
        self.sync_engine = BeatSyncEngine()
        self.renderer = VideoRenderer(output_dir)

    def run(
        self,
        video_paths: List[str],
        bgm_path: str,
        style: str = "dynamic",
        output_name: str = "final.mp4",
        threshold: float = 0.2,
        color_preset: str = None,
        enable_reframe: bool = False,
        reframe_aspect: float = 9 / 16,
        enable_ducking: bool = False,
        duck_level_db: float = -12.0,
        enable_harmonize: bool = False,
        harmonize_strength: float = 0.5,
    ) -> str:
        """
        运行完整混剪流程

        Args:
            video_paths: 视频文件路径列表
            bgm_path: BGM 文件路径
            style: 风格 (dynamic, calm, intense)
            output_name: 输出文件名
            threshold: 镜头检测灵敏度 (0.01~1.0，越小切得越细)
            color_preset: 颜色分级预设 (如 cinematic, vibrant, vintage 等)
            enable_reframe: 是否启用自动竖屏裁切
            reframe_aspect: 竖屏裁切目标宽高比 (默认 9:16)
            enable_ducking: 是否启用对话闪避
            duck_level_db: 闪避降低分贝数 (默认 -12dB)
            enable_harmonize: 是否启用色彩协调
            harmonize_strength: 色彩协调强度 (0.0~1.0)

        Returns:
            输出文件路径
        """
        print("=" * 50)
        print("AI Montage Agent - 开始混剪")
        print("=" * 50)

        # Step 1: 检测镜头
        print(f"\n[1/6] 检测镜头 (阈值: {threshold})...")
        if not video_paths:
            raise ValueError("没有可用的视频文件，请检查搜索关键词或上传文件")

        all_shots = []
        for video_idx, video_path in enumerate(video_paths):
            print(f"  处理视频: {Path(video_path).name}")
            shots = self.shot_detector.detect(video_path, threshold=threshold, video_index=video_idx)
            all_shots.extend(shots)

        if not all_shots:
            raise ValueError("没有检测到任何镜头，视频文件可能损坏或格式不支持")

        # Step 2: 分析运动
        print("\n[2/6] 分析运动...")
        for shot in all_shots:
            motion = self.motion_analyzer.analyze(shot.file_path)
            shot.motion_score = motion.magnitude

        # Step 3: 评分高光
        print("\n[3/6] 评分高光...")
        for shot in all_shots:
            motion = MotionData(magnitude=shot.motion_score)
            shot.highlight_score = self.scorer.score(shot, motion)

        # Step 4: 分析 BGM
        print("\n[4/6] 分析 BGM...")
        beat_analysis = self.beat_analyzer.analyze(bgm_path)

        # Step 5: 卡点同步
        print("\n[5/6] 卡点同步...")
        # 按 source_video 分组，每视频最多取 top N 个镜头（带最小间隔）
        max_per_video = 15
        min_gap = 20  # 同一视频相邻镜头的最小间隔（确保视觉差异）
        video_shots: Dict[str, List[Shot]] = {}
        for shot in all_shots:
            key = shot.source_video or "unknown"
            if key not in video_shots:
                video_shots[key] = []
            video_shots[key].append(shot)

        # 每个视频取 top max_per_video 个高分镜头（带间隔约束）
        per_video_lists = []
        for key, shots in video_shots.items():
            sorted_group = sorted(shots, key=lambda s: s.highlight_score, reverse=True)
            selected = []
            last_id = -999
            for shot in sorted_group:
                if len(selected) >= max_per_video:
                    break
                if abs(shot.shot_id - last_id) >= min_gap:
                    selected.append(shot)
                    last_id = shot.shot_id
            per_video_lists.append(selected)

        # 交替排列不同视频的镜头（避免连续同源）
        balanced_shots = []
        max_len = max(len(lst) for lst in per_video_lists) if per_video_lists else 0
        for i in range(max_len):
            for lst in per_video_lists:
                if i < len(lst):
                    balanced_shots.append(lst[i])

        # 截取 top 50（保持交替排列，不按分数重新排序）
        max_shots = min(50, len(balanced_shots))
        top_shots = balanced_shots[:max_shots]
        print(f"  选择 Top {max_shots} 高光镜头（共 {len(all_shots)} 个，来自 {len(video_shots)} 个视频）")
        timeline = self.sync_engine.sync(top_shots, beat_analysis.beats, style)

        if not timeline:
            raise ValueError("时间线为空")

        # 存储时间线数据（供导出使用）
        self._last_timeline = timeline
        self._last_bgm_path = bgm_path
        self._last_total_duration = sum(e.duration for e in timeline)

        # Step 6: 渲染 + 后处理
        print("\n[6/6] 渲染输出...")
        output_path = f"{self.output_dir}/{output_name}"
        result = self.renderer.render(timeline, bgm_path, output_path)

        # 后处理：色彩协调（渲染前对镜头做，不是对最终视频做）
        if enable_harmonize:
            print("\n  色彩协调...")
            try:
                from packages.video_enhancement.src.color_harmonizer import harmonize_clips
                shot_paths = [e.shot_path for e in timeline if e.shot_path and Path(e.shot_path).exists()]
                if shot_paths:
                    harmonized = [p.replace(".mp4", "_harmonized.mp4") for p in shot_paths]
                    harmonize_clips(shot_paths, harmonized, strength=harmonize_strength)
                    # 重新渲染
                    for i, entry in enumerate(timeline):
                        if entry.shot_path and i < len(harmonized) and Path(harmonized[i]).exists():
                            entry.shot_path = harmonized[i]
                    result = self.renderer.render(timeline, bgm_path, output_path)
            except Exception as e:
                print(f"  色彩协调失败（跳过）: {e}")

        # 后处理：对话闪避
        if enable_ducking:
            print("\n  对话闪避...")
            try:
                from packages.video_enhancement.src.dialogue_ducking import duck_audio
                ducked_path = output_path.replace(".mp4", "_ducked.mp4")
                duck_audio(result, bgm_path, ducked_path, duck_level_db=duck_level_db)
                if Path(ducked_path).exists():
                    import os
                    os.replace(ducked_path, result)
            except Exception as e:
                print(f"  对话闪避失败（跳过）: {e}")

        # 后处理：颜色分级
        if color_preset and color_preset != "none":
            print(f"\n  颜色分级: {color_preset}...")
            try:
                from packages.video_enhancement.src.color_grading import apply_color_grade
                graded_path = output_path.replace(".mp4", "_graded.mp4")
                apply_color_grade(result, graded_path, preset=color_preset)
                if Path(graded_path).exists():
                    import os
                    os.replace(graded_path, result)
            except Exception as e:
                print(f"  颜色分级失败（跳过）: {e}")

        # 后处理：自动竖屏裁切
        if enable_reframe:
            print(f"\n  自动竖屏裁切...")
            try:
                from packages.video_enhancement.src.auto_reframe import auto_reframe
                reframed_path = output_path.replace(".mp4", "_9x16.mp4")
                auto_reframe(result, reframed_path, target_aspect=reframe_aspect)
                if Path(reframed_path).exists():
                    result = reframed_path
            except Exception as e:
                print(f"  竖屏裁切失败（跳过）: {e}")

        print("\n" + "=" * 50)
        print("混剪完成!")
        print(f"输出文件: {result}")
        print(f"镜头数量: {len(all_shots)}")
        print(f"节拍数量: {len(beat_analysis.beats)}")
        print(f"BPM: {beat_analysis.tempo:.1f}")
        print("=" * 50)

        return result


def main():
    """命令行入口"""
    import argparse

    parser = argparse.ArgumentParser(description="AI Montage Agent")
    parser.add_argument("--movies", nargs="+", help="本地视频文件路径")
    parser.add_argument("--query", type=str, help="搜索关键词，自动下载素材（与 --movies 二选一）")
    parser.add_argument("--source", type=str, default="playphrase",
                        choices=["playphrase", "quodb", "bilibili",
                                 "youtube", "dailymotion", "douyin", "ixigua", "acfun", "vimeo",
                                 "yarn", "zhaotaici"],
                        help="素材来源（默认 playphrase）")
    parser.add_argument("--clip-limit", type=int, default=20, help="最大下载片段数，默认 20（仅 --query 模式）")
    parser.add_argument("--bgm", help="BGM 文件路径（与 --bgm-query 二选一）")
    parser.add_argument("--bgm-query", help="BGM 搜索关键词，自动从B站搜索下载（与 --bgm 二选一）")
    parser.add_argument("--style", default="dynamic", choices=["dynamic", "calm", "intense"],
                        help="基础风格: dynamic(动感) / calm(舒缓) / intense(高燃)")
    parser.add_argument("--style-preset", type=str, default=None,
                        help="风格预设模板(如 action/wedding/cinematic/gaming 等)，会覆盖 --style 和 --enhance")
    parser.add_argument("--output", default="final.mp4", help="输出文件名")
    parser.add_argument("--threshold", type=float, default=0.2,
                        help="镜头检测灵敏度 0.01~1.0，越小切得越细（默认 0.2，混剪推荐 0.1~0.2）")
    # 新增功能参数
    parser.add_argument("--prompt", type=str, help="自然语言描述，如 '做一个30秒的漫威高燃混剪'")
    parser.add_argument("--subtitles", type=str, default="none",
                        choices=["none", "tiktok", "youtube", "minimal", "cinematic"],
                        help="字幕风格（默认 none）")
    parser.add_argument("--enhance", nargs="*", default=[],
                        help="视频增强选项: stabilize denoise color-grade")
    parser.add_argument("--export-timeline", type=str,
                        choices=["edl", "csv", "json", "xml", "otio"],
                        help="导出时间轴格式")
    parser.add_argument("--webui", action="store_true", help="启动 WebUI 界面")

    args = parser.parse_args()

    # 风格预设模板处理
    if args.style_preset:
        from packages.video_enhancement.src.style_templates import get_pipeline_params
        preset_params = get_pipeline_params(args.style_preset)
        args.style = preset_params.get("style", args.style)
        if preset_params.get("stabilize") and "stabilize" not in args.enhance:
            args.enhance.append("stabilize")
        if preset_params.get("color_preset"):
            args._color_preset = preset_params["color_preset"]
            if "color-grade" not in args.enhance:
                args.enhance.append("color-grade")
        print(f"  风格预设: {args.style_preset} -> style={args.style}, color={getattr(args, '_color_preset', 'default')}")

    # WebUI 模式
    if args.webui:
        from packages.webui import start_webui
        print("启动 WebUI: http://localhost:8000")
        start_webui()
        return

    # 校验参数：--movies 和 --query 二选一
    if not args.movies and not args.query:
        parser.error("请指定 --movies（本地视频）或 --query（搜索素材）")
    if args.movies and args.query:
        parser.error("--movies 和 --query 不能同时使用")

    # 获取视频路径
    if args.query:
        video_paths = _crawl_videos(args.query, args.source, args.clip_limit, parser)
        if not video_paths:
            return
    else:
        video_paths = args.movies
        for movie in video_paths:
            if not Path(movie).exists():
                print(f"错误: 视频文件不存在: {movie}")
                return

    # BGM 处理：本地文件或搜索下载
    bgm_path = args.bgm
    if not bgm_path and not args.bgm_query:
        print("错误: 请指定 --bgm（本地文件）或 --bgm-query（搜索关键词）")
        return
    if args.bgm_query:
        from packages.video_crawler.src.bgm_crawler import BgmCrawler
        bgm_crawler = BgmCrawler()
        bgm_paths = bgm_crawler.search_and_download(args.bgm_query, max_clips=1)
        if not bgm_paths:
            print("错误: 未找到 BGM")
            return
        bgm_path = bgm_paths[0]
        print(f"  使用 BGM: {bgm_path}")
    elif not Path(bgm_path).exists():
        print(f"错误: BGM 文件不存在: {bgm_path}")
        return

    # LLM 自然语言控制
    if args.prompt:
        from packages.ai_director import CreativeDirector
        director = CreativeDirector()
        instructions = director.interpret_prompt(args.prompt)
        if instructions:
            # 从 LLM 指令中提取参数
            style_map = {"intense": "intense", "calm": "calm", "dynamic": "dynamic"}
            llm_speed = instructions.get("pacing", {}).get("speed", "dynamic")
            args.style = style_map.get(llm_speed, args.style)
            print(f"  AI 导演建议风格: {args.style}")

            # 自动设置调色
            effects = instructions.get("effects", {})
            color_preset = effects.get("color_grading", "")
            if color_preset and color_preset != "neutral":
                if "color-grade" not in args.enhance:
                    args.enhance.append("color-grade")
                print(f"  AI 导演建议调色: {color_preset}")

            # 自动设置字幕
            if args.subtitles == "none" and instructions.get("subtitles"):
                args.subtitles = instructions["subtitles"]

            # 自动设置目标时长
            target_dur = instructions.get("constraints", {}).get("target_duration_sec")
            if target_dur:
                print(f"  AI 导演建议时长: {target_dur}s")

    # 运行 pipeline
    pipeline = MontagePipeline()
    result_path = pipeline.run(video_paths, bgm_path, args.style, args.output, threshold=args.threshold)

    # 后处理：视频增强
    if args.enhance:
        _apply_enhancement(result_path, args.enhance, getattr(args, '_color_preset', None))

    # 后处理：字幕压制
    if args.subtitles != "none":
        _apply_subtitles(result_path, args.subtitles)

    # 导出时间轴
    if args.export_timeline:
        _export_timeline(pipeline, args.export_timeline)


def _apply_enhancement(video_path: str, enhance_options: list, color_preset: str = None):
    """对输出视频应用增强"""
    from packages.video_enhancement import enhance_video, stabilize_video, apply_color_grade

    temp_path = video_path + ".enhanced.mp4"
    enhanced = False

    if "stabilize" in enhance_options:
        print("\n  应用防抖...")
        stabilize_video(video_path, temp_path)
        import shutil
        shutil.move(temp_path, video_path)
        enhanced = True

    if "denoise" in enhance_options:
        print("  应用降噪...")
        enhance_video(video_path, temp_path, denoise=True)
        import shutil
        shutil.move(temp_path, video_path)
        enhanced = True

    if "color-grade" in enhance_options:
        preset = color_preset or "cinematic"
        print(f"  应用调色: {preset}")
        apply_color_grade(video_path, temp_path, preset=preset)
        import shutil
        shutil.move(temp_path, video_path)
        enhanced = True

    if enhanced:
        print("  增强完成!")


def _apply_subtitles(video_path: str, style: str):
    """对输出视频应用字幕"""
    try:
        from packages.subtitle_engine import Transcriber, burn_captions
        import tempfile

        print(f"\n  生成字幕 (风格: {style})...")

        # 1. 用 Whisper 转录
        transcriber = Transcriber(backend="whisper", model_size="base")
        srt_path = video_path.replace(".mp4", ".srt")
        transcriber.transcribe(video_path, output_path=srt_path, output_format="srt")
        print(f"  字幕文件: {srt_path}")

        # 2. 烧录字幕
        output_path = video_path.replace(".mp4", "_subtitled.mp4")
        burn_captions(video_path, srt_path, style=style, output_path=output_path)

        # 3. 替换原文件
        import shutil
        shutil.move(output_path, video_path)
        print(f"  字幕烧录完成!")
    except ImportError as e:
        print(f"  字幕功能需要安装 whisper: pip install openai-whisper")
        print(f"  错误: {e}")
    except Exception as e:
        print(f"  字幕处理失败: {e}")


def _export_timeline(pipeline, format: str):
    """导出时间轴"""
    # OTIO 使用专用导出器
    if format == "otio":
        from packages.timeline_export.src.otio_exporter import export_otio_from_pipeline
        output_path = f"{pipeline.output_dir}/timeline.otio"
        export_otio_from_pipeline(pipeline, output_path)
        return

    from packages.timeline_export import TimelineExporter, Timeline, Clip

    # 从 pipeline 中收集的时间线数据构建 Timeline 对象
    timeline_entries = getattr(pipeline, '_last_timeline', [])
    bgm_path = getattr(pipeline, '_last_bgm_path', '')
    total_duration = getattr(pipeline, '_last_total_duration', 0.0)

    if not timeline_entries:
        print(f"\n  导出时间轴: 无时间线数据（需要先运行 pipeline）")
        return

    # 转换为 Clip 对象
    clips = []
    for entry in timeline_entries:
        clips.append(Clip(
            source_path=getattr(entry, 'shot_path', ''),
            start_time=getattr(entry, 'start_time', 0.0),
            duration=getattr(entry, 'duration', 0.0),
            timeline_start=getattr(entry, 'start_time', 0.0),
        ))

    timeline = Timeline(
        clips=clips,
        audio_path=bgm_path,
        total_duration=total_duration,
    )

    exporter = TimelineExporter(output_dir=pipeline.output_dir)
    exported = exporter.export(timeline, formats=[format])

    for fmt, path in exported.items():
        print(f"  导出 {fmt.upper()}: {path}")


def _crawl_videos(keyword: str, source: str, clip_limit: int, parser) -> list:
    """根据来源爬取视频"""
    if source == "bilibili":
        from packages.video_crawler.src.bilibili_crawler import BilibiliCrawler
        crawler = BilibiliCrawler()
    elif source in ("youtube", "dailymotion", "douyin", "ixigua", "acfun", "vimeo"):
        from packages.video_crawler.src.ytdlp_crawler import create_crawler
        try:
            crawler = create_crawler(source)
        except ValueError as e:
            parser.error(str(e))
    elif source in ("yarn", "playphrase", "quodb", "zhaotaici"):
        from packages.video_crawler.src.quote_crawler import create_quote_crawler
        try:
            crawler = create_quote_crawler(source)
        except ValueError as e:
            parser.error(str(e))
    else:
        parser.error(f"不支持的素材来源: {source}")

    paths = crawler.search_and_download(keyword, max_clips=clip_limit)
    if not paths:
        print("错误: 未下载到任何视频")
    return paths


if __name__ == "__main__":
    main()
