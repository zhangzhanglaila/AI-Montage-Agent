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


def _run_pipeline_task(task_id: str, video_paths: list, bgm_path: str, style: str, output_name: str, color_preset: str = None, stabilize: bool = False):
    """后台运行 pipeline"""
    import sys
    import traceback
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from pipeline import MontagePipeline

    task = _tasks[task_id]
    try:
        task["status"] = "running"
        task["progress"] = 10
        task["message"] = "正在检测镜头..."

        if not video_paths:
            task["status"] = "error"
            task["message"] = "没有可用的视频文件，请检查搜索关键词"
            return

        task["progress"] = 20
        task["message"] = f"正在处理 {len(video_paths)} 个视频..."

        pipeline = MontagePipeline(cache_dir="cache", output_dir="output")
        result = pipeline.run(video_paths, bgm_path, style, output_name, threshold=0.2)

        # 应用颜色分级（如果指定了预设）
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

        # 应用防抖（如果启用了）
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
        task["message"] = str(e)
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
    """创建混剪任务"""
    task_id = uuid.uuid4().hex
    _tasks[task_id] = {
        "id": task_id,
        "status": "pending",
        "progress": 0,
        "message": "任务已创建",
        "output_path": None,
    }

    # BGM：搜索下载或使用上传的文件
    if bgm_query:
        from packages.video_crawler.src.bgm_crawler import BgmCrawler
        bgm_crawler = BgmCrawler()
        bgm_paths = bgm_crawler.search_and_download(bgm_query, max_clips=1)
        if not bgm_paths:
            _tasks[task_id]["status"] = "error"
            _tasks[task_id]["message"] = f"未找到 BGM: {bgm_query}"
            return {"task_id": task_id}
        bgm_path = bgm_paths[0]
    elif not bgm_path:
        _tasks[task_id]["status"] = "error"
        _tasks[task_id]["message"] = "请提供 BGM 文件或搜索关键词"
        return {"task_id": task_id}

    # 视频来源：搜索下载或使用上传的文件
    if query:
        from packages.video_crawler.src.quote_crawler import create_quote_crawler
        from packages.video_crawler.src.bilibili_crawler import BilibiliCrawler
        try:
            if source in ("playphrase", "quodb"):
                crawler = create_quote_crawler(source)
            elif source == "bilibili":
                crawler = BilibiliCrawler()
            else:
                crawler = BilibiliCrawler()
            video_paths_list = crawler.search_and_download(query, max_clips=clip_limit)
        except Exception:
            video_paths_list = []
    else:
        video_paths_list = json.loads(video_paths)

    # 风格预设处理
    color_preset = None
    stabilize = False
    if style_preset:
        from packages.video_enhancement.src.style_templates import get_pipeline_params
        preset_params = get_pipeline_params(style_preset)
        style = preset_params.get("style", style)
        color_preset = preset_params.get("color_preset")
        stabilize = preset_params.get("stabilize", False)

    # 后台运行 pipeline
    background_tasks.add_task(
        _run_pipeline_task, task_id, video_paths_list, bgm_path, style, output_name, color_preset, stabilize
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
