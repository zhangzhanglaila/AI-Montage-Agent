# AI Montage Agent

AI自动影视混剪Agent - 输入视频+BGM，自动生成混剪

## 现在能做什么

**输入：**
- 多个电影视频文件（mp4/mkv/mov）
- 一首 BGM

**输出：**
- 自动切镜头
- 自动检测 BGM 节拍
- 自动评分高光镜头
- 自动卡点拼接
- 输出一个混剪视频

## 快速开始

### 1. 环境要求

- Python 3.10+
- FFmpeg（必须）

### 2. 安装 FFmpeg

**Windows：**
```bash
# 方法1: scoop
scoop install ffmpeg

# 方法2: choco
choco install ffmpeg

# 方法3: 下载 https://ffmpeg.org/download.html 添加到 PATH
```

**Mac：**
```bash
brew install ffmpeg
```

**Linux：**
```bash
sudo apt install ffmpeg
```

### 3. 安装 Python 依赖

```bash
cd ai-montage-agent
pip install -r requirements.txt
```

### 4. 生成混剪

**方式一：本地视频文件**

```bash
python pipeline.py \
  --movies movie1.mp4 movie2.mp4 movie3.mp4 \
  --bgm bgm.mp3 \
  --style dynamic \
  --output my_montage.mp4
```

**方式二：Remix 别人的混剪（拆镜头 → 重排 → 新 BGM）**

把别人的混剪视频当输入，自动切镜头、重新评分、用新 BGM 重新卡点：

```bash
python pipeline.py \
  --movies someone_montage.mp4 \
  --bgm new_bgm.mp3 \
  --style intense \
  --output my_remix.mp4
```

流程：`别人的混剪 → ShotDetector 切镜头 → 逐镜头分析 → 新 BGM 卡点 → 输出新混剪`

**方式三：关键词自动搜索下载素材**

```bash
# Pexels 素材（无版权，需免费 API Key）
export PEXELS_API_KEY=your_key_here
python pipeline.py \
  --query "avengers fight" \
  --source pexels \
  --bgm bgm.mp3 \
  --style intense \
  --output my_montage.mp4

# Pixabay 素材（无版权，需免费 API Key）
export PIXABAY_API_KEY=your_key_here
python pipeline.py \
  --query "explosion action" \
  --source pixabay \
  --bgm bgm.mp3 \
  --style intense \
  --output my_montage.mp4

# B站素材（无需 Key，但内容为二创）
python pipeline.py \
  --query "漫威混剪" \
  --source bilibili \
  --bgm bgm.mp3 \
  --style intense \
  --output my_montage.mp4
```

**素材来源说明：**

| 来源 | 类型 | API Key | 说明 |
|------|------|---------|------|
| `pexels` | 原始素材 | 免费注册 | 无版权高清视频，适合混剪 |
| `pixabay` | 原始素材 | 免费注册 | 无版权高清视频 |
| `bilibili` | 二创内容 | 不需要 | B站视频，注意版权 |

**免费 API Key 注册：**
- Pexels: https://www.pexels.com/api/ （200请求/小时）
- Pixabay: https://pixabay.com/api/docs/ （5000请求/天）

参数说明：
- `--movies`：本地视频文件路径，可以多个
- `--query`：搜索关键词，自动下载素材（与 --movies 二选一）
- `--source`：素材来源（pexels / pixabay / bilibili，默认 bilibili）
- `--clip-limit`：最大下载片段数，默认 20（仅 --query 模式）
- `--bgm`：BGM 音频文件
- `--style`：风格（dynamic/calm/intense）
- `--output`：输出文件名

## 测试

```bash
# 生成测试视频并验证 pipeline
python test_pipeline.py
```

## 项目结构

```
ai-montage-agent/
├── pipeline.py              # 核心 Pipeline（端到端流程）
├── test_pipeline.py         # 测试脚本
├── requirements.txt         # Python 依赖
├── packages/
│   ├── core_types/          # 统一数据类型
│   ├── video_understanding/ # 视频理解
│   ├── video_crawler/       # 素材爬取（Pexels/Pixabay/B站）
│   ├── beat_engine/         # 节拍引擎
│   ├── montage_engine/      # 蒙太奇引擎
│   ├── timeline_engine/     # 时间轴引擎
│   └── render_engine/       # 渲染引擎
├── cache/                   # 缓存（镜头、关键帧）
└── output/                  # 输出文件
```

## 技术栈

- **视频处理**: FFmpeg, PySceneDetect, OpenCV
- **音频分析**: librosa
- **渲染**: FFmpeg

## 当前限制

1. **高光评分**：基于运动幅度的规则评分，不够智能
2. **没有AI理解**：不知道哪个镜头"帅"
3. **没有字幕**：需要手动加字幕
4. **没有高级转场**：只有硬切

## 下一步计划

- [ ] 接入 CLIP 做镜头语义理解
- [ ] 接入 Whisper 做自动字幕
- [ ] 接入 LLM 做 AI 导演
- [ ] 更多转场效果

## 许可证

MIT License
