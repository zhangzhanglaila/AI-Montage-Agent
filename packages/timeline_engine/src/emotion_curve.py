"""
Emotion Curve Module
情绪曲线模块 - 生成和管理情绪变化曲线
"""

import numpy as np
from typing import List, Dict, Any
from .timeline_planner import EmotionPoint

class EmotionCurve:
    """
    情绪曲线生成器
    根据风格生成不同的情绪变化曲线
    """

    # 情绪类型定义
    EMOTIONS = [
        "calm",        # 平静
        "building",    # 积蓄
        "intense",     # 激烈
        "climax",      # 高潮
        "emotional",   # 情感
        "reflective",  # 沉思
        "hopeful",     # 希望
        "sad",         # 悲伤
        "gentle",      # 温柔
        "peaceful",    # 宁静
        "explosive",   # 爆发
    ]

    def generate(
        self,
        duration: float,
        style: str = "dynamic"
    ) -> List[EmotionPoint]:
        """
        生成情绪曲线

        Args:
            duration: 总时长(秒)
            style: 风格

        Returns:
            情绪点列表
        """
        # 获取风格参数
        arc = self._get_emotion_arc(style)

        # 生成时间点
        num_points = int(duration / 0.5)  # 每0.5秒一个点
        times = np.linspace(0, duration, num_points)

        # 生成情绪曲线
        points = []
        for t in times:
            # 计算当前阶段
            position = t / duration
            emotion, intensity = self._interpolate_emotion(position, arc)

            points.append(EmotionPoint(
                time=float(t),
                emotion=emotion,
                intensity=float(intensity)
            ))

        return points

    def _get_emotion_arc(self, style: str) -> List[Dict[str, Any]]:
        """获取情绪弧线模板"""

        arcs = {
            "dynamic": [
                {"emotion": "calm", "start": 0.0, "end": 0.15, "intensity": 0.3},
                {"emotion": "building", "start": 0.15, "end": 0.35, "intensity": 0.5},
                {"emotion": "intense", "start": 0.35, "end": 0.55, "intensity": 0.7},
                {"emotion": "building", "start": 0.55, "end": 0.70, "intensity": 0.6},
                {"emotion": "climax", "start": 0.70, "end": 0.85, "intensity": 1.0},
                {"emotion": "calm", "start": 0.85, "end": 1.0, "intensity": 0.4}
            ],
            "calm": [
                {"emotion": "calm", "start": 0.0, "end": 0.2, "intensity": 0.3},
                {"emotion": "gentle", "start": 0.2, "end": 0.4, "intensity": 0.4},
                {"emotion": "peaceful", "start": 0.4, "end": 0.7, "intensity": 0.5},
                {"emotion": "reflective", "start": 0.7, "end": 0.9, "intensity": 0.4},
                {"emotion": "calm", "start": 0.9, "end": 1.0, "intensity": 0.3}
            ],
            "intense": [
                {"emotion": "intense", "start": 0.0, "end": 0.2, "intensity": 0.7},
                {"emotion": "building", "start": 0.2, "end": 0.4, "intensity": 0.8},
                {"emotion": "explosive", "start": 0.4, "end": 0.6, "intensity": 0.9},
                {"emotion": "intense", "start": 0.6, "end": 0.75, "intensity": 0.8},
                {"emotion": "climax", "start": 0.75, "end": 0.9, "intensity": 1.0},
                {"emotion": "intense", "start": 0.9, "end": 1.0, "intensity": 0.7}
            ],
            "emotional": [
                {"emotion": "sad", "start": 0.0, "end": 0.2, "intensity": 0.6},
                {"emotion": "reflective", "start": 0.2, "end": 0.4, "intensity": 0.5},
                {"emotion": "building", "start": 0.4, "end": 0.6, "intensity": 0.7},
                {"emotion": "emotional", "start": 0.6, "end": 0.8, "intensity": 0.9},
                {"emotion": "hopeful", "start": 0.8, "end": 0.95, "intensity": 0.8},
                {"emotion": "calm", "start": 0.95, "end": 1.0, "intensity": 0.4}
            ]
        }

        return arcs.get(style, arcs["dynamic"])

    def _interpolate_emotion(
        self,
        position: float,
        arc: List[Dict[str, Any]]
    ) -> tuple:
        """在情绪弧线中插值"""

        # 找到当前阶段
        for segment in arc:
            if segment["start"] <= position <= segment["end"]:
                # 在这个阶段内插值
                local_position = (
                    (position - segment["start"]) /
                    (segment["end"] - segment["start"])
                )

                # 使用平滑函数
                intensity = self._smooth_interpolation(
                    local_position, segment["intensity"]
                )

                return segment["emotion"], intensity

        # 默认返回平静
        return "calm", 0.3

    def _smooth_interpolation(
        self,
        position: float,
        target_intensity: float
    ) -> float:
        """平滑插值"""

        # 使用正弦函数进行平滑
        smooth = np.sin(position * np.pi)

        # 调整到目标强度
        return target_intensity * smooth

    def blend_emotions(
        self,
        emotion1: str,
        emotion2: str,
        ratio: float
    ) -> str:
        """混合两种情绪"""

        if ratio < 0.3:
            return emotion1
        elif ratio > 0.7:
            return emotion2
        else:
            # 创建混合情绪
            return f"{emotion1}_{emotion2}"

    def get_emotion_color(self, emotion: str) -> str:
        """获取情绪对应的颜色（用于可视化）"""

        colors = {
            "calm": "#4CAF50",        # 绿色
            "building": "#FF9800",     # 橙色
            "intense": "#F44336",      # 红色
            "climax": "#9C27B0",       # 紫色
            "emotional": "#2196F3",    # 蓝色
            "reflective": "#607D8B",   # 灰蓝色
            "hopeful": "#FFEB3B",      # 黄色
            "sad": "#795548",          # 棕色
            "gentle": "#E91E63",       # 粉色
            "peaceful": "#00BCD4",     # 青色
            "explosive": "#FF5722",    # 深橙色
        }

        return colors.get(emotion, "#9E9E9E")  # 默认灰色

    def visualize_curve(
        self,
        points: List[EmotionPoint],
        output_path: str
    ):
        """可视化情绪曲线（需要matplotlib）"""

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed, skipping visualization")
            return

        times = [p.time for p in points]
        intensities = [p.intensity for p in points]
        emotions = [p.emotion for p in points]

        # 创建颜色映射
        colors = [self.get_emotion_color(e) for e in emotions]

        # 绘制曲线
        fig, ax = plt.subplots(figsize=(12, 4))

        # 绘制强度曲线
        ax.plot(times, intensities, 'k-', alpha=0.3, linewidth=1)

        # 绘制彩色点
        for i in range(len(times) - 1):
            ax.plot(
                times[i:i+2],
                intensities[i:i+2],
                color=colors[i],
                linewidth=2
            )

        # 设置图表
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Intensity')
        ax.set_title('Emotion Curve')
        ax.set_ylim(0, 1)

        # 添加图例
        unique_emotions = list(set(emotions))
        for emotion in unique_emotions:
            ax.plot([], [], color=self.get_emotion_color(emotion), label=emotion)
        ax.legend(loc='upper right', bbox_to_anchor=(1.15, 1))

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
