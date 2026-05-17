# AI Montage Agent

AI自动影视混剪Agent - 输入视频+BGM，自动生成混剪

## 功能特性

| 功能 | 说明 | 状态 |
|------|------|------|
| 镜头检测 | FFmpeg scene detect，自动切镜头 | ✅ |
| BGM节拍分析 | librosa 检测节拍/能量/高潮段 | ✅ |
| 高光评分 | 5维评分（运动/镜头多样性/表情/运镜/音频） | ✅ |
| 卡点同步 | 镜头与节拍对齐，强弱拍分级 | ✅ |
| 素材搜索 | B站/YouTube/台词搜索等自动下载 | ✅ |
| 风格模板 | 11种预设风格（Vlog/纪录片/婚礼/游戏等） | ✅ |
| 视频增强 | 防抖/降噪/调色 | ✅ |
| 自动裁剪 | 智能跟踪主体，横屏转竖屏 | ✅ |
| 对白闪避 | BGM自动避让人声 | ✅ |
| 色彩和谐 | 多片段亮度统一 | ✅ |
| 字幕生成 | Whisper 语音转字幕，6种风格 | ✅ |
| LLM控制 | 自然语言描述→剪辑指令 | ✅ |
| 时间轴导出 | EDL/CSV/JSON/XML/OTIO | ✅ |
| 丰富转场 | dissolve/zoom/shake/wipe 等10+种 | ✅ |
| WebUI | FastAPI + B站漫画风格前端 | ✅ |

## 快速开始

### 1. 环境要求

- Python 3.10+
- FFmpeg（必须）

### 2. 安装

```bash
# 安装 FFmpeg
# Windows: scoop install ffmpeg / choco install ffmpeg
# Mac: brew install ffmpeg
# Linux: sudo apt install ffmpeg

# 安装 Python 依赖
pip install -r requirements.txt
```

### 3. 基础用法

**本地视频文件：**
```bash
python pipeline.py \
  --movies movie1.mp4 movie2.mp4 \
  --bgm bgm.mp3 \
  --style dynamic \
  --output my_montage.mp4
```

**关键词搜索素材（推荐 PlayPhrase，电影原片无水印）：**
```bash
python pipeline.py \
  --query "i love you" \
  --bgm bgm.mp3 \
  --style dynamic \
  --output my_montage.mp4
```

**B站素材（可能有作者水印）：**
```bash
python pipeline.py \
  --query "漫威混剪" \
  --source bilibili \
  --bgm bgm.mp3 \
  --style intense \
  --output my_montage.mp4
```

**Remix 别人的混剪：**
```bash
python pipeline.py \
  --movies someone_montage.mp4 \
  --bgm new_bgm.mp3 \
  --style intense \
  --output my_remix.mp4
```

### 4. 高级功能

**LLM 自然语言控制：**
```bash
python pipeline.py \
  --movies video.mp4 \
  --bgm bgm.mp3 \
  --prompt "做一个30秒的漫威高燃混剪，橙青调色，快节奏"
```

**视频增强（防抖+降噪+调色）：**
```bash
python pipeline.py \
  --movies video.mp4 \
  --bgm bgm.mp3 \
  --enhance stabilize denoise color-grade
```

**字幕压制：**
```bash
python pipeline.py \
  --movies video.mp4 \
  --bgm bgm.mp3 \
  --subtitles tiktok
```

**导出时间轴（导入PR/DaVinci）：**
```bash
python pipeline.py \
  --movies video.mp4 \
  --bgm bgm.mp3 \
  --export-timeline edl

# OTIO格式（DaVinci Resolve / Premiere Pro / FCP）
python pipeline.py \
  --movies video.mp4 \
  --bgm bgm.mp3 \
  --export-timeline otio
```

**使用风格预设：**
```bash
python pipeline.py \
  --movies video.mp4 \
  --bgm bgm.mp3 \
  --style-preset vlog

# 可用预设：action, vlog, documentary, wedding, gaming, mtv, sport, travel, cinematic, viral, lofi
```

**BGM关键词搜索（自动下载BGM）：**
```bash
python pipeline.py \
  --movies video.mp4 \
  --bgm-query "高燃 BGM" \
  --style dynamic
```

**自动裁剪（横屏转竖屏）：**
```bash
python pipeline.py \
  --movies video.mp4 \
  --bgm bgm.mp3 \
  --enhance auto-reframe
```

**启动 WebUI：**
```bash
python pipeline.py --webui
# 浏览器打开 http://localhost:8000
```

### 5. 素材来源

