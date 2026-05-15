"""
LLM 自然语言控制模块 - 将自然语言描述转为剪辑指令

支持 OpenAI 兼容 API（含 Ollama 本地部署）。
用户输入自然语言 → LLM 解析 → 结构化 JSON 剪辑参数
"""

import json
import os
import re
import time
from typing import Dict, Any, Optional, List


# 风格关键词检测
STYLE_KEYWORDS = {
    "hitchcock": ["hitchcock", "悬疑", "惊悚", "紧张", "thriller", "suspense", "tension"],
    "action": ["action", "动作", "爆炸", "高速", "blockbuster", "explosive", "adrenaline", "高燃"],
    "mtv": ["mtv", "音乐视频", "快节奏", "fast-paced", "energetic", "rapid"],
    "documentary": ["documentary", "纪录片", "真实", "realism", "natural", "观察"],
    "minimalist": ["minimalist", "艺术", "冥想", "平静", "contemplative", "长镜头", "慢节奏"],
    "wes_anderson": ["wes anderson", "对称", "symmetry", "pastel", "quirky", "复古文艺"],
}

MOOD_TO_STYLE = {
    "cinematic": "hitchcock",
    "电影感": "hitchcock",
    "史诗": "hitchcock",
    "专业": "documentary",
    "流畅": "documentary",
    "画廊": "minimalist",
    "唯美": "wes_anderson",
    "艺术": "minimalist",
}

# 调色检测
COLOR_GRADING_KEYWORDS = {
    "teal_orange": ["teal and orange", "好莱坞", "hollywood", "blockbuster", "cinematic look", "橙青"],
    "warm": ["warm", "暖色", "golden", "sunset", "sunrise", "cozy", "autumn", "秋天"],
    "cool": ["cool", "冷色", "blue", "cold", "winter", "icy", "夜晚"],
    "vintage": ["vintage", "复古", "retro", "old film", "classic", "怀旧"],
    "noir": ["noir", "黑白", "black and white", "monochrome", "film noir", "侦探"],
    "vibrant": ["vibrant", "鲜艳", "saturated", "colorful", "pop", "vivid"],
    "desaturated": ["desaturated", "低饱和", "muted", "faded", "matte"],
    "golden_hour": ["golden hour", "magic hour", "黄金时刻", "sunset glow"],
    "blue_hour": ["blue hour", "twilight", "dusk", "蓝色时刻"],
    "high_contrast": ["high contrast", "高对比", "dramatic", "punchy", "bold"],
    "natural": ["natural", "自然", "true to life", "authentic", "realistic"],
}

MOOD_TO_COLOR_GRADING = {
    "cinematic": "teal_orange",
    "dramatic": "high_contrast",
    "warm": "warm",
    "cool": "cool",
    "vintage": "vintage",
    "professional": "natural",
    "artistic": "vibrant",
    "documentary": "documentary",
    "minimalist": "desaturated",
    "beautiful": "golden_hour",
}


DIRECTOR_SYSTEM_PROMPT = """你是一个专业的 AI 视频剪辑导演。你的任务是将用户的自然语言描述转换为结构化的 JSON 剪辑指令。

你必须输出以下格式的 JSON（不要输出其他内容）：
{
  "style": {
    "name": "风格名称(action/documentary/cinematic/minimalist等)",
    "mood": "情绪基调(intense/calm/dramatic/energetic等)"
  },
  "pacing": {
    "speed": "节奏(dynamic/calm/intense)",
    "variation": "变化程度(low/moderate/high)",
    "intro_duration_beats": 8,
    "climax_intensity": 0.8
  },
  "cinematography": {
    "prefer_wide_shots": false,
    "prefer_high_action": false,
    "match_cuts_enabled": true,
    "shot_variation_priority": "medium"
  },
  "transitions": {
    "type": "过渡类型(cut/crossfade/energy_aware)",
    "crossfade_duration_sec": 0.5
  },
  "effects": {
    "color_grading": "调色预设(natural/teal_orange/warm/cool/vintage/noir/vibrant/desaturated/golden_hour/blue_hour/high_contrast/cinematic/blockbuster/documentary)",
    "stabilization": true,
    "sharpness_boost": false
  },
  "constraints": {
    "target_duration_sec": null,
    "min_clip_duration_sec": 1.0,
    "max_clip_duration_sec": 8.0
  }
}

规则：
1. 根据用户的描述选择合适的风格、节奏和调色
2. 如果用户指定了时长，设置 target_duration_sec
3. 动作类视频用 fast pacing + intense mood
4. 纪录片用 moderate pacing + calm mood
5. 只输出 JSON，不要任何解释"""


