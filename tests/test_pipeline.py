"""
测试 Pipeline
生成测试视频，验证完整流程
"""

import subprocess
import os
import sys
from pathlib import Path

# 添加项目根目录到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))


def create_test_video(output_path: str, duration: float = 5.0, color: str = "blue"):
    """创建测试视频"""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:s=640x360:d={duration}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)
    print(f"  创建测试视频: {output_path}")


def create_test_audio(output_path: str, duration: float = 10.0):
    """创建测试音频"""
    # 先生成 wav，再转 mp3
    wav_path = output_path.replace(".mp3", ".wav")
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        wav_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    # 转换为 mp3
    cmd = [
        "ffmpeg", "-y",
        "-i", wav_path,
        "-c:a", "libmp3lame",
        "-b:a", "128k",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    # 删除临时 wav
    if os.path.exists(wav_path):
        os.remove(wav_path)

    print(f"  创建测试音频: {output_path}")


def test_pipeline():
    """测试完整 pipeline"""
    print("=" * 50)
    print("测试 Pipeline")
    print("=" * 50)

    # 创建测试目录
    test_dir = Path("test_assets")
    test_dir.mkdir(exist_ok=True)

    # 创建测试视频
    print("\n[1/3] 创建测试视频...")
    videos = []
    for i, color in enumerate(["red", "blue", "green"]):
        path = test_dir / f"test_{i}.mp4"
        create_test_video(str(path), duration=3.0 + i, color=color)
        videos.append(str(path))

    # 创建测试音频
    print("\n[2/3] 创建测试音频...")
    bgm_path = test_dir / "test_bgm.mp3"
    create_test_audio(str(bgm_path), duration=15.0)

    # 运行 pipeline
    print("\n[3/3] 运行 Pipeline...")
    from pipeline import MontagePipeline

    pipeline = MontagePipeline()
    result = pipeline.run(
        video_paths=videos,
        bgm_path=str(bgm_path),
        style="dynamic",
        output_name="test_output.mp4"
    )

    # 验证输出
    if Path(result).exists():
        size = Path(result).stat().st_size
        print(f"\n[OK] 测试成功!")
        print(f"  输出文件: {result}")
        print(f"  文件大小: {size / 1024:.1f} KB")
    else:
        print(f"\n[FAIL] 测试失败: 输出文件不存在")


if __name__ == "__main__":
    test_pipeline()
