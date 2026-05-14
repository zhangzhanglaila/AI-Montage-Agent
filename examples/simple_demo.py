"""
AI Montage Agent 简单演示脚本
直接定义核心类，避免导入问题
"""

from dataclasses import dataclass
from typing import List, Dict, Any
import numpy as np


@dataclass
class Shot:
    """镜头数据结构"""
    shot_id: int
    start_time: float
    end_time: float
    duration: float
    file_path: str = None

    def to_dict(self):
        return {
            "shot_id": self.shot_id,
            "start": self.start_time,
            "end": self.end_time,
            "duration": self.duration,
            "file_path": self.file_path
        }


@dataclass
class EmotionPoint:
    """情绪点"""
    time: float
    emotion: str
    intensity: float


@dataclass
class RhythmPoint:
    """节奏点"""
    time: float
    tempo: float
    energy: float


class HighlightScorer:
    """高光评分器"""

    def __init__(self):
        self.weights = {
            "motion": 0.35,
            "face_emotion": 0.25,
            "camera_movement": 0.25,
            "audio": 0.15
        }

    def score_shot(self, shot_id, motion_data, face_data=None, camera_data=None):
        motion_score = self._calculate_motion_score(motion_data)
        face_score = self._calculate_face_score(face_data)
        camera_score = self._calculate_camera_score(camera_data)
        audio_score = 0.5

        overall = (
            self.weights["motion"] * motion_score +
            self.weights["face_emotion"] * face_score +
            self.weights["camera_movement"] * camera_score +
            self.weights["audio"] * audio_score
        )

        return {
            "shot_id": shot_id,
            "highlight_score": overall
        }

    def _calculate_motion_score(self, motion_data):
        magnitude = motion_data.get("magnitude", 0.0)
        return 1 / (1 + np.exp(-magnitude + 5))

    def _calculate_face_score(self, face_data):
        if not face_data:
            return 0.0
        emotions = face_data.get("emotions", [])
        if not emotions:
            return 0.0
        weights = {"angry": 0.9, "surprise": 0.7, "sad": 0.6, "happy": 0.5, "neutral": 0.1}
        total = sum(weights.get(e.get("type", "neutral"), 0.1) * e.get("confidence", 0) for e in emotions)
        count = sum(e.get("confidence", 0) for e in emotions)
        return total / count if count > 0 else 0.0

    def _calculate_camera_score(self, camera_data):
        if not camera_data:
            return 0.0
        shake = camera_data.get("shake", 0.0)
        zoom = camera_data.get("zoom", 0.0)
        pan = camera_data.get("pan_speed", 0.0)
        return min(0.4 * min(shake * 10, 1.0) + 0.3 * min(abs(zoom) * 5, 1.0) + 0.3 * min(pan * 2, 1.0), 1.0)


class BeatSyncEngine:
    """卡点同步引擎"""

    def __init__(self, min_duration=0.3, max_duration=5.0):
        self.min_duration = min_duration
        self.max_duration = max_duration

    def sync(self, shots, beats, style="dynamic"):
        if not shots or not beats:
            return []

        params = self._get_style_params(style)
        timeline = []
        beat_times = [b["time"] for b in beats]

        for i, shot in enumerate(shots):
            beat_idx = i % len(beat_times)
            beat_time = beat_times[beat_idx]

            highlight_score = shot.get("highlight_score", 0.5)
            if highlight_score > 0.8:
                duration = params["climax_duration"]
            elif highlight_score > 0.5:
                duration = params["normal_duration"]
            else:
                duration = params["calm_duration"]

            duration = max(self.min_duration, min(duration, self.max_duration))

            timeline.append({
                "shot_id": shot.get("shot_id", i),
                "start_time": beat_time,
                "end_time": beat_time + duration,
                "duration": duration,
                "beat_time": beat_time,
                "speed_factor": 1.0
            })

        return timeline

    def _get_style_params(self, style):
        return {
            "dynamic": {"climax_duration": 0.3, "normal_duration": 1.0, "calm_duration": 2.0},
            "calm": {"climax_duration": 1.0, "normal_duration": 2.5, "calm_duration": 4.0},
            "intense": {"climax_duration": 0.2, "normal_duration": 0.5, "calm_duration": 1.5}
        }.get(style, {"climax_duration": 0.3, "normal_duration": 1.0, "calm_duration": 2.0})


