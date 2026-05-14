# AI Montage Agent

AI自动影视混剪Agent - 自动生成B站级影视混剪

## 功能特性

- 自动镜头检测
- BGM节拍分析
- 高光片段识别
- 智能卡点同步
- 情绪曲线规划
- 自动转场效果
- 一键生成混剪

## 项目结构

```
ai-montage-agent/
├── apps/
│   ├── api/           # FastAPI后端
│   ├── web/           # Next.js前端
│   └── worker/        # CLI工具和任务队列
├── packages/
│   ├── video-understanding/  # 视频理解模块
│   ├── beat-engine/          # 节拍引擎
│   ├── montage-engine/       # 蒙太奇引擎
│   ├── timeline-engine/      # 时间轴引擎
│   └── render-engine/        # 渲染引擎
└── docs/              # 文档
```

## 快速开始

### 安装

```bash
# 克隆项目
git clone https://github.com/yourusername/ai-montage-agent.git
cd ai-montage-agent

# 安装依赖
pip install -e .
```

### 使用CLI

```bash
# 检测镜头
ai-montage detect-shots movie.mp4

# 分析BGM
ai-montage analyze-beats bgm.mp3

# 完整混剪流程
ai-montage full-pipeline movie1.mp4 movie2.mp4 --bgm bgm.mp3 --style dynamic
```

### 使用API

```bash
# 启动API服务
uvicorn apps.api.src.main:app --reload

# 访问API文档
open http://localhost:8000/docs
```

## 技术栈

- **后端**: FastAPI, Celery, Redis
- **AI**: PySceneDetect, librosa, CLIP
- **渲染**: FFmpeg
- **前端**: Next.js (开发中)

## 开发路线图

### P0 - 最小可运行版本
- [x] 项目初始化
- [x] 镜头检测
- [x] 音频分析
- [x] 高光评分
- [x] 卡点同步
- [x] 时间轴规划
- [x] 视频合成

### P1 - 像导演一样
- [ ] 镜头语义图谱
- [ ] AI导演Agent
- [ ] 音乐驱动剪辑
- [ ] 动作连续性

### P2 - 可能爆火
- [ ] 风格学习
- [ ] 多模态导演模型
- [ ] 自动生成神级高潮

## 贡献

欢迎贡献！请阅读 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

## 许可证

MIT License
