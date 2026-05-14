"""
Highlight Scoring Module
高光评分系统 - 自动评估镜头的精彩程度
"""

import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class HighlightScore:
    """高光评分数据结构"""
    shot_id: int
    motion_score: float
    face_emotion_score: float
    camera_movement_score: float
    audio_score: float
    overall_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "motion_score": self.motion_score,
            "face_emotion_score": self.face_emotion_score,
            "camera_movement_score": self.camera_movement_score,
            "audio_score": self.audio_score,
            "highlight_score": self.overall_score
        }

class HighlightScorer:
    """
    高光评分器
    评估镜头的精彩程度
    评分维度:
    1. 动作强度 (motion magnitude)
    2. 人脸情绪 (anger, crying, screaming)
    3. 镜头变化 (camera shake, zoom, whip pan)
    4. 音量 (高潮部分加权)
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        # 默认权重
        self.weights = weights or {
            "motion": 0.35,
            "face_emotion": 0.25,
            "camera_movement": 0.25,
            "audio": 0.15
        }

    def score_shot(
        self,
        shot_id: int,
        motion_data: Dict[str, Any],
        face_data: Optional[Dict[str, Any]] = None,
        camera_data: Optional[Dict[str, Any]] = None,
        audio_data: Optional[Dict[str, Any]] = None
    ) -> HighlightScore:
        """
        为单个镜头评分

        Args:
            shot_id: 镜头ID
            motion_data: 动作数据
            face_data: 人脸情绪数据
            camera_data: 镜头运动数据
            audio_data: 音频数据

        Returns:
            高光评分
        """

        # 计算动作强度分数
        motion_score = self._calculate_motion_score(motion_data)

        # 计算人脸情绪分数
        face_emotion_score = self._calculate_face_emotion_score(face_data)

        # 计算镜头运动分数
        camera_movement_score = self._calculate_camera_movement_score(camera_data)

        # 计算音频分数
        audio_score = self._calculate_audio_score(audio_data)

        # 计算综合分数
        overall_score = (
            self.weights["motion"] * motion_score +
            self.weights["face_emotion"] * face_emotion_score +
            self.weights["camera_movement"] * camera_movement_score +
            self.weights["audio"] * audio_score
        )

        return HighlightScore(
            shot_id=shot_id,
            motion_score=motion_score,
            face_emotion_score=face_emotion_score,
            camera_movement_score=camera_movement_score,
            audio_score=audio_score,
            overall_score=overall_score
        )

    def score_shots(
        self,
        shots_data: List[Dict[str, Any]]
    ) -> List[HighlightScore]:
        """
        批量为镜头评分

        Args:
            shots_data: 镜头数据列表

        Returns:
            评分列表
        """
        scores = []

        for shot_data in shots_data:
            score = self.score_shot(
                shot_id=shot_data["shot_id"],
                motion_data=shot_data.get("motion", {}),
                face_data=shot_data.get("face"),
                camera_data=shot_data.get("camera"),
                audio_data=shot_data.get("audio")
            )
            scores.append(score)

        return scores

    def _calculate_motion_score(self, motion_data: Dict[str, Any]) -> float:
        """
        计算动作强度分数
        基于光流或帧差分计算的运动幅度
        """
        if not motion_data:
            return 0.0

        # 提取运动幅度
        magnitude = motion_data.get("magnitude", 0.0)

        # 归一化到0-1
        # 使用sigmoid函数进行平滑归一化
        score = 1 / (1 + np.exp(-magnitude + 5))

        return float(score)

    def _calculate_face_emotion_score(
        self,
        face_data: Optional[Dict[str, Any]]
    ) -> float:
        """
        计算人脸情绪分数
        高能量情绪(愤怒、哭泣、尖叫)得分更高
        """
        if not face_data:
            return 0.0

        # 情绪权重
        emotion_weights = {
            "angry": 0.9,
            "fear": 0.8,
            "surprise": 0.7,
            "sad": 0.6,
            "happy": 0.5,
            "disgust": 0.4,
            "neutral": 0.1
        }

        # 获取检测到的情绪
        emotions = face_data.get("emotions", [])
        if not emotions:
            return 0.0

        # 计算加权平均
        total_weight = 0
        weighted_sum = 0

        for emotion in emotions:
            emotion_type = emotion.get("type", "neutral")
            confidence = emotion.get("confidence", 0.0)

            weight = emotion_weights.get(emotion_type, 0.1)
            weighted_sum += weight * confidence
            total_weight += confidence

        if total_weight == 0:
            return 0.0

        return float(weighted_sum / total_weight)

    def _calculate_camera_movement_score(
        self,
        camera_data: Optional[Dict[str, Any]]
    ) -> float:
        """
        计算镜头运动分数
        快速运动(摇摄、变焦、抖动)得分更高
        """
        if not camera_data:
            return 0.0

        # 提取镜头运动特征
        shake = camera_data.get("shake", 0.0)
        zoom = camera_data.get("zoom", 0.0)
        pan_speed = camera_data.get("pan_speed", 0.0)

        # 综合评分
        # 抖动表示紧张/动作场景
        # 变焦表示强调
        # 快速摇摄表示动作
        score = (
            0.4 * min(shake * 10, 1.0) +
            0.3 * min(abs(zoom) * 5, 1.0) +
            0.3 * min(pan_speed * 2, 1.0)
        )

        return float(min(score, 1.0))

    def _calculate_audio_score(
        self,
        audio_data: Optional[Dict[str, Any]]
    ) -> float:
        """
        计算音频分数
        高音量、高能量的片段得分更高
        """
        if not audio_data:
            return 0.0

        # 提取音频特征
        volume = audio_data.get("volume", 0.0)
        energy = audio_data.get("energy", 0.0)

        # 归一化
        volume_score = min(volume / 0.8, 1.0)  # 假设0.8是最大音量
        energy_score = min(energy * 2, 1.0)

        # 综合评分
        score = 0.6 * volume_score + 0.4 * energy_score

        return float(score)

    def get_highlight_shots(
        self,
        scores: List[HighlightScore],
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[HighlightScore]:
        """
        获取高光镜头

        Args:
            scores: 评分列表
            top_k: 返回前k个
            threshold: 最低分数阈值

        Returns:
            高光镜头列表
        """
        # 按分数排序
        sorted_scores = sorted(
            scores,
            key=lambda x: x.overall_score,
            reverse=True
        )

        # 过滤低分镜头
        filtered = [
            s for s in sorted_scores
            if s.overall_score >= threshold
        ]

        return filtered[:top_k]

    def normalize_scores(
        self,
        scores: List[HighlightScore]
    ) -> List[HighlightScore]:
        """
        归一化分数到0-1范围
        """
        if not scores:
            return scores

        # 提取所有分数
        all_scores = [s.overall_score for s in scores]

        # 计算最小值和最大值
        min_score = min(all_scores)
        max_score = max(all_scores)

        # 归一化
        for score in scores:
            if max_score - min_score > 0:
                score.overall_score = (
                    (score.overall_score - min_score) /
                    (max_score - min_score)
                )

        return scores
