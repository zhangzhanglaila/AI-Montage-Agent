"""
Beat Engine Package
节拍引擎包 - 负责BGM分析、节拍检测、高潮识别
"""

from .beat_detector import BeatDetector
from .beat_sync_engine import BeatSyncEngine

__all__ = ["BeatDetector", "BeatSyncEngine"]
