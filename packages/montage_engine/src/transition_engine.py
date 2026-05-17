"""
Transition Engine
转场引擎 - 实现各种转场效果
"""

import subprocess
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum

class TransitionType(Enum):
    """转场类型枚举"""
    CUT = "cut"
    FADE = "fade"
    DISSOLVE = "dissolve"
    WIPE = "wipe"
    BLUR = "blur"
    FLASH = "flash"
    SHAKE = "shake"
    ZOOM = "zoom"
    MOTION_BLUR = "motion_blur"
    DIRECTIONAL_WIPE = "directional_wipe"

@dataclass
class Transition:
    """转场配置"""
    type: TransitionType
    duration: float = 0.5
    direction: str = "right"  # left, right, up, down
    intensity: float = 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "duration": self.duration,
            "direction": self.direction,
            "intensity": self.intensity
        }

class TransitionEngine:
    """
    转场引擎
    支持多种转场效果:
    - 基础: fade, dissolve, wipe
    - 高级: motion_blur, directional_wipe, camera_match_cut
    - AI: 基于内容的智能转场
    """

    def __init__(self, ffmpeg_path: str = "ffmpeg"):
        self.ffmpeg_path = ffmpeg_path

    def apply_transition(
        self,
        video1_path: str,
        video2_path: str,
        output_path: str,
        transition: Transition
    ) -> str:
        """
        在两个视频之间应用转场

        Args:
            video1_path: 第一个视频路径
            video2_path: 第二个视频路径
            output_path: 输出视频路径
            transition: 转场配置

        Returns:
            输出文件路径
        """
        # 根据转场类型选择FFmpeg滤镜
        filter_complex = self._build_filter_complex(transition)

        # 构建FFmpeg命令
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video1_path,
            "-i", video2_path,
            "-filter_complex", filter_complex,
            "-map", "[out]",
            output_path
        ]

        # 执行命令
        subprocess.run(cmd, check=True, capture_output=True)

        return output_path

    def _build_filter_complex(self, transition: Transition) -> str:
        """构建FFmpeg滤镜复杂图"""

        if transition.type == TransitionType.FADE:
            return self._build_fade_filter(transition)
        elif transition.type == TransitionType.DISSOLVE:
            return self._build_dissolve_filter(transition)
        elif transition.type == TransitionType.WIPE:
            return self._build_wipe_filter(transition)
        elif transition.type == TransitionType.BLUR:
            return self._build_blur_filter(transition)
        elif transition.type == TransitionType.FLASH:
            return self._build_flash_filter(transition)
        elif transition.type == TransitionType.MOTION_BLUR:
            return self._build_motion_blur_filter(transition)
        elif transition.type == TransitionType.ZOOM:
            return self._build_zoom_filter(transition)
        elif transition.type == TransitionType.SHAKE:
            return self._build_shake_filter(transition)
        elif transition.type == TransitionType.DIRECTIONAL_WIPE:
            return self._build_directional_wipe_filter(transition)
        else:
            return self._build_cut_filter(transition)

    def _build_fade_filter(self, transition: Transition) -> str:
        """构建淡入淡出滤镜"""
        duration = transition.duration
        return (
            f"[0:v]fade=t=out:st=0:d={duration}[v0];"
            f"[1:v]fade=t=in:st=0:d={duration}[v1];"
            f"[v0][v1]concat=n=2:v=1[out]"
        )

    def _build_dissolve_filter(self, transition: Transition) -> str:
        """构建溶解滤镜"""
        duration = transition.duration
        return (
            f"[0:v][1:v]xfade=transition=fade:duration={duration}:offset=0[out]"
        )

    def _build_wipe_filter(self, transition: Transition) -> str:
        """构建擦除滤镜"""
        duration = transition.duration
        direction = transition.direction

        # 根据方向选择xfade过渡类型
        if direction == "right":
            xfade_type = "wipeleft"
        elif direction == "left":
            xfade_type = "wiperight"
        elif direction == "down":
            xfade_type = "wipeup"
        else:
            xfade_type = "wipedown"

        return (
            f"[0:v][1:v]xfade=transition={xfade_type}:duration={duration}:offset=0[out]"
        )

    def _build_blur_filter(self, transition: Transition) -> str:
        """构建模糊转场滤镜"""
        duration = transition.duration
        return (
            f"[0:v]fade=t=out:st=0:d={duration/2}:alpha=1[v0];"
            f"[v0]boxblur=20:20[v0blur];"
            f"[1:v]fade=t=in:st=0:d={duration/2}:alpha=1[v1];"
            f"[v0blur][v1]overlay[out]"
        )

    def _build_flash_filter(self, transition: Transition) -> str:
        """构建闪光转场滤镜"""
        duration = transition.duration
        intensity = transition.intensity

        # 创建白色闪光帧
        return (
            f"color=white:s=1920x1080:d={duration/2}[flash];"
            f"[0:v][flash][1:v]concat=n=3:v=1[out]"
        )

    def _build_motion_blur_filter(self, transition: Transition) -> str:
        """构建动态模糊转场滤镜"""
        duration = transition.duration
        return (
            f"[0:v]fade=t=out:st=0:d={duration/2}[v0];"
            f"[v0]boxblur=10:5[v0blur];"
            f"[1:v]fade=t=in:st=0:d={duration/2}[v1];"
            f"[v0blur][v1]concat=n=2:v=1[out]"
        )

    def _build_cut_filter(self, transition: Transition) -> str:
        """构建硬切滤镜"""
        return "[0:v][1:v]concat=n=2:v=1[out]"

    def _build_zoom_filter(self, transition: Transition) -> str:
        """构建缩放转场滤镜（zoom in/out）"""
        duration = transition.duration
        return (
            f"[0:v]zoompan=z='min(zoom+0.015,1.5)':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080[v0];"
            f"[1:v]zoompan=z='if(eq(on,1),1.5,max(1.001,zoom-0.015))':d=1:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080[v1];"
            f"[v0][v1]concat=n=2:v=1[out]"
        )

    def _build_shake_filter(self, transition: Transition) -> str:
        """构建抖动转场滤镜（画面抖动后切换）"""
        duration = transition.duration
        intensity = transition.intensity
        return (
            f"[0:v]crop=in_w-{int(20*intensity)}:in_h-{int(20*intensity)}:"
            f"x='if(eq(mod(n,4),0),10,if(eq(mod(n,4),1),5,if(eq(mod(n,4),2),15,0)))':"
            f"y='if(eq(mod(n,4),0),5,if(eq(mod(n,4),1),10,if(eq(mod(n,4),2),0,15)))'[v0];"
            f"[v0]scale=1920:1080[v0s];"
            f"[v0s][1:v]concat=n=2:v=1[out]"
        )

    def _build_directional_wipe_filter(self, transition: Transition) -> str:
        """构建方向擦除滤镜"""
        duration = transition.duration
        direction = transition.direction

        if direction == "right":
            xfade_type = "wipeleft"
        elif direction == "left":
            xfade_type = "wiperight"
        elif direction == "up":
            xfade_type = "wipedown"
        elif direction == "down":
            xfade_type = "wipeup"
        else:
            xfade_type = "wipeleft"

        return (
            f"[0:v][1:v]xfade=transition={xfade_type}:duration={duration}:offset=0[out]"
        )

    def apply_multiple_transitions(
        self,
        videos: List[str],
        output_path: str,
        transitions: List[Transition]
    ) -> str:
        """
        对多个视频应用转场

        Args:
            videos: 视频路径列表
            output_path: 输出视频路径
            transitions: 转场配置列表

        Returns:
            输出文件路径
        """
        if len(videos) < 2:
            raise ValueError("Need at least 2 videos")

        if len(transitions) != len(videos) - 1:
            raise ValueError("Transitions count must be videos count - 1")

        # 逐个应用转场
        current_output = output_path
        temp_files = []

        for i in range(len(videos) - 1):
            if i == 0:
                temp_output = output_path
            else:
                temp_output = str(Path(output_path).parent / f"transition_temp_{i}.mp4")
                temp_files.append(temp_output)

            self.apply_transition(
                videos[i],
                videos[i + 1],
                temp_output,
                transitions[i]
            )

            if i > 0:
                videos[i + 1] = temp_output

        # 清理临时文件
        for temp_file in temp_files:
            import os
            if os.path.exists(temp_file):
                os.remove(temp_file)

        return output_path

    def suggest_transition(
        self,
        shot1_analysis: Dict[str, Any],
        shot2_analysis: Dict[str, Any]
    ) -> Transition:
        """
        基于镜头内容智能推荐转场

        Args:
            shot1_analysis: 第一个镜头的分析结果
            shot2_analysis: 第二个镜头的分析结果

        Returns:
            推荐的转场配置
        """
        # 获取镜头特征
        motion1 = shot1_analysis.get("motion_score", 0)
        motion2 = shot2_analysis.get("motion_score", 0)
        emotion1 = shot1_analysis.get("emotion", "neutral")
        emotion2 = shot2_analysis.get("emotion", "neutral")

        # 根据特征选择转场
        if motion1 > 0.8 or motion2 > 0.8:
            # 高动作场景，使用快速转场
            return Transition(
                type=TransitionType.MOTION_BLUR,
                duration=0.2
            )
        elif emotion1 != emotion2:
            # 情绪变化，使用溶解
            return Transition(
                type=TransitionType.DISSOLVE,
                duration=0.5
            )
        else:
            # 默认使用淡入淡出
            return Transition(
                type=TransitionType.FADE,
                duration=0.3
            )
