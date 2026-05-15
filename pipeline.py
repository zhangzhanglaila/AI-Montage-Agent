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

    def detect(self, video_path: str, threshold: float = 0.3) -> List[Shot]:
        """检测镜头并切割"""
        print(f"  检测镜头: {video_path}")

        # 获取视频时长
        duration = self._get_duration(video_path)

        # 使用 FFmpeg 检测场景变化
        scenes = self._detect_scenes(video_path, threshold)

        # 如果没检测到场景变化，整个视频作为一个镜头
        if not scenes:
            scenes = [(0.0, duration)]

        # 切割视频
        shots = []
        for i, (start, end) in enumerate(scenes):
            shot_path = self.cache_dir / f"shot_{i:04d}.mp4"

            # 切割视频（stream copy，不重新编码，速度极快）
            cmd = [
                "ffmpeg", "-y",
                "-ss", str(start),
                "-i", video_path,
                "-to", str(end - start),
                "-c", "copy",
                "-avoid_negative_ts", "make_zero",
                str(shot_path)
            ]
            subprocess.run(cmd, capture_output=True, check=True)

            shots.append(Shot(
                shot_id=i,
                start_time=start,
                end_time=end,
                duration=end - start,
                file_path=str(shot_path)
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

            # 检测节拍
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

            # 如果没有检测到节拍，生成默认节拍
            if len(beat_times) == 0:
                print("  警告: 未检测到节拍，使用默认节拍")
                beat_interval = 0.5  # 120 BPM
                beat_times = np.arange(0, duration, beat_interval)

            # 计算能量
            rms = librosa.feature.rms(y=y)[0]
            rms_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
            rms_normalized = (rms - rms.min()) / (rms.max() - rms.min() + 1e-8)

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

            # 创建节拍对象
            beats = [
                Beat(time=float(t), strength=0.8, beat_type="normal")
                for t in beat_times
            ]

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
    """高光评分"""

    def score(self, shot: Shot, motion: MotionData) -> float:
        """计算高光分数"""
        # 运动幅度权重
        motion_weight = 0.6
        # 镜头时长权重（太短或太长都不好）
        duration_weight = 0.4

        # 运动分数
        motion_score = min(motion.magnitude / 5.0, 1.0)

        # 时长分数（1-3秒最佳）
        if 1.0 <= shot.duration <= 3.0:
            duration_score = 1.0
        elif shot.duration < 1.0:
            duration_score = shot.duration
        else:
            duration_score = max(0.5, 1.0 - (shot.duration - 3.0) * 0.1)

        return motion_weight * motion_score + duration_weight * duration_score


class BeatSyncEngine:
    """卡点同步引擎"""

    def sync(
        self,
        shots: List[Shot],
        beats: List[Beat],
        style: str = "dynamic"
    ) -> List[TimelineEntry]:
        """将镜头与节拍同步"""
        if not shots or not beats:
            return []

        # 按高光分数排序
        sorted_shots = sorted(shots, key=lambda s: s.highlight_score, reverse=True)

        # 获取风格参数
        params = self._get_style_params(style)

        timeline = []
        beat_idx = 0

        for i, shot in enumerate(sorted_shots):
            if beat_idx >= len(beats):
                break

            # 获取当前节拍
            beat = beats[beat_idx]

            # 根据高光分数决定时长
            if shot.highlight_score > 0.7:
                # 高光镜头，短而快
                duration = params["fast"]
            elif shot.highlight_score > 0.4:
                # 中等镜头
                duration = params["medium"]
            else:
                # 普通镜头
                duration = params["slow"]

            # 量化到节拍
            beat_interval = beats[1].time - beats[0].time if len(beats) > 1 else 0.5
            duration = round(duration / beat_interval) * beat_interval

            # 创建时间线条目
            entry = TimelineEntry(
                shot_id=shot.shot_id,
                shot_path=shot.file_path or "",
                start_time=beat.time,
                end_time=beat.time + duration,
                duration=duration,
                beat_time=beat.time,
                speed_factor=1.0,
                transition_type="cut",
                transition_duration=0.0
            )

            timeline.append(entry)

            # 跳过相应的节拍
            beats_to_skip = max(1, int(duration / beat_interval))
            beat_idx += beats_to_skip

        # 按时间排序
        timeline.sort(key=lambda x: x.start_time)

        return timeline

    def _get_style_params(self, style: str) -> Dict[str, float]:
        """获取风格参数"""
        params = {
            "dynamic": {"fast": 0.3, "medium": 0.5, "slow": 1.0},
            "calm": {"fast": 0.5, "medium": 1.0, "slow": 2.0},
            "intense": {"fast": 0.2, "medium": 0.3, "slow": 0.5},
        }
        return params.get(style, params["dynamic"])


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
        """渲染最终视频"""
        print(f"  渲染视频...")

        # 创建 concat 文件
        concat_file = self.output_dir / "concat.txt"
        temp_files = []

        with open(concat_file, 'w') as f:
            for entry in timeline:
                if not entry.shot_path or not Path(entry.shot_path).exists():
                    continue

                # 使用绝对路径和正斜杠
                shot_path = Path(entry.shot_path).resolve().as_posix()

                # 调整速度
                if entry.speed_factor != 1.0:
                    temp_path = self.output_dir / f"speed_{entry.shot_id}.mp4"
                    self._adjust_speed(entry.shot_path, str(temp_path), entry.speed_factor)
                    temp_files.append(temp_path)
                    f.write(f"file '{temp_path.resolve().as_posix()}'\n")
                else:
                    f.write(f"file '{shot_path}'\n")

        # 拼接视频
        concat_video = self.output_dir / "concat.mp4"
        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c", "copy",
            str(concat_video)
        ]
        subprocess.run(cmd, capture_output=True, check=True)

        # 添加 BGM
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
            f.unlink(missing_ok=True)
        concat_file.unlink(missing_ok=True)
        concat_video.unlink(missing_ok=True)

        print(f"  输出: {output_path}")
        return output_path

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
    ) -> str:
        """
        运行完整混剪流程

        Args:
            video_paths: 视频文件路径列表
            bgm_path: BGM 文件路径
            style: 风格 (dynamic, calm, intense)
            output_name: 输出文件名
            threshold: 镜头检测灵敏度 (0.01~1.0，越小切得越细)

        Returns:
            输出文件路径
        """
        print("=" * 50)
        print("AI Montage Agent - 开始混剪")
        print("=" * 50)

        # Step 1: 检测镜头
        print(f"\n[1/5] 检测镜头 (阈值: {threshold})...")
        all_shots = []
        for video_path in video_paths:
            shots = self.shot_detector.detect(video_path, threshold=threshold)
            all_shots.extend(shots)

        if not all_shots:
            raise ValueError("没有检测到任何镜头")

        # Step 2: 分析运动
        print("\n[2/5] 分析运动...")
        for shot in all_shots:
            motion = self.motion_analyzer.analyze(shot.file_path)
            shot.motion_score = motion.magnitude

        # Step 3: 评分高光
        print("\n[3/5] 评分高光...")
        for shot in all_shots:
            motion = MotionData(magnitude=shot.motion_score)
            shot.highlight_score = self.scorer.score(shot, motion)

        # Step 4: 分析 BGM
        print("\n[4/5] 分析 BGM...")
        beat_analysis = self.beat_analyzer.analyze(bgm_path)

        # Step 5: 卡点同步 + 渲染
        print("\n[5/5] 卡点同步 + 渲染...")
        timeline = self.sync_engine.sync(all_shots, beat_analysis.beats, style)

        if not timeline:
            raise ValueError("时间线为空")

        # 存储时间线数据（供导出使用）
        self._last_timeline = timeline
        self._last_bgm_path = bgm_path
        self._last_total_duration = sum(e.duration for e in timeline)

        # 渲染输出
        output_path = f"{self.output_dir}/{output_name}"
        result = self.renderer.render(timeline, bgm_path, output_path)

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
    parser.add_argument("--source", type=str, default="bilibili",
                        choices=["bilibili",
                                 "youtube", "dailymotion", "douyin", "ixigua", "acfun", "vimeo",
                                 "yarn", "playphrase", "quodb", "zhaotaici"],
                        help="素材来源（默认 bilibili）")
    parser.add_argument("--clip-limit", type=int, default=20, help="最大下载片段数，默认 20（仅 --query 模式）")
    parser.add_argument("--bgm", required=True, help="BGM 文件路径")
    parser.add_argument("--style", default="dynamic", choices=["dynamic", "calm", "intense"])
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
                        choices=["edl", "csv", "json", "xml"],
                        help="导出时间轴格式")
    parser.add_argument("--webui", action="store_true", help="启动 WebUI 界面")

    args = parser.parse_args()

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

    if not Path(args.bgm).exists():
        print(f"错误: BGM 文件不存在: {args.bgm}")
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
    result_path = pipeline.run(video_paths, args.bgm, args.style, args.output, threshold=args.threshold)

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
