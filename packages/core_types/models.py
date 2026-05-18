"""统一数据类型定义"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class Shot:
    """镜头"""
    shot_id: int
    start_time: float
    end_time: float
    duration: float
    file_path: Optional[str] = None
    source_video: str = ""
    highlight_score: float = 0.0
    motion_score: float = 0.0
    actions: List[str] = field(default_factory=list)
    embedding: Optional[List[float]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "start": self.start_time,
            "end": self.end_time,
            "duration": self.duration,
            "file_path": self.file_path,
            "source_video": self.source_video,
            "highlight_score": self.highlight_score,
            "motion_score": self.motion_score,
            "actions": self.actions,
        }


@dataclass
class Beat:
    """节拍"""
    time: float
    strength: float
    beat_type: str = "normal"  # normal, strong, weak

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "strength": self.strength,
            "type": self.beat_type,
        }


@dataclass
class MusicSegment:
    """音乐片段"""
    start: float
    end: float
    segment_type: str  # intro, verse, chorus, bridge, climax, outro
    energy: float
    tempo: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "type": self.segment_type,
            "energy": self.energy,
            "tempo": self.tempo,
        }


@dataclass
class HighlightScore:
    """高光评分"""
    shot_id: int
    motion_score: float = 0.0
    face_emotion_score: float = 0.0
    camera_movement_score: float = 0.0
    audio_score: float = 0.0
    overall_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "motion_score": self.motion_score,
            "face_emotion_score": self.face_emotion_score,
            "camera_movement_score": self.camera_movement_score,
            "audio_score": self.audio_score,
            "highlight_score": self.overall_score,
        }


@dataclass
class TimelineEntry:
    """时间线条目"""
    shot_id: int
    shot_path: str
    start_time: float
    end_time: float
    duration: float
    beat_time: float
    speed_factor: float = 1.0
    transition_type: str = "cut"
    transition_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shot_id": self.shot_id,
            "shot_path": self.shot_path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "beat_time": self.beat_time,
            "speed_factor": self.speed_factor,
            "transition_type": self.transition_type,
            "transition_duration": self.transition_duration,
        }


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
            "intensity": self.intensity,
        }


@dataclass
class MotionData:
    """运动数据"""
    magnitude: float = 0.0
    direction_x: float = 0.0
    direction_y: float = 0.0
    shake: float = 0.0
    zoom: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "magnitude": self.magnitude,
            "direction_x": self.direction_x,
            "direction_y": self.direction_y,
            "shake": self.shake,
            "zoom": self.zoom,
        }


@dataclass
class BeatAnalysis:
    """节拍分析结果"""
    beats: List[Beat]
    tempo: float
    energy_curve: List[Dict[str, float]]
    drops: List[Dict[str, float]]
    segments: List[MusicSegment]
    duration: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "beats": [b.to_dict() for b in self.beats],
            "tempo": self.tempo,
            "energy_curve": self.energy_curve,
            "drops": self.drops,
            "segments": [s.to_dict() for s in self.segments],
            "duration": self.duration,
        }
