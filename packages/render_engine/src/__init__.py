"""
Render Engine Package
渲染引擎包 - 负责最终视频生成、FFmpeg执行
"""

from .ffmpeg_executor import FFmpegExecutor

__all__ = ["FFmpegExecutor"]
