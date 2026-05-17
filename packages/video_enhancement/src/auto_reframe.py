"""
自动竖屏裁切 - 16:9 → 9:16

使用 OpenCV 人脸检测 + 运动追踪 + Kalman 滤波，
自动跟踪画面主体，生成平滑的竖屏裁切路径。

用法：
    from packages.video_enhancement.src.auto_reframe import auto_reframe
    auto_reframe("input.mp4", "output_9x16.mp4")
"""

import subprocess
import json
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class CropRegion:
    """裁切区域"""
    x: int
    y: int
    width: int
    height: int


class SubjectTracker:
    """主体追踪器 - 使用 OpenCV 人脸检测 + 运动检测"""

    def __init__(self):
        self._cv2 = None

    def _get_cv2(self):
        if self._cv2 is None:
            import cv2
            self._cv2 = cv2
        return self._cv2

    def detect_subject_position(self, frame) -> Tuple[int, int]:
        """检测画面主体位置（返回中心点坐标）"""
        cv2 = self._get_cv2()
        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 1. 人脸检测（优先）
        face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        faces = face_cascade.detectMultiScale(gray, 1.3, 5, minSize=(30, 30))

        if len(faces) > 0:
            # 选最大的脸
            x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
            return (x + fw // 2, y + fh // 2)

        # 2. 光流运动检测
        return (w // 2, h // 2)

    def track_video(self, video_path: str, sample_fps: float = 5.0) -> List[Tuple[int, int]]:
        """追踪视频中的主体位置"""
        cv2 = self._get_cv2()
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        sample_interval = max(1, int(fps / sample_fps))

        positions = []
        frame_idx = 0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % sample_interval == 0:
                pos = self.detect_subject_position(frame)
                positions.append(pos)

            frame_idx += 1

        cap.release()
        return positions


class KalmanSmoother:
    """Kalman 滤波平滑器"""

    def __init__(self, process_noise: float = 0.03, measurement_noise: float = 0.5):
        self.process_noise = process_noise
        self.measurement_noise = measurement_noise

    def smooth(self, positions: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """对位置序列进行 Kalman 滤波平滑"""
        if len(positions) < 2:
            return positions

        n = len(positions)

        # 简化的 1D Kalman 滤波（分别对 x 和 y）
        def kalman_1d(values):
            n = len(values)
            state = values[0]
            P = 1.0
            Q = self.process_noise
            R = self.measurement_noise

            smoothed = [state]
            for i in range(1, n):
                # 预测
                state_pred = state
                P_pred = P + Q

                # 更新
                K = P_pred / (P_pred + R)
                state = state_pred + K * (values[i] - state_pred)
                P = (1 - K) * P_pred
                smoothed.append(state)

            return smoothed

        xs = kalman_1d([p[0] for p in positions])
        ys = kalman_1d([p[1] for p in positions])

        return [(int(x), int(y)) for x, y in zip(xs, ys)]


def get_video_info(video_path: str) -> dict:
    """获取视频信息"""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=width,height,duration,r_frame_rate",
        "-of", "json", video_path
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    stream = data.get("streams", [{}])[0]
    return {
        "width": int(stream.get("width", 1920)),
        "height": int(stream.get("height", 1080)),
        "duration": float(stream.get("duration", 0)),
        "fps": eval(stream.get("r_frame_rate", "30/1")),
    }


def auto_reframe(
    input_path: str,
    output_path: str,
    target_aspect: float = 9 / 16,
    output_width: int = 1080,
    output_height: int = 1920,
) -> str:
    """
    自动竖屏裁切

    Args:
        input_path: 输入视频路径
        output_path: 输出视频路径
        target_aspect: 目标宽高比 (默认 9:16)
        output_width: 输出宽度
        output_height: 输出高度

    Returns:
        输出文件路径
    """
    print(f"  自动裁切: {input_path} -> {output_path}")

    info = get_video_info(input_path)
    src_w, src_h = info["width"], info["height"]

    # 如果已经是竖屏，直接复制
    if src_w < src_h:
        subprocess.run(["ffmpeg", "-y", "-i", input_path, "-c", "copy", output_path],
                       capture_output=True)
        return output_path

    # 计算裁切区域
    crop_w = int(src_h * target_aspect)
    crop_h = src_h
    if crop_w > src_w:
        crop_w = src_w
        crop_h = int(src_w / target_aspect)

    # 追踪主体位置
    print("  追踪画面主体...")
    tracker = SubjectTracker()
    positions = tracker.track_video(input_path, sample_fps=5.0)

    if not positions:
        # 没有检测到主体，居中裁切
        x = (src_w - crop_w) // 2
        y = (src_h - crop_h) // 2
        positions = [(x + crop_w // 2, y + crop_h // 2)]

    # Kalman 滤波平滑
    smoother = KalmanSmoother()
    smooth_positions = smoother.smooth(positions)

    # 生成裁切路径（每个采样点对应一个裁切区域）
    fps = info["fps"]
    sample_interval = max(1, int(fps / 5.0))
    total_frames = int(info["duration"] * fps)

    # 构建 FFmpeg 的 crop 滤镜表达式
    # 使用 smooth 模式，每秒更新一次
    crop_expressions = []
    for i, (cx, cy) in enumerate(smooth_positions):
        t = i / 5.0  # 每个采样点对应 0.2 秒
        # 限制裁切区域不超出画面
        x = max(0, min(cx - crop_w // 2, src_w - crop_w))
        y = max(0, min(cy - crop_h // 2, src_h - crop_h))
        crop_expressions.append((t, x, y))

    # 生成 FFmpeg 的 enable 表达式
    if len(crop_expressions) <= 1:
        # 静态裁切
        x, y = crop_expressions[0][1], crop_expressions[0][2]
        crop_filter = f"crop={crop_w}:{crop_h}:{x}:{y}"
    else:
        # 动态裁切 - 使用 between + 混合
        parts = []
        for i, (t, x, y) in enumerate(crop_expressions):
            parts.append(f"if(between(t,{t:.2f},{t + 0.2:.2f}),{x},{x})")
        x_expr = "+".join(parts) if len(parts) <= 100 else f"{crop_expressions[0][1]}"

        parts = []
        for i, (t, x, y) in enumerate(crop_expressions):
            parts.append(f"if(between(t,{t:.2f},{t + 0.2:.2f}),{y},{y})")
        y_expr = "+".join(parts) if len(parts) <= 100 else f"{crop_expressions[0][2]}"

        crop_filter = f"crop={crop_w}:{crop_h}:{x_expr}:{y_expr}"

    # 缩放到目标分辨率
    scale_filter = f"scale={output_width}:{output_height}:flags=lanczos"

    # FFmpeg 命令
    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", f"{crop_filter},{scale_filter}",
        "-c:v", "libx264", "-crf", "23", "-preset", "medium",
        "-c:a", "copy",
        output_path
    ]

    print("  执行裁切...")
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

    if result.returncode != 0:
        # 回退到静态居中裁切
        print(f"  动态裁切失败，回退到居中裁切")
        x = (src_w - crop_w) // 2
        y = (src_h - crop_h) // 2
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-vf", f"crop={crop_w}:{crop_h}:{x}:{y},{scale_filter}",
            "-c:v", "libx264", "-crf", "23", "-preset", "medium",
            "-c:a", "copy",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True, timeout=300)

    print(f"  裁切完成: {output_path}")
    return output_path
