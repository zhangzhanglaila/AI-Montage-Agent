"""
Timeline Planner
时间轴规划器 - 导演的大脑
负责:
1. 情绪曲线
2. 节奏曲线
3. 镜头多样性
"""

import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class EmotionPoint:
    """情绪点"""
    time: float
    emotion: str
    intensity: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "emotion": self.emotion,
            "intensity": self.intensity
        }

@dataclass
class RhythmPoint:
    """节奏点"""
    time: float
    tempo: float
    energy: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "tempo": self.tempo,
            "energy": self.energy
        }

class TimelinePlanner:
    """
    时间轴规划器
    导演的大脑，负责:
    1. 情绪曲线 (emotion graph)
    2. 节奏曲线 (越来越快)
    3. 镜头多样性 (避免连续10个爆炸)
    """

    def __init__(self):
        self.emotion_curve = EmotionCurve()
        self.rhythm_planner = RhythmPlanner()

    def plan(
        self,
        shots: List[Dict[str, Any]],
        style: str = "dynamic",
        target_duration: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        规划时间轴

        Args:
            shots: 镜头列表
            style: 风格 (dynamic, calm, intense, emotional)
            target_duration: 目标时长(秒)

        Returns:
            规划结果
        """
        # 获取风格参数
        params = self._get_style_params(style)

        # 生成情绪曲线
        emotion_points = self.emotion_curve.generate(
            duration=target_duration or sum(s.get("duration", 1.0) for s in shots),
            style=style
        )

        # 生成节奏曲线
        rhythm_points = self.rhythm_planner.generate(
            duration=target_duration or sum(s.get("duration", 1.0) for s in shots),
            style=style
        )

        # 根据情绪和节奏安排镜头
        planned_shots = self._arrange_shots(
            shots, emotion_points, rhythm_points, params
        )

        # 确保镜头多样性
        planned_shots = self._ensure_diversity(planned_shots, params)

        return {
            "shots": planned_shots,
            "emotion_curve": [e.to_dict() for e in emotion_points],
            "rhythm_curve": [r.to_dict() for r in rhythm_points],
            "style": style,
            "params": params
        }

    def _get_style_params(self, style: str) -> Dict[str, Any]:
        """获取风格参数"""

        params = {
            "dynamic": {
                "emotion_arc": ["calm", "building", "intense", "climax", "calm"],
                "rhythm_pattern": "accelerating",
                "shot_diversity_threshold": 3,
                "climax_position": 0.7,
                "max_same_type_streak": 3
            },
            "calm": {
                "emotion_arc": ["calm", "gentle", "peaceful", "calm"],
                "rhythm_pattern": "steady",
                "shot_diversity_threshold": 5,
                "climax_position": 0.5,
                "max_same_type_streak": 5
            },
            "intense": {
                "emotion_arc": ["intense", "building", "explosive", "climax", "intense"],
                "rhythm_pattern": "accelerating",
                "shot_diversity_threshold": 2,
                "climax_position": 0.6,
                "max_same_type_streak": 2
            },
            "emotional": {
                "emotion_arc": ["sad", "reflective", "building", "emotional", "hopeful"],
                "rhythm_pattern": "wave",
                "shot_diversity_threshold": 4,
                "climax_position": 0.75,
                "max_same_type_streak": 4
            }
        }

        return params.get(style, params["dynamic"])

    def _arrange_shots(
        self,
        shots: List[Dict[str, Any]],
        emotion_points: List[EmotionPoint],
        rhythm_points: List[RhythmPoint],
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """根据情绪和节奏安排镜头"""

        planned = []
        shot_index = 0

        for i, (emotion, rhythm) in enumerate(zip(emotion_points, rhythm_points)):
            # 找到最适合当前情绪的镜头
            best_shot = self._find_best_shot_for_emotion(
                shots, emotion, shot_index, params
            )

            if best_shot:
                # 计算镜头时长（根据节奏）
                duration = self._calculate_duration(rhythm, params)

                # 添加到计划
                planned.append({
                    **best_shot,
                    "planned_start": emotion.time,
                    "planned_duration": duration,
                    "emotion": emotion.emotion,
                    "intensity": emotion.intensity
                })

                shot_index = (shot_index + 1) % len(shots)

        return planned

    def _find_best_shot_for_emotion(
        self,
        shots: List[Dict[str, Any]],
        emotion: EmotionPoint,
        current_index: int,
        params: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """找到最适合当前情绪的镜头"""

        # 情绪匹配映射
        emotion_action_map = {
            "calm": ["walking", "standing", "talking"],
            "intense": ["fighting", "running", "explosion"],
            "emotional": ["crying", "hugging", "screaming"],
            "building": ["walking", "running", "approaching"],
            "climax": ["explosion", "fighting", "dramatic_action"]
        }

        target_actions = emotion_action_map.get(emotion.emotion, [])

        # 查找匹配的镜头
        for i in range(len(shots)):
            idx = (current_index + i) % len(shots)
            shot = shots[idx]

            # 检查动作是否匹配
            shot_actions = shot.get("actions", [])
            if any(action in target_actions for action in shot_actions):
                return shot

        # 如果没有完全匹配，返回高光分数最高的镜头
        sorted_shots = sorted(
            shots,
            key=lambda x: x.get("highlight_score", 0),
            reverse=True
        )

        return sorted_shots[current_index % len(sorted_shots)] if sorted_shots else None

    def _calculate_duration(
        self,
        rhythm: RhythmPoint,
        params: Dict[str, Any]
    ) -> float:
        """根据节奏计算镜头时长"""

        pattern = params.get("rhythm_pattern", "steady")

        if pattern == "accelerating":
            # 节奏越来越快
            base_duration = 2.0
            return base_duration * (1.0 - rhythm.energy * 0.5)
        elif pattern == "steady":
            # 稳定节奏
            return 1.5
        elif pattern == "wave":
            # 波浪式节奏
            base_duration = 2.0
            return base_duration * (0.8 + 0.4 * np.sin(rhythm.time * 0.5))
        else:
            return 1.0

    def _ensure_diversity(
        self,
        shots: List[Dict[str, Any]],
        params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """确保镜头多样性"""

        max_streak = params.get("max_same_type_streak", 3)
        diverse_shots = []

        current_type = None
        streak_count = 0

        for shot in shots:
            # 获取镜头类型
            shot_type = self._get_shot_type(shot)

            if shot_type == current_type:
                streak_count += 1
            else:
                streak_count = 1
                current_type = shot_type

            # 如果连续相同类型超过阈值，插入不同类型镜头
            if streak_count > max_streak:
                # 找一个不同类型的镜头
                alternative = self._find_alternative_shot(
                    shots, shot_type, diverse_shots
                )
                if alternative:
                    diverse_shots.append(alternative)
                    streak_count = 1
                    current_type = self._get_shot_type(alternative)
                    continue

            diverse_shots.append(shot)

        return diverse_shots

    def _get_shot_type(self, shot: Dict[str, Any]) -> str:
        """获取镜头类型"""

        actions = shot.get("actions", [])
        if not actions:
            return "unknown"

        # 根据动作分类
        action_types = {
            "fighting": "action",
            "running": "action",
            "explosion": "action",
            "walking": "movement",
            "standing": "static",
            "talking": "dialogue",
            "crying": "emotional",
            "hugging": "emotional"
        }

        for action in actions:
            if action in action_types:
                return action_types[action]

        return "unknown"

    def _find_alternative_shot(
        self,
        shots: List[Dict[str, Any]],
        current_type: str,
        used_shots: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """找到不同类型的镜头"""

        for shot in shots:
            if self._get_shot_type(shot) != current_type:
                if shot not in used_shots:
                    return shot

        return None

    def create_emotion_arc(
        self,
        style: str,
        duration: float
    ) -> List[EmotionPoint]:
        """创建情绪弧线"""

        return self.emotion_curve.generate(duration, style)

    def create_rhythm_curve(
        self,
        style: str,
        duration: float
    ) -> List[RhythmPoint]:
        """创建节奏曲线"""

        return self.rhythm_planner.generate(duration, style)