class CreativeDirector:
    """LLM 自然语言剪辑导演"""

    def __init__(
        self,
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = 30,
    ):
        self.api_base = api_base or os.environ.get("OPENAI_API_BASE", "http://localhost:11434/v1")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "sk-placeholder")
        self.model = model or os.environ.get("LLM_MODEL", "qwen2.5:7b")
        self.timeout = timeout

    def _strip_markdown_json(self, text: str) -> str:
        """移除 markdown 代码块包裹"""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            lines = lines[1:]  # 移除 ```json
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines)
        return text.strip()

    def _repair_json(self, text: str) -> str:
        """修复截断或格式错误的 JSON"""
        text = re.sub(r"//[^\n]*", "", text)
        text = re.sub(r",\s*([}\]])", r"\1", text)

        open_braces = text.count("{") - text.count("}")
        open_brackets = text.count("[") - text.count("]")
        if open_braces > 0 or open_brackets > 0:
            text = text.rstrip(",\n\t ")
            text += "]" * open_brackets + "}" * open_braces
        return text

    def _query_llm(self, prompt: str) -> Optional[str]:
        """调用 OpenAI 兼容 API"""
        try:
            import requests

            url = f"{self.api_base.rstrip('/')}/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            }
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": DIRECTOR_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                "temperature": 0.3,
                "max_tokens": 1024,
            }

            resp = requests.post(url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return self._strip_markdown_json(content)
            return None
        except Exception as e:
            print(f"  LLM 查询失败: {e}")
            return None

    def _parse_response(self, text: str) -> Optional[Dict[str, Any]]:
        """解析 LLM 返回的 JSON"""
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            repaired = self._repair_json(text)
            try:
                return json.loads(repaired)
            except json.JSONDecodeError:
                match = re.search(r"(\{.*\})", text, re.DOTALL)
                if match:
                    try:
                        return json.loads(self._repair_json(match.group(1)))
                    except json.JSONDecodeError:
                        pass
        return None

    def _infer_style_from_prompt(self, prompt: str) -> Optional[str]:
        """启发式风格检测（不依赖 LLM）"""
        lower = prompt.lower()
        for style, keywords in STYLE_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    return style
        for mood, style in MOOD_TO_STYLE.items():
            if mood in lower:
                return style
        return None

    def _detect_color_grading(self, prompt: str) -> str:
        """从自然语言检测调色偏好"""
        lower = prompt.lower()
        for preset, keywords in COLOR_GRADING_KEYWORDS.items():
            for kw in keywords:
                if kw in lower:
                    return preset
        for mood, grading in MOOD_TO_COLOR_GRADING.items():
            if mood in lower:
                return grading
        return "neutral"

    def _infer_style(self, prompt: str) -> str:
        """从 prompt 推断 pacing speed"""
        lower = prompt.lower()
        if any(kw in lower for kw in ["快", "fast", "rapid", "intense", "高燃", "激烈", "动作"]):
            return "intense"
        if any(kw in lower for kw in ["慢", "slow", "calm", "平静", "舒缓", "冥想"]):
            return "calm"
        return "dynamic"

    def get_default_instructions(self, prompt: str = "") -> Dict[str, Any]:
        """默认剪辑指令（LLM 不可用时的降级方案）"""
        color_grading = self._detect_color_grading(prompt) if prompt else "neutral"
        speed = self._infer_style(prompt) if prompt else "dynamic"

        return {
            "style": {"name": "documentary", "mood": "calm"},
            "pacing": {
                "speed": speed,
                "variation": "moderate",
                "intro_duration_beats": 8,
                "climax_intensity": 0.8,
            },
            "cinematography": {
                "prefer_wide_shots": False,
                "prefer_high_action": False,
                "match_cuts_enabled": True,
                "shot_variation_priority": "medium",
            },
            "transitions": {"type": "cut", "crossfade_duration_sec": 0.5},
            "effects": {
                "color_grading": color_grading,
                "stabilization": True,
                "sharpness_boost": False,
            },
            "constraints": {
                "target_duration_sec": None,
                "min_clip_duration_sec": 1.0,
                "max_clip_duration_sec": 8.0,
            },
        }

    def interpret_prompt(self, user_prompt: str) -> Dict[str, Any]:
        """将自然语言转为剪辑指令

        优先用 LLM 解析，失败则用启发式降级。

        Args:
            user_prompt: 如 "做一个30秒的漫威高燃混剪"

        Returns:
            结构化剪辑指令 dict
        """
        print(f"  AI 导演分析: {user_prompt}")

        # 尝试 LLM
        response = self._query_llm(user_prompt)
        if response:
            instructions = self._parse_response(response)
            if instructions:
                print(f"  LLM 解析成功，风格: {instructions.get('style', {}).get('name', 'unknown')}")
                return instructions
            print("  LLM 返回格式错误，使用启发式降级")

        # 启发式降级
        print("  使用启发式规则生成指令")
        return self.get_default_instructions(user_prompt)
