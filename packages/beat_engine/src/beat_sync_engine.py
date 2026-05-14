"""
Beat Sync Engine
卡点引擎 - 将镜头与节拍同步
这是混剪的灵魂
"""

import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class TimelineEntry:
    """时间线条目"""
    shot_id: int
    start_time: float
    end_time: float
    duration: float
    beat_time: float
    speed_factor: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "beat_time": self.beat_time,
            "speed_factor": self.speed_factor
        }

class BeatSyncEngine:
    """
    卡点引擎
    将镜头与节拍同步
    核心功能:
    1. 镜头长度适配 (高潮0.3s, 平静3s)
    2. 动作对齐 (鼓点瞬间 = 爆炸瞬间)
    3. 速度拉伸 (slow motion, speed ramp)
    """

    def __init__(
        self,
        min_shot_duration: float = 0.3,
        max_shot_duration: float = 5.0,
        default_shot_duration: float = 1.0
    ):
        self.min_shot_duration = min_shot_duration
        self.max_shot_duration = max_shot_duration
        self.default_shot_duration = default_shot_duration

    def sync(
        self,
        shots: List[Dict[str, Any]],
        beats: List[Dict[str, Any]],
        climax_segments: Optional[List[Dict[str, Any]]] = None,
        style: str = "dynamic"
    ) -> List[TimelineEntry]:
        """
        将镜头与节拍同步

        Args:
            shots: 镜头列表（包含高光分数）
            beats: 节拍列表
            climax_segments: 高潮片段
            style: 同步风格 (dynamic, calm, intense)

        Returns:
            时间线条目列表
        """
        if not shots or not beats:
            return []

        # 提取节拍时间点
        beat_times = [b["time"] for b in beats]
        beat_strengths = [b.get("strength", 1.0) for b in beats]

        # 根据风格调整参数
        params = self._get_style_params(style)

        # 为每个镜头分配最佳节拍
        timeline = self._assign_shots_to_beats(
            shots, beat_times, beat_strengths,
            climax_segments, params
        )

        # 调整镜头时长
        timeline = self._adjust_durations(timeline, beat_times, params)

        # 应用速度拉伸
        timeline = self._apply_speed_ramps(timeline, beats, params)

        return timeline

    def _get_style_params(self, style: str) -> Dict[str, Any]:
        """获取风格参数"""

        params = {
            "dynamic": {
                "climax_duration": 0.3,
                "normal_duration": 1.0,
                "calm_duration": 2.0,
                "speed_range": (0.5, 2.0),
                "beat_alignment": "strong"
            },
            "calm": {
                "climax_duration": 1.0,
                "normal_duration": 2.5,
                "calm_duration": 4.0,
                "speed_range": (0.7, 1.3),
                "beat_alignment": "all"
            },
            "intense": {
                "climax_duration": 0.2,
                "normal_duration": 0.5,
                "calm_duration": 1.5,
                "speed_range": (0.3, 3.0),
                "beat_alignment": "strong"
            }
        }

        return params.get(style, params["dynamic"])

    def _assign_shots_to_beats(
        self,
        shots: List[Dict[str, Any]],
        beat_times: List[float],
        beat_strengths: List[float],
        climax_segments: Optional[List[Dict[str, Any]]],
        params: Dict[str, Any]
    ) -> List[TimelineEntry]:
        """将镜头分配到节拍"""

        timeline = []
        shot_index = 0
        beat_index = 0

        # 按高光分数排序镜头（高分优先）
        sorted_shots = sorted(
            shots,
            key=lambda x: x.get("highlight_score", 0),
            reverse=True
        )

        while shot_index < len(sorted_shots) and beat_index < len(beat_times):
            shot = sorted_shots[shot_index]
            beat_time = beat_times[beat_index]

            # 判断是否在高潮部分
            is_climax = self._is_in_climax(beat_time, climax_segments)

            # 确定时长
            if is_climax:
                duration = params["climax_duration"]
            elif shot.get("highlight_score", 0) > 0.7:
                duration = params["normal_duration"]
            else:
                duration = params["calm_duration"]

            # 限制时长范围
            duration = max(self.min_shot_duration, min(duration, self.max_shot_duration))

            # 创建时间线条目
            entry = TimelineEntry(
                shot_id=shot.get("shot_id", shot_index),
                start_time=beat_time,
                end_time=beat_time + duration,
                duration=duration,
                beat_time=beat_time,
                speed_factor=1.0
            )

            timeline.append(entry)

            # 移动到下一个镜头和节拍
            shot_index += 1

            # 根据时长跳过相应的节拍
            beats_to_skip = max(1, int(duration / (beat_times[1] - beat_times[0])))
            beat_index += beats_to_skip

        return timeline

    def _is_in_climax(
        self,
        time: float,
        climax_segments: Optional[List[Dict[str, Any]]]
    ) -> bool:
        """判断时间点是否在高潮部分"""

        if not climax_segments:
            return False

        for segment in climax_segments:
            if segment["start"] <= time <= segment["end"]:
                return True

        return False

    def _adjust_durations(
        self,
        timeline: List[TimelineEntry],
        beat_times: List[float],
        params: Dict[str, Any]
    ) -> List[TimelineEntry]:
        """调整镜头时长以对齐节拍"""

        for i, entry in enumerate(timeline):
            # 找到最近的节拍点
            closest_beat = min(
                beat_times,
                key=lambda x: abs(x - entry.end_time)
            )

            # 调整结束时间到最近的节拍
            entry.end_time = closest_beat
            entry.duration = entry.end_time - entry.start_time

            # 确保时长在合理范围内
            entry.duration = max(
                self.min_shot_duration,
                min(entry.duration, self.max_shot_duration)
            )
            entry.end_time = entry.start_time + entry.duration

        return timeline

    def _apply_speed_ramps(
        self,
        timeline: List[TimelineEntry],
        beats: List[Dict[str, Any]],
        params: Dict[str, Any]
    ) -> List[TimelineEntry]:
        """应用速度拉伸"""

        for entry in timeline:
            # 获取该时间段的节拍强度
            beat_strength = self._get_beat_strength(
                entry.beat_time, beats
            )

            # 根据节拍强度调整速度
            # 强拍 -> 慢动作
            # 弱拍 -> 快速
            if beat_strength > 0.8:
                # 强拍，使用慢动作
                entry.speed_factor = 0.5
            elif beat_strength < 0.3:
                # 弱拍，使用快速
                entry.speed_factor = 1.5
            else:
                # 正常速度
                entry.speed_factor = 1.0

            # 限制速度范围
            min_speed, max_speed = params["speed_range"]
            entry.speed_factor = max(
                min_speed,
                min(entry.speed_factor, max_speed)
            )

        return timeline

    def _get_beat_strength(
        self,
        time: float,
        beats: List[Dict[str, Any]]
    ) -> float:
        """获取指定时间点的节拍强度"""

        # 找到最近的节拍
        closest_beat = min(
            beats,
            key=lambda x: abs(x["time"] - time)
        )

        return closest_beat.get("strength", 1.0)

    def optimize_for_energy(
        self,
        timeline: List[TimelineEntry],
        energy_curve: List[Dict[str, Any]]
    ) -> List[TimelineEntry]:
        """
        根据能量曲线优化时间线
        高能量部分：短镜头、快节奏
        低能量部分：长镜头、慢节奏
        """

        for entry in timeline:
            # 获取该时间段的能量
            energy = self._get_energy_at_time(
                entry.start_time, energy_curve
            )

            # 根据能量调整时长
            if energy > 0.8:
                # 高能量，缩短镜头
                entry.duration *= 0.7
            elif energy < 0.3:
                # 低能量，延长镜头
                entry.duration *= 1.5

            # 限制时长范围
            entry.duration = max(
                self.min_shot_duration,
                min(entry.duration, self.max_shot_duration)
            )

            # 更新结束时间
            entry.end_time = entry.start_time + entry.duration

        return timeline

    def _get_energy_at_time(
        self,
        time: float,
        energy_curve: List[Dict[str, Any]]
    ) -> float:
        """获取指定时间点的能量"""

        if not energy_curve:
            return 0.5

        # 找到最近的能量点
        closest = min(
            energy_curve,
            key=lambda x: abs(x["time"] - time)
        )

        return closest.get("energy", 0.5)

    def export_timeline(
        self,
        timeline: List[TimelineEntry],
        output_path: str
    ):
        """导出时间线到JSON文件"""

        import json

        timeline_data = {
            "entries": [entry.to_dict() for entry in timeline],
            "total_duration": sum(e.duration for e in timeline),
            "shot_count": len(timeline)
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(timeline_data, f, indent=2, ensure_ascii=False)
