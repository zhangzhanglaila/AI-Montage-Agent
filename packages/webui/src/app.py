"""
WebUI 模块 - FastAPI + HTML 前端

功能：
- 关键词输入 → 选源 → 上传BGM → 选风格/质量/比例 → 提交 → 进度 → 下载
- 支持本地视频上传和在线搜索
- SSE 实时进度推送
"""

import asyncio
import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="AI Montage Agent", version="1.0.0")

# 任务存储
_tasks = {}

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)


def _run_montage_task(task_id: str, video_paths: list, bgm_path: str, bgm_query: str,
                      style: str, output_name: str, query: str, source: str, clip_limit: int,
                      color_preset: str = None, stabilize: bool = False):
    """后台运行完整流程：搜索下载 → pipeline → 后处理"""
    import sys
    import traceback
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from pipeline import MontagePipeline

    task = _tasks[task_id]
    try:
        # ===== 阶段 1：BGM 搜索下载 =====
        if bgm_query:
            task["status"] = "running"
            task["progress"] = 3
            task["message"] = f"正在搜索 BGM: {bgm_query}..."
            from packages.video_crawler.src.bgm_crawler import BgmCrawler
            bgm_crawler = BgmCrawler()
            bgm_paths = bgm_crawler.search_and_download(bgm_query, max_clips=1)
            if not bgm_paths:
                task["status"] = "error"
                task["message"] = f"未找到 BGM「{bgm_query}」，请换个关键词试试"
                return
            bgm_path = bgm_paths[0]
            task["progress"] = 8
            task["message"] = "BGM 下载完成 ✓"
        elif not bgm_path:
            task["status"] = "error"
            task["message"] = "请提供 BGM 文件或搜索关键词"
            return

        # ===== 阶段 2：视频素材搜索下载 =====
        if query:
            task["status"] = "running"
            task["progress"] = 10
            task["message"] = f"正在搜索素材: {query}（来源: {source}）..."

            try:
                if source in ("playphrase", "quodb"):
                    from packages.video_crawler.src.quote_crawler import create_quote_crawler
                    crawler = create_quote_crawler(source)
                    if source == "playphrase":
                        task["message"] = "正在启动浏览器搜索 PlayPhrase...首次可能较慢"
                    else:
                        task["message"] = "正在搜索 QuoDB 台词库..."
                elif source == "bilibili":
                    from packages.video_crawler.src.bilibili_crawler import BilibiliCrawler
                    crawler = BilibiliCrawler()
                    task["message"] = "正在搜索 B站视频..."
                elif source == "youtube":
                    from packages.video_crawler.src.ytdlp_crawler import YtdlpCrawler
                    crawler = YtdlpCrawler("youtube")
                    task["message"] = "正在搜索 YouTube（需要代理）..."
                elif source == "dailymotion":
                    from packages.video_crawler.src.ytdlp_crawler import YtdlpCrawler
                    crawler = YtdlpCrawler("dailymotion")
                    task["message"] = "正在搜索 Dailymotion..."
                else:
                    from packages.video_crawler.src.bilibili_crawler import BilibiliCrawler
                    crawler = BilibiliCrawler()
                    task["message"] = f"正在搜索 {source}..."

                task["progress"] = 12
                video_paths = crawler.search_and_download(query, max_clips=clip_limit)

                if not video_paths:
                    task["status"] = "error"
                    task["message"] = f"搜索「{query}」未找到结果，请检查关键词或换一个来源试试"
                    return

                task["progress"] = 25
                task["message"] = f"素材下载完成，共 {len(video_paths)} 个片段 ✓"

            except Exception as e:
                task["status"] = "error"
                task["message"] = f"素材搜索失败: {str(e)}"
                print(f"[Crawler Error] task={task_id}, source={source}")
                traceback.print_exc()
                return

        if not video_paths:
            task["status"] = "error"
            task["message"] = "没有可用的视频文件，请检查搜索关键词"
            return

        # ===== 阶段 3：AI 混剪 pipeline =====
        task["status"] = "running"
        task["progress"] = 30
        task["message"] = f"正在分析 {len(video_paths)} 个素材，检测镜头与节拍..."

        pipeline = MontagePipeline(cache_dir="cache", output_dir="output")
        result = pipeline.run(video_paths, bgm_path, style, output_name, threshold=0.2)

        # ===== 阶段 4：后处理 =====
        if color_preset and color_preset != "none":
            task["progress"] = 85
            task["message"] = f"正在应用颜色分级: {color_preset}..."
            try:
                from packages.video_enhancement.src.color_grading import apply_color_grade
                temp_path = result + ".graded.mp4"
                apply_color_grade(result, temp_path, preset=color_preset)
                import os
                os.replace(temp_path, result)
            except Exception as e:
                print(f"[Color Grading] 跳过: {e}")

        if stabilize:
            task["progress"] = 90
            task["message"] = "正在应用视频防抖..."
            try:
                from packages.video_enhancement.src.stabilizer import stabilize_video
                temp_path = result + ".stab.mp4"
                stabilize_video(result, temp_path)
                import os
                os.replace(temp_path, result)
            except Exception as e:
                print(f"[Stabilize] 跳过: {e}")

        task["status"] = "done"
        task["progress"] = 100
        task["message"] = "混剪完成!"
        task["output_path"] = result

    except Exception as e:
        task["status"] = "error"
        task["message"] = f"混剪失败: {str(e)}"
        print(f"[Pipeline Error] task={task_id}")
        traceback.print_exc()


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


