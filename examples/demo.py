"""
AI Montage Agent 演示脚本
展示如何使用各个模块
"""

import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "packages"))
sys.path.insert(0, str(project_root))

from packages.video-understanding.src.shot_detector import ShotDetector, Shot
from packages.beat-engine.src.beat_detector import BeatDetector
from packages.beat-engine.src.beat_sync_engine import BeatSyncEngine
from packages.video-understanding.src.highlight_scorer import HighlightScorer
from packages.timeline-engine.src.timeline_planner import TimelinePlanner
from packages.timeline-engine.src.emotion_curve import EmotionCurve
from packages.timeline-engine.src.rhythm_planner import RhythmPlanner


def demo_shot_detection():
    """演示镜头检测"""
    print("\n" + "="*50)
    print("演示: 镜头检测")
    print("="*50)

    # 创建模拟镜头数据
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

    # 创建模拟节拍数据
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
    for beat in beats[:5]:  # 只显示前5个
        print(f"  - {beat['time']:.1f}s: {beat['type']} (强度: {beat['strength']:.2f})")

    return {"beats": beats, "tempo": 120.0}


def demo_highlight_scoring():
    """演示高光评分"""
    print("\n" + "="*50)
    print("演示: 高光评分")
    print("="*50)

    scorer = HighlightScorer()

    # 模拟镜头数据
    shots_data = [
        {
            "shot_id": 0,
            "motion": {"magnitude": 3.0},
            "face": {"emotions": [{"type": "neutral", "confidence": 0.8}]},
            "camera": {"shake": 0.2, "zoom": 0.1, "pan_speed": 0.1}
        },
        {
            "shot_id": 1,
            "motion": {"magnitude": 8.0},
            "face": {"emotions": [{"type": "angry", "confidence": 0.9}]},
            "camera": {"shake": 0.8, "zoom": 0.5, "pan_speed": 0.7}
        },
        {
            "shot_id": 2,
            "motion": {"magnitude": 5.0},
            "face": {"emotions": [{"type": "sad", "confidence": 0.7}]},
            "camera": {"shake": 0.3, "zoom": 0.2, "pan_speed": 0.2}
        },
        {
            "shot_id": 3,
            "motion": {"magnitude": 9.0},
            "face": {"emotions": [{"type": "surprise", "confidence": 0.95}]},
            "camera": {"shake": 0.9, "zoom": 0.8, "pan_speed": 0.9}
        },
    ]

    scores = scorer.score_shots(shots_data)
    scores = scorer.normalize_scores(scores)

    print("高光评分结果:")
    for score in scores:
        print(f"  - 镜头 {score.shot_id}: {score.overall_score:.2f}")

    # 获取高光镜头
    highlights = scorer.get_highlight_shots(scores, top_k=2)
    print(f"\nTop 2 高光镜头: {[s.shot_id for s in highlights]}")

    return scores


def demo_beat_sync():
    """演示卡点同步"""
    print("\n" + "="*50)
    print("演示: 卡点同步")
    print("="*50)

    engine = BeatSyncEngine()

    # 模拟数据
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
        print(f"  - 镜头 {entry.shot_id}: {entry.start_time:.2f}s - {entry.end_time:.2f}s")

    return timeline


def demo_emotion_curve():
    """演示情绪曲线"""
    print("\n" + "="*50)
    print("演示: 情绪曲线")
    print("="*50)

    curve = EmotionCurve()

    # 生成不同风格的情绪曲线
    styles = ["dynamic", "calm", "intense", "emotional"]

    for style in styles:
        points = curve.generate(10.0, style)
        print(f"\n{style} 风格:")
        print(f"  - 生成 {len(points)} 个情绪点")

        # 显示几个关键点
        for i in range(0, len(points), len(points)//5):
            p = points[i]
            print(f"    {p.time:.1f}s: {p.emotion} (强度: {p.intensity:.2f})")


def demo_timeline_planner():
    """演示时间轴规划"""
    print("\n" + "="*50)
    print("演示: 时间轴规划")
    print("="*50)

    planner = TimelinePlanner()

    # 模拟镜头数据
    shots = [
        {"shot_id": 0, "actions": ["walking"], "highlight_score": 0.6},
        {"shot_id": 1, "actions": ["fighting", "explosion"], "highlight_score": 0.9},
        {"shot_id": 2, "actions": ["crying"], "highlight_score": 0.7},
        {"shot_id": 3, "actions": ["running"], "highlight_score": 0.85},
        {"shot_id": 4, "actions": ["explosion", "fighting"], "highlight_score": 0.95},
    ]

    result = planner.plan(shots, style="dynamic")

    print(f"规划结果:")
    print(f"  - 镜头数量: {len(result['shots'])}")
    print(f"  - 风格: {result['style']}")
    print(f"  - 情绪点数: {len(result['emotion_curve'])}")
    print(f"  - 节奏点数: {len(result['rhythm_curve'])}")


def main():
    """主演示函数"""
    print("AI Montage Agent 演示")
    print("="*50)

    # 运行各个演示
    demo_shot_detection()
    demo_beat_detection()
    demo_highlight_scoring()
    demo_beat_sync()
    demo_emotion_curve()
    demo_timeline_planner()

    print("\n" + "="*50)
    print("演示完成!")
    print("="*50)


if __name__ == "__main__":
    main()
