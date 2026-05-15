"""
时间轴导出模块 - 将剪辑结果导出为专业 NLE 格式

支持：
- CMX 3600 EDL (.edl) - 通用格式，所有 NLE 都支持
- FCP XML v7 (.xml) - DaVinci/Premiere/剪映
- CSV (.csv) - 电子表格查看
- JSON (.json) - 完整元数据
"""

import csv
import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any


@dataclass
class Clip:
    """时间轴中的一个片段"""
    source_path: str
    start_time: float      # 源文件中的起始时间（秒）
    duration: float         # 片段时长（秒）
    timeline_start: float   # 在最终时间轴中的起始位置（秒）
    metadata: Dict = field(default_factory=dict)


@dataclass
class Timeline:
    """完整的时间轴"""
    clips: List[Clip]
    audio_path: str
    total_duration: float
    fps: float = 30.0
    resolution: Tuple[int, int] = (1920, 1080)
    project_name: str = "montage"


class TimelineExporter:
    """时间轴导出器"""

    def __init__(self, output_dir: str = "output"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

    def export(
        self,
        timeline: Timeline,
        formats: Optional[List[str]] = None,
    ) -> Dict[str, str]:
        """导出时间轴到指定格式

        Args:
            timeline: 时间轴对象
            formats: 要导出的格式列表，None 表示全部导出
                     可选: edl, xml, csv, json

        Returns:
            {格式: 文件路径} 字典
        """
        if formats is None:
            formats = ["edl", "xml", "csv", "json"]

        exported = {}

        if "edl" in formats:
            exported["edl"] = self._export_edl(timeline)

        if "xml" in formats:
            exported["xml"] = self._export_xml(timeline)

        if "csv" in formats:
            exported["csv"] = self._export_csv(timeline)

        if "json" in formats:
            exported["json"] = self._export_json(timeline)

        return exported

    @staticmethod
    def _seconds_to_timecode(seconds: float, fps: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        f = int((seconds % 1) * fps)
        return f"{h:02d}:{m:02d}:{s:02d}:{f:02d}"

    def _export_edl(self, timeline: Timeline) -> str:
        path = os.path.join(self.output_dir, f"{timeline.project_name}.edl")
        with open(path, "w") as fh:
            fh.write(f"TITLE: {timeline.project_name}\n")
            fh.write("FCM: NON-DROP FRAME\n\n")

            for i, clip in enumerate(timeline.clips, 1):
                src_in = self._seconds_to_timecode(clip.start_time, timeline.fps)
                src_out = self._seconds_to_timecode(clip.start_time + clip.duration, timeline.fps)
                rec_in = self._seconds_to_timecode(clip.timeline_start, timeline.fps)
                rec_out = self._seconds_to_timecode(clip.timeline_start + clip.duration, timeline.fps)

                reel = os.path.splitext(os.path.basename(clip.source_path))[0][:8]
                fh.write(f"{i:03d}  {reel:<8} V     C        ")
                fh.write(f"{src_in} {src_out} {rec_in} {rec_out}\n")
                fh.write(f"* FROM CLIP NAME: {os.path.basename(clip.source_path)}\n")
                fh.write(f"* SOURCE FILE: {clip.source_path}\n\n")

        return path

    def _export_xml(self, timeline: Timeline) -> str:
        path = os.path.join(self.output_dir, f"{timeline.project_name}.xml")
        fps_int = int(timeline.fps)
        w, h = timeline.resolution

        with open(path, "w", encoding="utf-8") as fh:
            fh.write('<?xml version="1.0" encoding="UTF-8"?>\n')
            fh.write('<!DOCTYPE xmeml>\n')
            fh.write('<xmeml version="4">\n')
            fh.write('  <project>\n')
            fh.write(f'    <name>{timeline.project_name}</name>\n')
            fh.write('    <children>\n')
            fh.write(f'      <sequence id="sequence-1">\n')
            fh.write(f'        <name>{timeline.project_name}</name>\n')
            fh.write(f'        <duration>{int(timeline.total_duration * fps_int)}</duration>\n')
            fh.write('        <rate>\n')
            fh.write(f'          <timebase>{fps_int}</timebase>\n')
            fh.write('          <ntsc>FALSE</ntsc>\n')
            fh.write('        </rate>\n')
            fh.write('        <media>\n')
            fh.write('          <video>\n')
            fh.write('            <format>\n')
            fh.write('              <samplecharacteristics>\n')
            fh.write(f'                <width>{w}</width>\n')
            fh.write(f'                <height>{h}</height>\n')
            fh.write('              </samplecharacteristics>\n')
            fh.write('            </format>\n')
            fh.write('            <track>\n')

            for i, clip in enumerate(timeline.clips, 1):
                start_frame = int(clip.timeline_start * fps_int)
                end_frame = int((clip.timeline_start + clip.duration) * fps_int)
                src_in_frame = int(clip.start_time * fps_int)
                src_out_frame = src_in_frame + (end_frame - start_frame)
                filename = os.path.basename(clip.source_path)

                fh.write(f'              <clipitem id="clip-{i}">\n')
                fh.write(f'                <name>{filename}</name>\n')
                fh.write(f'                <duration>{end_frame - start_frame}</duration>\n')
                fh.write(f'                <start>{start_frame}</start>\n')
                fh.write(f'                <end>{end_frame}</end>\n')
                fh.write(f'                <in>{src_in_frame}</in>\n')
                fh.write(f'                <out>{src_out_frame}</out>\n')
                fh.write(f'                <file id="file-{i}">\n')
                fh.write(f'                  <name>{filename}</name>\n')
                fh.write(f'                  <pathurl>file://{Path(clip.source_path).resolve().as_posix()}</pathurl>\n')
                fh.write(f'                </file>\n')
                fh.write(f'              </clipitem>\n')

            fh.write('            </track>\n')
            fh.write('          </video>\n')

            # Audio track
            fh.write('          <audio>\n')
            fh.write('            <track>\n')
            audio_name = os.path.basename(timeline.audio_path)
            total_frames = int(timeline.total_duration * fps_int)
            fh.write(f'              <clipitem id="audio-1">\n')
            fh.write(f'                <name>{audio_name}</name>\n')
            fh.write(f'                <duration>{total_frames}</duration>\n')
            fh.write(f'                <start>0</start>\n')
            fh.write(f'                <end>{total_frames}</end>\n')
            fh.write(f'                <in>0</in>\n')
            fh.write(f'                <out>{total_frames}</out>\n')
            fh.write(f'                <file id="file-audio">\n')
            fh.write(f'                  <name>{audio_name}</name>\n')
            fh.write(f'                  <pathurl>file://{Path(timeline.audio_path).resolve().as_posix()}</pathurl>\n')
            fh.write(f'                </file>\n')
            fh.write(f'              </clipitem>\n')
            fh.write('            </track>\n')
            fh.write('          </audio>\n')

            fh.write('        </media>\n')
            fh.write('      </sequence>\n')
            fh.write('    </children>\n')
            fh.write('  </project>\n')
            fh.write('</xmeml>\n')

        return path

    def _export_csv(self, timeline: Timeline) -> str:
        path = os.path.join(self.output_dir, f"{timeline.project_name}.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as fh:
            writer = csv.writer(fh)
            writer.writerow([
                "序号", "源文件", "源入点(秒)", "源出点(秒)",
                "时间轴入点(秒)", "时间轴出点(秒)", "时长(秒)",
                "源入点(TC)", "源出点(TC)", "时间轴入点(TC)", "时间轴出点(TC)",
            ])
            for i, clip in enumerate(timeline.clips, 1):
                writer.writerow([
                    i,
                    clip.source_path,
                    f"{clip.start_time:.2f}",
                    f"{clip.start_time + clip.duration:.2f}",
                    f"{clip.timeline_start:.2f}",
                    f"{clip.timeline_start + clip.duration:.2f}",
                    f"{clip.duration:.2f}",
                    self._seconds_to_timecode(clip.start_time, timeline.fps),
                    self._seconds_to_timecode(clip.start_time + clip.duration, timeline.fps),
                    self._seconds_to_timecode(clip.timeline_start, timeline.fps),
                    self._seconds_to_timecode(clip.timeline_start + clip.duration, timeline.fps),
                ])
        return path

    def _export_json(self, timeline: Timeline) -> str:
        path = os.path.join(self.output_dir, f"{timeline.project_name}.json")
        data = {
            "project_name": timeline.project_name,
            "total_duration": timeline.total_duration,
            "fps": timeline.fps,
            "resolution": list(timeline.resolution),
            "audio_file": timeline.audio_path,
            "clips": [
                {
                    "index": i + 1,
                    "source_file": c.source_path,
                    "source_in": c.start_time,
                    "source_out": c.start_time + c.duration,
                    "timeline_in": c.timeline_start,
                    "timeline_out": c.timeline_start + c.duration,
                    "duration": c.duration,
                    "metadata": c.metadata,
                }
                for i, c in enumerate(timeline.clips)
            ],
            "exported_at": datetime.now().isoformat(),
        }
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)
        return path