class EmotionCurveGenerator:
    """情绪曲线生成器"""

    def generate(self, duration, style="dynamic"):
        num_points = int(duration / 0.5)
        times = np.linspace(0, duration, num_points)

        arcs = {
            "dynamic": [
                {"emotion": "calm", "start": 0.0, "end": 0.15, "intensity": 0.3},
                {"emotion": "building", "start": 0.15, "end": 0.35, "intensity": 0.5},
                {"emotion": "intense", "start": 0.35, "end": 0.55, "intensity": 0.7},
                {"emotion": "climax", "start": 0.70, "end": 0.85, "intensity": 1.0},
                {"emotion": "calm", "start": 0.85, "end": 1.0, "intensity": 0.4}
            ]
        }

        arc = arcs.get(style, arcs["dynamic"])
        points = []

        for t in times:
            position = t / duration
            for segment in arc:
                if segment["start"] <= position <= segment["end"]:
                    local_pos = (position - segment["start"]) / (segment["end"] - segment["start"])
                    intensity = segment["intensity"] * np.sin(local_pos * np.pi)
                    points.append(EmotionPoint(time=t, emotion=segment["emotion"], intensity=intensity))
                    break

        return points


class RhythmPlanner:
    """节奏规划器"""

    def generate(self, duration, style="dynamic"):
        num_points = int(duration / 0.5)
        times = np.linspace(0, duration, num_points)

        patterns = {
            "dynamic": {"base_tempo": 120, "variation": 40},
            "calm": {"base_tempo": 80, "variation": 20},
            "intense": {"base_tempo": 140, "variation": 60}
        }

        pattern = patterns.get(style, patterns["dynamic"])
        points = []

        for t in times:
            position = t / duration
            tempo = pattern["base_tempo"] + pattern["variation"] * position
            energy = 0.3 + 0.7 * position
            points.append(RhythmPoint(time=t, tempo=tempo, energy=energy))

        return points


def demo_shot_detection():
    """演示镜头检测"""
    print("\n" + "="*50)
    print("演示: 镜头检测")
    print("="*50)

    shots = [
        Shot(shot_id=0, start_time=0.0, end_time=2.5, duration=2.5),
        Shot(shot_id=1, start_time=2.5, end_time=5.0, duration=2.5),
        Shot(shot_id=2, start_time=5.0, end_time=7.8, duration=2.8),
        Shot(shot_id=3, start_time=7.8, end_time=10.0, duration=2.2),
    ]

    print(f"检测到 {len(shots)} 个镜头:")
    for shot in shots:
        print(f"  - 镜头 {shot.shot_id}: {shot.start_time:.1f}s - {shot.end_time:.1f}s")

    return shots


def demo_beat_detection():
    """演示节拍检测"""
    print("\n" + "="*50)
    print("演示: 节拍检测")
    print("="*50)

    beats = [
        {"time": 0.5, "strength": 0.8, "type": "strong"},
        {"time": 1.0, "strength": 0.5, "type": "normal"},
        {"time": 1.5, "strength": 0.9, "type": "strong"},
        {"time": 2.0, "strength": 0.4, "type": "weak"},
        {"time": 2.5, "strength": 0.85, "type": "strong"},
        {"time": 3.0, "strength": 0.6, "type": "normal"},
        {"time": 3.5, "strength": 0.95, "type": "strong"},
        {"time": 4.0, "strength": 0.3, "type": "weak"},
    ]

    print(f"检测到 {len(beats)} 个节拍:")
    for beat in beats[:5]:
        print(f"  - {beat['time']:.1f}s: {beat['type']} (强度: {beat['strength']:.2f})")

    return {"beats": beats, "tempo": 120.0}


def demo_highlight_scoring():
    """演示高光评分"""
    print("\n" + "="*50)
    print("演示: 高光评分")
    print("="*50)

    scorer = HighlightScorer()

    shots_data = [
        {
            "shot_id": 0,
            "motion_data": {"magnitude": 3.0},
            "face_data": {"emotions": [{"type": "neutral", "confidence": 0.8}]},
            "camera_data": {"shake": 0.2, "zoom": 0.1, "pan_speed": 0.1}
        },
        {
            "shot_id": 1,
            "motion_data": {"magnitude": 8.0},
            "face_data": {"emotions": [{"type": "angry", "confidence": 0.9}]},
            "camera_data": {"shake": 0.8, "zoom": 0.5, "pan_speed": 0.7}
        },
        {
            "shot_id": 2,
            "motion_data": {"magnitude": 5.0},
            "face_data": {"emotions": [{"type": "sad", "confidence": 0.7}]},
            "camera_data": {"shake": 0.3, "zoom": 0.2, "pan_speed": 0.2}
        },
        {
            "shot_id": 3,
            "motion_data": {"magnitude": 9.0},
            "face_data": {"emotions": [{"type": "surprise", "confidence": 0.95}]},
            "camera_data": {"shake": 0.9, "zoom": 0.8, "pan_speed": 0.9}
        },
    ]

    scores = [scorer.score_shot(shot["shot_id"], shot["motion_data"], shot.get("face_data"), shot.get("camera_data")) for shot in shots_data]

    print("高光评分结果:")
    for score in scores:
        print(f"  - 镜头 {score['shot_id']}: {score['highlight_score']:.2f}")

    # 按分数排序
    sorted_scores = sorted(scores, key=lambda x: x["highlight_score"], reverse=True)
    print(f"\nTop 2 高光镜头: {[s['shot_id'] for s in sorted_scores[:2]]}")

    return scores