@app.get("/api/styles")
async def list_styles():
    """获取可用风格模板列表"""
    from packages.video_enhancement.src.style_templates import get_style_names
    return get_style_names()


@app.post("/api/upload/video")
async def upload_video(files: list[UploadFile] = File(...)):
    """上传视频文件"""
    saved = []
    for f in files:
        dest = UPLOAD_DIR / f"{uuid.uuid4().hex}_{f.filename}"
        with open(dest, "wb") as fh:
            shutil.copyfileobj(f.file, fh)
        saved.append(str(dest))
    return {"files": saved}


@app.post("/api/upload/bgm")
async def upload_bgm(file: UploadFile = File(...)):
    """上传 BGM 文件"""
    dest = UPLOAD_DIR / f"bgm_{uuid.uuid4().hex}_{file.filename}"
    with open(dest, "wb") as fh:
        shutil.copyfileobj(file.file, fh)
    return {"path": str(dest)}


@app.post("/api/montage")
async def create_montage(
    background_tasks: BackgroundTasks,
    video_paths: str = Form(...),        # JSON 数组字符串
    bgm_path: Optional[str] = Form(None),
    bgm_query: Optional[str] = Form(None),
    style: str = Form("dynamic"),
    style_preset: Optional[str] = Form(None),
    output_name: str = Form("final.mp4"),
    query: Optional[str] = Form(None),
    source: str = Form("playphrase"),
    clip_limit: int = Form(20),
):
    """创建混剪任务 — 立即返回 task_id，搜索下载在后台进行"""
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {
        "id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "任务已创建，正在准备...",
        "output_path": None,
    }

    # 解析本地上传的视频路径
    video_paths_list = json.loads(video_paths) if video_paths else []

    # 风格预设处理
    color_preset = None
    stabilize = False
    if style_preset:
        from packages.video_enhancement.src.style_templates import get_pipeline_params
        preset_params = get_pipeline_params(style_preset)
        style = preset_params.get("style", style)
        color_preset = preset_params.get("color_preset")
        stabilize = preset_params.get("stabilize", False)

    # 立即返回 task_id，所有耗时操作在后台执行
    background_tasks.add_task(
        _run_montage_task, task_id, video_paths_list, bgm_path, bgm_query,
        style, output_name, query, source, clip_limit, color_preset, stabilize
    )

    return {"task_id": task_id}


@app.get("/api/task/{task_id}")
async def get_task(task_id: str):
    """查询任务状态"""
    if task_id not in _tasks:
        return {"error": "任务不存在"}
    return _tasks[task_id]


@app.get("/api/task/{task_id}/progress")
async def task_progress(task_id: str):
    """SSE 实时进度"""
    async def event_generator():
        while True:
            if task_id not in _tasks:
                yield f"data: {json.dumps({'error': 'not found'})}\n\n"
                break
            task = _tasks[task_id]
            yield f"data: {json.dumps(task)}\n\n"
            if task["status"] in ("done", "error"):
                break
            await asyncio.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/download/{task_id}")
async def download_result(task_id: str):
    """下载结果视频"""
    if task_id not in _tasks:
        return {"error": "任务不存在"}
    task = _tasks[task_id]
    if task["status"] != "done" or not task["output_path"]:
        return {"error": "任务未完成"}
    return FileResponse(task["output_path"], media_type="video/mp4", filename="montage.mp4")


def start_webui(host: str = "0.0.0.0", port: int = 8000):
    """启动 WebUI"""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    start_webui()
