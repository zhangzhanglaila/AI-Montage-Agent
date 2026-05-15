"""
Video Understanding Package
视频语义理解包 - 负责视频分析、镜头检测、语义提取
"""

from .shot_detector import ShotDetector
from .highlight_scorer import HighlightScorer

__all__ = ["ShotDetector", "HighlightScorer"]
