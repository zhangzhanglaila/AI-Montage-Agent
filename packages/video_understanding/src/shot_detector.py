"""
Shot Detection Module
镜头检测模块 - 使用PySceneDetect进行视频镜头分割
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json

@dataclass
class Shot:
    """镜头数据结构"""
    shot_id: int
    start_time: float
    end_time: float
    duration: float
    file_path: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "start": self.start_time,
            "end": self.end_time,
            "duration": self.duration,
            "file_path": self.file_path
        }

class ShotDetector:
    """
    镜头检测器
    使用PySceneDetect进行视频镜头分割
    支持: dissolve, fade, hard cut
    """

    def __init__(self, output_dir: str = "./shots"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def detect_shots(
        self,
        video_path: str,
        method: str = "content",
        threshold: float = 27.0,
        min_shot_len: int = 15
    ) -> List[Shot]:
        """
        检测视频镜头

        Args:
            video_path: 视频文件路径
            method: 检测方法 (content, adaptive, histogram, threshold)
            threshold: 检测阈值
            min_shot_len: 最小镜头长度(帧数)

        Returns:
            镜头列表
        """
        video_path = Path(video_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")

        # 使用PySceneDetect命令行工具
        shots = self._detect_with_scenedetect(
            str(video_path),
            method=method,
            threshold=threshold,
            min_shot_len=min_shot_len
        )

        # 分割视频为独立镜头文件
        shots = self._split_video(str(video_path), shots)

        return shots

    def _detect_with_scenedetect(
        self,
        video_path: str,
        method: str = "content",
        threshold: float = 27.0,
        min_shot_len: int = 15
    ) -> List[Shot]:
        """使用PySceneDetect进行镜头检测"""

        # 构建scenedetect命令
        cmd = [
            "scenedetect",
            "-i", video_path,
            "detect", method,
            "--threshold", str(threshold),
            "--min-scene-len", str(min_shot_len),
            "list-scenes",
            "--output", str(self.output_dir / "scenes.csv")
        ]

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"SceneDetect error: {e.stderr}")
            # 降级到FFmpeg场景检测
            return self._detect_with_ffmpeg(video_path, threshold)

        # 解析输出
        return self._parse_scenes_csv(self.output_dir / "scenes.csv")

    def _detect_with_ffmpeg(self, video_path: str, threshold: float = 0.3) -> List[Shot]:
        """使用FFmpeg进行镜头检测(降级方案)"""

        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", f"select='gt(scene,{threshold})',showinfo",
            "-f", "null", "-"
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)

        # 解析FFmpeg输出中的场景变化时间点
        shots = []
        times = []

        for line in result.stderr.split('\n'):
            if 'showinfo' in line and 'pts_time' in line:
                # 提取时间点
                import re
                match = re.search(r'pts_time:(\d+\.\d+)', line)
                if match:
                    times.append(float(match.group(1)))

        # 创建镜头列表
        if not times:
            # 如果没有检测到场景变化，整个视频作为一个镜头
            duration = self._get_video_duration(video_path)
            shots.append(Shot(
                shot_id=0,
                start_time=0.0,
                end_time=duration,
                duration=duration
            ))
        else:
            # 创建镜头
            for i, (start, end) in enumerate(zip([0.0] + times, times + [None])):
                if end is None:
                    end = self._get_video_duration(video_path)
                shots.append(Shot(
                    shot_id=i,
                    start_time=start,
                    end_time=end,
                    duration=end - start
                ))

        return shots

    def _parse_scenes_csv(self, csv_path: Path) -> List[Shot]:
        """解析SceneDetect输出的CSV文件"""

        shots = []

        if not csv_path.exists():
            return shots

        with open(csv_path, 'r') as f:
            lines = f.readlines()

        for i, line in enumerate(lines[1:], start=0):  # 跳过标题行
            parts = line.strip().split(',')
            if len(parts) >= 4:
                start_time = self._time_to_seconds(parts[1])
                end_time = self._time_to_seconds(parts[2])
                shots.append(Shot(
                    shot_id=i,
                    start_time=start_time,
                    end_time=end_time,
                    duration=end_time - start_time
                ))

        return shots

    def _split_video(self, video_path: str, shots: List[Shot]) -> List[Shot]:
        """将视频分割为独立的镜头文件"""

        for shot in shots:
            output_path = self.output_dir / f"shot_{shot.shot_id:04d}.mp4"

            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-ss", str(shot.start_time),
                "-to", str(shot.end_time),
                "-c", "copy",
                str(output_path)
            ]

            subprocess.run(cmd, capture_output=True, check=True)
            shot.file_path = str(output_path)

        return shots

    def _get_video_duration(self, video_path: str) -> float:
        """获取视频时长"""

        cmd = [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            video_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True)
        return float(result.stdout.strip())

    def _time_to_seconds(self, time_str: str) -> float:
        """将时间字符串转换为秒数"""

        parts = time_str.split(':')
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return float(hours) * 3600 + float(minutes) * 60 + float(seconds)
        elif len(parts) == 2:
            minutes, seconds = parts
            return float(minutes) * 60 + float(seconds)
        else:
            return float(time_str)
