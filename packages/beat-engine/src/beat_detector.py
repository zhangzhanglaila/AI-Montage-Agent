"""
Beat Detection Module
节拍检测模块 - 使用librosa进行BGM节拍分析
"""

import numpy as np
import librosa
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class Beat:
    """节拍数据结构"""
    time: float
    strength: float
    beat_type: str  # "normal", "strong", "weak"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "time": self.time,
            "strength": self.strength,
            "type": self.beat_type
        }

@dataclass
class MusicSegment:
    """音乐片段"""
    start: float
    end: float
    segment_type: str  # "intro", "verse", "chorus", "bridge", "climax", "outro"
    energy: float
    tempo: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "start": self.start,
            "end": self.end,
            "type": self.segment_type,
            "energy": self.energy,
            "tempo": self.tempo
        }

class BeatDetector:
    """
    节拍检测器
    使用librosa进行BGM节拍分析
    """

    def __init__(self, sr: int = 22050, hop_length: int = 512):
        self.sr = sr
        self.hop_length = hop_length

    def analyze(self, audio_path: str) -> Dict[str, Any]:
        """
        分析音频文件

        Args:
            audio_path: 音频文件路径

        Returns:
            分析结果，包含节拍、BPM、结构等信息
        """
        audio_path = Path(audio_path)
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio not found: {audio_path}")

        # 加载音频
        y, sr = librosa.load(str(audio_path), sr=self.sr)

        # 检测节拍
        beats = self._detect_beats(y, sr)

        # 计算BPM
        tempo = self._estimate_tempo(y, sr)

        # 检测能量变化
        energy = self._compute_energy(y, sr)

        # 检测音乐结构
        segments = self._detect_segments(y, sr)

        # 检测高潮部分
        climax_segments = self._detect_climax(y, sr, energy)

        return {
            "beats": [b.to_dict() for b in beats],
            "tempo": tempo,
            "energy": energy,
            "segments": [s.to_dict() for s in segments],
            "climax": climax_segments,
            "duration": len(y) / sr
        }

    def _detect_beats(self, y: np.ndarray, sr: int) -> List[Beat]:
        """检测节拍"""

        # 使用librosa检测节拍
        tempo, beat_frames = librosa.beat.beat_track(
            y=y, sr=sr, hop_length=self.hop_length
        )

        # 转换为时间
        beat_times = librosa.frames_to_time(
            beat_frames, sr=sr, hop_length=self.hop_length
        )

        # 计算每个节拍的强度
        onset_env = librosa.onset.onset_strength(
            y=y, sr=sr, hop_length=self.hop_length
        )

        beats = []
        for i, time in enumerate(beat_times):
            # 获取该时间点的强度
            frame = librosa.time_to_frames(
                time, sr=sr, hop_length=self.hop_length
            )
            if frame < len(onset_env):
                strength = float(onset_env[frame])
            else:
                strength = 0.0

            # 判断节拍类型
            if strength > np.mean(onset_env) + np.std(onset_env):
                beat_type = "strong"
            elif strength < np.mean(onset_env) - np.std(onset_env):
                beat_type = "weak"
            else:
                beat_type = "normal"

            beats.append(Beat(
                time=float(time),
                strength=strength,
                beat_type=beat_type
            ))

        return beats

    def _estimate_tempo(self, y: np.ndarray, sr: int) -> float:
        """估算BPM"""

        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        return float(tempo)

    def _compute_energy(self, y: np.ndarray, sr: int) -> List[Dict[str, Any]]:
        """计算能量变化曲线"""

        # 计算RMS能量
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]

        # 转换为时间序列
        times = librosa.frames_to_time(
            np.arange(len(rms)), sr=sr, hop_length=self.hop_length
        )

        # 归一化
        rms_normalized = (rms - rms.min()) / (rms.max() - rms.min() + 1e-8)

        return [
            {"time": float(t), "energy": float(e)}
            for t, e in zip(times, rms_normalized)
        ]

    def _detect_segments(self, y: np.ndarray, sr: int) -> List[MusicSegment]:
        """检测音乐结构段落"""

        # 使用频谱特征检测结构变化
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)

        # 使用自相似矩阵检测段落边界
        bound_frames = librosa.segment.agglomerative(chroma, k=6)
        bound_times = librosa.frames_to_time(
            bound_frames, sr=sr, hop_length=self.hop_length
        )

        # 计算每个段落的能量
        rms = librosa.feature.rms(y=y, hop_length=self.hop_length)[0]
        times = librosa.frames_to_time(
            np.arange(len(rms)), sr=sr, hop_length=self.hop_length
        )

        segments = []
        for i in range(len(bound_times) - 1):
            start = bound_times[i]
            end = bound_times[i + 1]

            # 计算该段落的平均能量
            mask = (times >= start) & (times < end)
            if mask.any():
                energy = float(np.mean(rms[mask]))
            else:
                energy = 0.0

            # 估算该段落的节奏
            segment_y = y[int(start * sr):int(end * sr)]
            if len(segment_y) > 0:
                tempo, _ = librosa.beat.beat_track(y=segment_y, sr=sr)
                tempo = float(tempo)
            else:
                tempo = 0.0

            # 根据能量和位置判断段落类型
            segment_type = self._classify_segment(
                i, len(bound_times), energy, tempo
            )

            segments.append(MusicSegment(
                start=float(start),
                end=float(end),
                segment_type=segment_type,
                energy=energy,
                tempo=tempo
            ))

        return segments

    def _classify_segment(
        self,
        index: int,
        total: int,
        energy: float,
        tempo: float
    ) -> str:
        """根据位置和能量分类段落"""

        position = index / total

        if position < 0.1:
            return "intro"
        elif position > 0.9:
            return "outro"
        elif energy > 0.7:
            return "chorus"
        elif energy < 0.3:
            return "verse"
        else:
            return "bridge"

    def _detect_climax(
        self,
        y: np.ndarray,
        sr: int,
        energy: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """检测高潮部分"""

        # 提取能量值
        energies = [e["energy"] for e in energy]
        times = [e["time"] for e in energy]

        # 计算能量阈值（前20%的高能量区域）
        threshold = np.percentile(energies, 80)

        # 找到连续的高能量区域
        climax_segments = []
        in_climax = False
        start_time = 0

        for i, (t, e) in enumerate(zip(times, energies)):
            if e > threshold and not in_climax:
                in_climax = True
                start_time = t
            elif e <= threshold and in_climax:
                in_climax = False
                if t - start_time > 1.0:  # 至少1秒
                    climax_segments.append({
                        "start": start_time,
                        "end": t,
                        "type": "climax",
                        "energy": float(np.mean([
                            ej["energy"] for ej in energy
                            if ej["time"] >= start_time and ej["time"] <= t
                        ]))
                    })

        # 处理最后一个高潮段
        if in_climax and times[-1] - start_time > 1.0:
            climax_segments.append({
                "start": start_time,
                "end": times[-1],
                "type": "climax",
                "energy": float(np.mean([
                    ej["energy"] for ej in energy
                    if ej["time"] >= start_time
                ]))
            })

        return climax_segments

    def get_beat_times(self, audio_path: str) -> List[float]:
        """获取所有节拍时间点（简化接口）"""

        result = self.analyze(audio_path)
        return [b["time"] for b in result["beats"]]

    def get_strong_beats(self, audio_path: str) -> List[float]:
        """获取强拍时间点"""

        result = self.analyze(audio_path)
        return [b["time"] for b in result["beats"] if b["type"] == "strong"]
