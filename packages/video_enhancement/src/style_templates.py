"""
风格模板系统 - JSON 预设 + 加载器

内置 11 种风格模板，支持用户自定义扩展。
"""

import json
from pathlib import Path
from functools import lru_cache
from typing import Dict, List, Optional

STYLES_DIR = Path(__file__).parent / "styles"

# Pipeline 参数映射：风格模板 -> pipeline 可用的参数
STYLE_TO_PIPELINE = {
    "action":      {"style": "intense",  "color_preset": "vibrant",     "stabilize": False},
    "vlog":        {"style": "dynamic",  "color_preset": "vibrant",     "stabilize": True},
    "documentary": {"style": "calm",     "color_preset": "neutral",     "stabilize": True},
    "wedding":     {"style": "calm",     "color_preset": "filmic_warm", "stabilize": True},
    "gaming":      {"style": "intense",  "color_preset": "high_contrast","stabilize": False},
    "mtv":         {"style": "intense",  "color_preset": "vibrant",     "stabilize": False},
    "sport":       {"style": "intense",  "color_preset": "high_contrast","stabilize": False},
    "travel":      {"style": "calm",     "color_preset": "golden_hour", "stabilize": True},
    "cinematic":   {"style": "dynamic",  "color_preset": "cinematic",   "stabilize": True},
    "viral":       {"style": "intense",  "color_preset": "vibrant",     "stabilize": False},
    "lofi":        {"style": "calm",     "color_preset": "vintage",     "stabilize": True},
}


def _load_templates_from_dir(styles_dir: Path) -> Dict[str, dict]:
    """从目录加载所有 JSON 模板"""
    templates = {}
    if not styles_dir.exists():
        return templates
    for f in sorted(styles_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "id" in data:
                templates[data["id"].lower()] = data
        except (json.JSONDecodeError, KeyError):
            continue
    return templates


@lru_cache(maxsize=1)
def load_style_templates() -> Dict[str, dict]:
    """加载所有风格模板（内置 + 用户自定义）"""
    templates = _load_templates_from_dir(STYLES_DIR)
    return templates


def get_style_template(style_name: str) -> dict:
    """获取指定风格模板"""
    templates = load_style_templates()
    key = style_name.lower()
    if key not in templates:
        available = ", ".join(sorted(templates.keys()))
        raise KeyError(f"未知风格: {style_name}，可用: {available}")
    return templates[key]


def get_pipeline_params(style_name: str) -> dict:
    """获取风格对应的 pipeline 参数"""
    key = style_name.lower()
    if key in STYLE_TO_PIPELINE:
        return STYLE_TO_PIPELINE[key].copy()
    # 默认使用 dynamic
    return {"style": "dynamic", "color_preset": "cinematic", "stabilize": False}


def list_available_styles() -> List[str]:
    """列出所有可用风格"""
    return sorted(load_style_templates().keys())


def get_style_names() -> List[dict]:
    """获取风格列表（含 id/name/description）"""
    templates = load_style_templates()
    return [
        {"id": t["id"], "name": t.get("name", t["id"]), "description": t.get("description", "")}
        for t in templates.values()
    ]