| 来源 | 类型 | 说明 |
|------|------|------|
| `playphrase` | 电影原片（推荐） | 3900万+英文台词片段，无水印，需 Playwright |
| `quodb` | 电影台词库 | 提供台词+电影+时间码，需配合其他源下载视频 |
| `bilibili` | 影视/二创 | B站视频，可能有作者水印 |
| `youtube` | 全品类 | 需要能访问 YouTube + 登录 cookies |
| `dailymotion` | 全品类 | 国际视频平台 |
| `douyin` | 短视频 | 抖音视频 |
| `ixigua` | 影视/综艺 | 西瓜视频 |
| `acfun` | 动漫/二创 | AcFun 弹幕视频 |
| `vimeo` | 创意短片 | 高质量创意视频 |
| `yarn` | 台词搜索 | 英文台词搜片段（Cloudflare 封锁，暂不可用） |
| `zhaotaici` | 台词搜索 | 中文台词搜片段（SSL 错误，暂不可用） |
| `zhaotaici` | 台词搜索 | 不需要 | 中文台词搜片段（需 Playwright） |

**台词搜索源说明：**
- YARN/PlayPhrase/QuoDB/找台词网 需要安装 Playwright：
  ```bash
  pip install playwright
  # 使用系统已安装的 Chrome 浏览器，无需额外下载 Chromium
  ```
- 这些站点有 Cloudflare 反爬保护，必须用浏览器自动化

## 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--movies` | 本地视频文件路径（可多个） | - |
| `--query` | 搜索关键词（与 --movies 二选一） | - |
| `--source` | 素材来源 | playphrase |
| `--clip-limit` | 最大下载数 | 20 |
| `--bgm` | BGM 文件路径 | - |
| `--bgm-query` | BGM搜索关键词（与 --bgm 二选一） | - |
| `--style` | 风格 (dynamic/calm/intense) | dynamic |
| `--style-preset` | 风格预设（覆盖 --style） | - |
| `--output` | 输出文件名 | final.mp4 |
| `--threshold` | 镜头检测灵敏度 (0.01~1.0) | 0.2 |
| `--prompt` | 自然语言描述 | - |
| `--subtitles` | 字幕风格 (none/tiktok/youtube/minimal/cinematic) | none |
| `--enhance` | 视频增强 (stabilize/denoise/color-grade/auto-reframe) | - |
| `--export-timeline` | 导出时间轴 (edl/csv/json/xml/otio) | - |
| `--webui` | 启动 WebUI | - |

**风格预设列表：**

| 预设 | 名称 | 适用场景 |
|------|------|----------|
| `action` | 动作片 | 快节奏、高强度 |
| `vlog` | Vlog | 日常记录、轻松氛围 |
| `documentary` | 纪录片 | 沉稳、专业 |
| `wedding` | 婚礼 | 浪漫、温馨 |
| `gaming` | 游戏 | 高能、炫酷 |
| `mtv` | MTV | 音乐视频、节奏感 |
| `sport` | 体育 | 动感、激情 |
| `travel` | 旅行 | 治愈、清新 |
| `cinematic` | 电影感 | 大片质感 |
| `viral` | 爆款 | 短视频、吸睛 |
| `lofi` | Lo-fi | 复古、文艺 |

## 项目结构

```
ai-montage-agent/
├── pipeline.py              # 核心 Pipeline + CLI
├── requirements.txt         # Python 依赖
├── packages/
│   ├── core_types/          # 统一数据类型
│   ├── video_crawler/       # 素材爬取（B站/YouTube/台词搜索/BGM搜索）
│   ├── video_enhancement/   # 视频增强
│   │   ├── src/
│   │   │   ├── stabilizer.py        # 视频防抖
│   │   │   ├── enhancer.py          # 降噪/锐化/胶片颗粒
│   │   │   ├── color_grading.py     # 调色预设
│   │   │   ├── style_templates.py   # 风格模板系统
│   │   │   ├── auto_reframe.py      # 自动裁剪（横屏转竖屏）
│   │   │   ├── dialogue_ducking.py  # 对白闪避
│   │   │   ├── color_harmonizer.py  # 色彩和谐
│   │   │   └── styles/              # 11种风格JSON预设
│   │   └── __init__.py
│   ├── subtitle_engine/     # 字幕引擎（Whisper转录+压制）
│   ├── ai_director/         # LLM自然语言控制
│   ├── timeline_export/     # 时间轴导出
│   │   ├── src/
│   │   │   ├── exporter.py          # EDL/CSV/JSON/XML
│   │   │   └── otio_exporter.py     # OTIO格式（DaVinci/PR/FCP）
│   │   └── __init__.py
│   ├── webui/               # WebUI（FastAPI + B站漫画风格前端）
│   ├── beat_engine/         # 节拍引擎
│   ├── montage_engine/      # 蒙太奇引擎（10+种转场）
│   └── render_engine/       # 渲染引擎
├── cache/                   # 缓存
└── output/                  # 输出文件
```

## 技术栈

- **视频处理**: FFmpeg, OpenCV
- **音频分析**: librosa
- **字幕**: openai-whisper / faster-whisper
- **LLM**: OpenAI 兼容 API（支持 Ollama 本地部署）
- **WebUI**: FastAPI + SSE
- **素材爬取**: yt-dlp + B站 API + Playwright（台词搜索）

## 许可证

MIT License
