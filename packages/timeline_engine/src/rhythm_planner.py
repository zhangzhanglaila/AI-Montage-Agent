"""
Rhythm Planner Module
节奏规划器 - 生成和管理节奏曲线
"""

import numpy as np
from typing import List, Dict, Any
from .timeline_planner import RhythmPoint

class RhythmPlanner:
    """
    节奏规划器
    生成不同风格的节奏曲线
    """

    def generate(
        self,
        duration: float,
        style: str = "dynamic"
    ) -> List[RhythmPoint]:
        """
        生成节奏曲线

        Args:
            duration: 总时长(秒)
            style: 风格

        Returns:
            节奏点列表
        """
        # 获取节奏模式
        pattern = self._get_rhythm_pattern(style)

        # 生成时间点
        num_points = int(duration / 0.5)  # 每0.5秒一个点
        times = np.linspace(0, duration, num_points)

        # 生成节奏曲线
        points = []
        for t in times:
            tempo, energy = self._calculate_rhythm(t, duration, pattern)

            points.append(RhythmPoint(
                time=float(t),
                tempo=float(tempo),
                energy=float(energy)
            ))

        return points

    def _get_rhythm_pattern(self, style: str) -> Dict[str, Any]:
        """获取节奏模式"""

        patterns = {
            "dynamic": {
                "base_tempo": 120,
                "tempo_variation": 40,
                "energy_pattern": "accelerating",
                "acceleration_point": 0.7
            },
            "calm": {
                "base_tempo": 80,
                "tempo_variation": 20,
                "energy_pattern": "steady",
                "acceleration_point": 0.5
            },
            "intense": {
                "base_tempo": 140,
                "tempo_variation": 60,
                "energy_pattern": "accelerating",
                "acceleration_point": 0.6
            },
            "emotional": {
                "base_tempo": 90,
                "tempo_variation": 30,
                "energy_pattern": "wave",
                "acceleration_point": 0.75
            }
        }

        return patterns.get(style, patterns["dynamic"])

    def _calculate_rhythm(
        self,
        time: float,
        duration: float,
        pattern: Dict[str, Any]
    ) -> tuple:
        """计算指定时间点的节奏"""

        position = time / duration

        # 计算节奏速度
        base_tempo = pattern["base_tempo"]
        variation = pattern["tempo_variation"]

        # 根据模式计算
        if pattern["energy_pattern"] == "accelerating":
            # 加速模式：节奏越来越快
            tempo = base_tempo + variation * position
            energy = 0.3 + 0.7 * position
        elif pattern["energy_pattern"] == "steady":
            # 稳定模式：节奏基本不变
            tempo = base_tempo + variation * 0.1 * np.sin(position * 2 * np.pi)
            energy = 0.5 + 0.2 * np.sin(position * 4 * np.pi)
        elif pattern["energy_pattern"] == "wave":
            # 波浪模式：节奏起伏变化
            tempo = base_tempo + variation * np.sin(position * 3 * np.pi)
            energy = 0.4 + 0.4 * np.sin(position * 2 * np.pi)
        else:
            tempo = base_tempo
            energy = 0.5

        # 归一化到合理范围
        tempo = max(60, min(200, tempo))
        energy = max(0, min(1, energy))

        return tempo, energy

    def sync_with_beats(
        self,
        rhythm_points: List[RhythmPoint],
        beat_times: List[float]
    ) -> List[RhythmPoint]:
        """
        将节奏曲线与节拍同步

        Args:
            rhythm_points: 节奏点列表
            beat_times: 节拍时间点列表

        Returns:
            同步后的节奏点列表
        """
        if not beat_times:
            return rhythm_points

        synced_points = []

        for point in rhythm_points:
            # 找到最近的节拍
            closest_beat = min(beat_times, key=lambda x: abs(x - point.time))

            # 如果在节拍附近，调整能量
            distance = abs(point.time - closest_beat)
            if distance < 0.1:  # 100ms内
                # 在节拍上，提高能量
                energy_boost = 1.0 - (distance / 0.1)
                point.energy = min(1.0, point.energy + energy_boost * 0.3)

            synced_points.append(point)

        return synced_points

    def generate_cut_points(
        self,
        rhythm_points: List[RhythmPoint],
        intensity_threshold: float = 0.7
    ) -> List[float]:
        """
        根据节奏曲线生成剪辑点

        Args:
            rhythm_points: 节奏点列表
            intensity_threshold: 强度阈值

        Returns:
            剪辑点时间列表
        """
        cut_points = []

        for i in range(1, len(rhythm_points) - 1):
            prev = rhythm_points[i - 1]
            curr = rhythm_points[i]
            next_point = rhythm_points[i + 1]

            # 检测能量峰值
            if (curr.energy > prev.energy and
                curr.energy > next_point.energy and
                curr.energy > intensity_threshold):
                cut_points.append(curr.time)

            # 检测能量突变
            if abs(curr.energy - prev.energy) > 0.3:
                cut_points.append(curr.time)

        # 去重和排序
        cut_points = sorted(list(set(cut_points)))

        return cut_points

    def visualize_rhythm(
        self,
        points: List[RhythmPoint],
        output_path: str
    ):
        """可视化节奏曲线（需要matplotlib）"""

        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib not installed, skipping visualization")
            return

        times = [p.time for p in points]
        tempos = [p.tempo for p in points]
        energies = [p.energy for p in points]

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)

        # 绘制节奏速度
        ax1.plot(times, tempos, 'b-', linewidth=2)
        ax1.set_ylabel('Tempo (BPM)')
        ax1.set_title('Rhythm Curve')
        ax1.grid(True, alpha=0.3)

        # 绘制能量曲线
        ax2.fill_between(times, energies, alpha=0.3, color='orange')
        ax2.plot(times, energies, 'r-', linewidth=2)
        ax2.set_xlabel('Time (s)')
        ax2.set_ylabel('Energy')
        ax2.set_ylim(0, 1)
        ax2.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
        plt.close()
