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


def _run_pipeline_task(task_id: str, video_paths: list, bgm_path: str, style: str, output_name: str):
    """后台运行 pipeline"""
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from pipeline import MontagePipeline

    task = _tasks[task_id]
    try:
        task["status"] = "running"
        task["progress"] = 10
        task["message"] = "正在检测镜头..."

        pipeline = MontagePipeline(cache_dir="cache", output_dir="output")
        result = pipeline.run(video_paths, bgm_path, style, output_name, threshold=0.2)

        task["status"] = "done"
        task["progress"] = 100
        task["message"] = "混剪完成!"
        task["output_path"] = result
    except Exception as e:
        task["status"] = "error"
        task["message"] = str(e)


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path(__file__).parent / "index.html"
    return HTMLResponse(html_path.read_text(encoding="utf-8"))


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
    bgm_path: str = Form(...),
    style: str = Form("dynamic"),
    output_name: str = Form("final.mp4"),
    query: Optional[str] = Form(None),
    source: str = Form("bilibili"),
    clip_limit: int = Form(20),
):
    """创建混剪任务"""
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {
        "id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "任务已创建",
        "output_path": None,
    }

    # 如果是搜索模式，先下载视频
    if query:
        from packages.video_crawler.src.bilibili_crawler import BilibiliCrawler
        crawler = BilibiliCrawler()
        video_paths_list = crawler.search_and_download(query, max_clips=clip_limit)
    else:
        video_paths_list = json.loads(video_paths)

    # 后台运行 pipeline
    background_tasks.add_task(
        _run_pipeline_task, task_id, video_paths_list, bgm_path, style, output_name
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
