"""
OTIO 时间线导出 - OpenTimelineIO 格式

支持 DaVinci Resolve / Premiere Pro / Final Cut Pro / Avid

用法：
    from packages.timeline_export.src.otio_exporter import export_otio
    export_otio(timeline_entries, bgm_path, "output.otio")
"""

import json
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict


def _seconds_to_rational_timecode(seconds: float, fps: float = 30.0) -> dict:
    """将秒数转换为 OTIO RationalTime 格式"""
    frames = int(seconds * fps)
    return {
        "OTIO_SCHEMA": "RationalTime.1",
        "value": frames,
        "rate": fps,
    }


def _seconds_to_time_range(start: float, duration: float, fps: float = 30.0) -> dict:
    """将秒数转换为 OTIO TimeRange 格式"""
    return {
        "OTIO_SCHEMA": "TimeRange.1",
        "start_time": _seconds_to_rational_timecode(start, fps),
        "duration": _seconds_to_rational_timecode(duration, fps),
    }


def _create_media_reference(source_path: str, fps: float = 30.0) -> dict:
    """创建 OTIO 媒体引用"""
    return {
        "OTIO_SCHEMA": "ExternalReference.1",
        "target_url": Path(source_path).resolve().as_uri(),
        "available_range": None,
    }


def _create_clip(
    name: str,
    source_path: str,
    source_start: float,
    duration: float,
    fps: float = 30.0,
) -> dict:
    """创建 OTIO Clip"""
    return {
        "OTIO_SCHEMA": "Clip.1",
        "name": name,
        "source_range": _seconds_to_time_range(source_start, duration, fps),
        "media_reference": _create_media_reference(source_path, fps),
        "metadata": {},
    }


def _create_gap(duration: float, fps: float = 30.0) -> dict:
    """创建 OTIO Gap（空白段）"""
    return {
        "OTIO_SCHEMA": "Gap.1",
        "source_range": _seconds_to_time_range(0, duration, fps),
        "metadata": {},
    }


def _create_transition(
    name: str,
    in_offset: float,
    out_offset: float,
    transition_type: str = "dissolve",
    fps: float = 30.0,
) -> dict:
    """创建 OTIO Transition"""
    return {
        "OTIO_SCHEMA": "Transition.1",
        "name": name,
        "transition_type": f"custom_{transition_type}" if transition_type not in ("dissolve", "fade_to_black", "fade_to_white") else transition_type,
        "in_offset": _seconds_to_rational_timecode(in_offset, fps),
        "out_offset": _seconds_to_rational_timecode(out_offset, fps),
        "metadata": {},
    }


def export_otio(
    timeline_entries: list,
    bgm_path: str,
    output_path: str,
    fps: float = 30.0,
    project_name: str = "AI Montage",
) -> str:
    """
    导出 OTIO 时间线文件

    Args:
        timeline_entries: 时间线条目列表（需有 shot_path, start_time, duration, transition_type 等属性）
        bgm_path: BGM 文件路径
        output_path: 输出 .otio 文件路径
        fps: 帧率
        project_name: 项目名称

    Returns:
        输出文件路径
    """
    print(f"  导出 OTIO: {output_path}")

    clips = []
    for i, entry in enumerate(timeline_entries):
        shot_path = getattr(entry, "shot_path", "") or ""
        start_time = getattr(entry, "start_time", 0.0)
        duration = getattr(entry, "duration", 1.0)
        transition_type = getattr(entry, "transition_type", "cut")
        transition_duration = getattr(entry, "transition_duration", 0.0)

        # 添加转场（非 cut 时）
        if transition_duration > 0 and transition_type != "cut" and i > 0:
            clips.append(_create_transition(
                name=f"Transition_{i}",
                in_offset=transition_duration / 2,
                out_offset=transition_duration / 2,
                transition_type=transition_type,
                fps=fps,
            ))

        # 添加片段
        clip_name = Path(shot_path).stem if shot_path else f"Shot_{i}"
        clips.append(_create_clip(
            name=clip_name,
            source_path=shot_path,
            source_start=0.0,
            duration=duration,
            fps=fps,
        ))

    # 构建完整的 OTIO 结构
    otio = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": project_name,
        "tracks": [
            {
                "OTIO_SCHEMA": "Track.1",
                "name": "Video",
                "kind": "Video",
                "children": clips,
                "metadata": {},
            },
            {
                "OTIO_SCHEMA": "Track.1",
                "name": "Audio",
                "kind": "Audio",
                "children": [
                    _create_clip(
                        name="BGM",
                        source_path=bgm_path,
                        source_start=0.0,
                        duration=sum(
                            getattr(e, "duration", 1.0) for e in timeline_entries
                        ),
                        fps=fps,
                    )
                ] if bgm_path else [],
                "metadata": {},
            },
        ],
        "metadata": {
            "ai_montage_agent": {
                "version": "1.0.0",
                "fps": fps,
                "total_clips": len(timeline_entries),
                "total_duration": sum(getattr(e, "duration", 1.0) for e in timeline_entries),
            }
        },
    }

    # 写入文件
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(otio, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"  OTIO 导出完成: {output_path}")
    return output_path


def export_otio_from_pipeline(pipeline, output_path: str, fps: float = 30.0) -> str:
    """
    从 pipeline 对象导出 OTIO

    Args:
        pipeline: MontagePipeline 实例（需有 _last_timeline, _last_bgm_path 属性）
        output_path: 输出路径
        fps: 帧率

    Returns:
        输出文件路径
    """
    timeline = getattr(pipeline, "_last_timeline", [])
    bgm_path = getattr(pipeline, "_last_bgm_path", "")

    if not timeline:
        print("  无时间线数据，跳过 OTIO 导出")
        return ""

    return export_otio(timeline, bgm_path, output_path, fps=fps)