def demo_beat_sync():
    """演示卡点同步"""
    print("\n" + "="*50)
    print("演示: 卡点同步")
    print("="*50)

    engine = BeatSyncEngine()

    shots = [
        {"shot_id": 0, "highlight_score": 0.6},
        {"shot_id": 1, "highlight_score": 0.9},
        {"shot_id": 2, "highlight_score": 0.7},
        {"shot_id": 3, "highlight_score": 0.95},
    ]

    beats = [
        {"time": 0.5, "strength": 0.8},
        {"time": 1.0, "strength": 0.5},
        {"time": 1.5, "strength": 0.9},
        {"time": 2.0, "strength": 0.4},
        {"time": 2.5, "strength": 0.85},
    ]

    timeline = engine.sync(shots, beats, style="dynamic")

    print(f"生成 {len(timeline)} 个时间线条目:")
    for entry in timeline:
        print(f"  - 镜头 {entry['shot_id']}: {entry['start_time']:.2f}s - {entry['end_time']:.2f}s")

    return timeline


def demo_emotion_curve():
    """演示情绪曲线"""
    print("\n" + "="*50)
    print("演示: 情绪曲线")
    print("="*50)

    generator = EmotionCurveGenerator()
    points = generator.generate(10.0, "dynamic")

    print(f"生成 {len(points)} 个情绪点")
    print("\n前5个情绪点:")
    for p in points[:5]:
        print(f"  {p.time:.1f}s: {p.emotion} (强度: {p.intensity:.2f})")

    return points


def demo_rhythm_planner():
    """演示节奏规划"""
    print("\n" + "="*50)
    print("演示: 节奏规划")
    print("="*50)

    planner = RhythmPlanner()
    points = planner.generate(10.0, "dynamic")

    print(f"生成 {len(points)} 个节奏点")
    print("\n前5个节奏点:")
    for p in points[:5]:
        print(f"  {p.time:.1f}s: 节奏={p.tempo:.0f}BPM, 能量={p.energy:.2f}")

    return points


def demo_full_workflow():
    """演示完整工作流程"""
    print("\n" + "="*50)
    print("演示: 完整工作流程")
    print("="*50)

    # 1. 检测镜头
    print("\n[1/4] 检测镜头...")
    shots = demo_shot_detection()

    # 2. 分析节拍
    print("\n[2/4] 分析节拍...")
    beats_data = demo_beat_detection()

    # 3. 评分高光
    print("\n[3/4] 评分高光...")
    scores = demo_highlight_scoring()

    # 4. 卡点同步
    print("\n[4/4] 卡点同步...")
    shots_with_scores = [
        {"shot_id": s["shot_id"], "highlight_score": s["highlight_score"]}
        for s in scores
    ]
    timeline = BeatSyncEngine().sync(shots_with_scores, beats_data["beats"])

    print("\n" + "="*50)
    print("完整工作流程演示完成!")
    print("="*50)
    print(f"\n结果:")
    print(f"  - 检测到 {len(shots)} 个镜头")
    print(f"  - 检测到 {len(beats_data['beats'])} 个节拍")
    print(f"  - 生成 {len(timeline)} 个时间线条目")
    print(f"  - 总时长: {sum(t['duration'] for t in timeline):.1f}s")


def main():
    """主演示函数"""
    print("AI Montage Agent 简单演示")
    print("="*50)

    demo_shot_detection()
    demo_beat_detection()
    demo_highlight_scoring()
    demo_beat_sync()
    demo_emotion_curve()
    demo_rhythm_planner()
    demo_full_workflow()

    print("\n" + "="*50)
    print("所有演示完成!")
    print("="*50)
    print("\n项目已成功创建在: D:/AI-Montage-Agent")
    print("\n下一步:")
    print("  1. 安装依赖: pip install -e .")
    print("  2. 运行演示: python examples/simple_demo.py")
    print("  3. 查看文档: docs/architecture.md")


if __name__ == "__main__":
    main()
