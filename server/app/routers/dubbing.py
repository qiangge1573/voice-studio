"""视频配音接口：上传视频 + 台本 + 音色 -> 逐段云合成 -> ffmpeg 按时间轴混音 -> 输出 mp4。

台本格式（每行一条，可混用）：
    "[mm:ss] 文本"  锚定到指定时间开始配音
    "文本"          顺序接续（第一段从 0 开始）
"""
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from .. import audio_utils, video_utils
from ..deps import get_current_user

router = APIRouter(prefix="/api/dubbing", tags=["dubbing"])

MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100MB
ALLOWED_VIDEO_EXT = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm"}
_MAX_LINES = 30


def _run_job(db, engine, task_id: str, voice: dict, video_path: str,
             script: str, mode: str, settings) -> None:
    import time
    try:
        db.update_dubbing(task_id, status="running")
        segments = video_utils.parse_script(script)
        if not segments:
            raise RuntimeError("台本为空，请至少输入一行文本")

        # 1) 逐段合成配音
        rendered = []
        for seg in segments:
            out = engine.synthesize(voice["sample_path"], seg["text"], voice.get("lang", "zh"))
            rendered.append({"audio_path": out, "anchor": seg["anchor"], "text": seg["text"]})

        # 2) ffmpeg 混音
        output = os.path.join(settings.outputs_dir, f"dub_{uuid.uuid4().hex}.mp4")
        video_utils.render_dubbing(video_path, rendered, mode, output)
        db.update_dubbing(task_id, status="done", output_path=output, finished_at=time.time())
    except Exception as exc:  # noqa: BLE001
        db.update_dubbing(task_id, status="failed", error=str(exc)[:500], finished_at=time.time())


@router.post("")
def create_dubbing(
    request: Request,
    file: UploadFile = File(...),
    voice_id: int = Form(...),
    script: str = Form(...),
    mode: str = Form("overlay"),
    user: dict = Depends(get_current_user),
):
    settings = request.app.state.settings
    db = request.app.state.db
    engine = request.app.state.engine
    tm = request.app.state.task_manager

    voice = db.get_voice(voice_id)
    if voice is None or voice["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="音色不存在")
    if mode not in ("overlay", "replace"):
        raise HTTPException(status_code=400, detail="mode 仅支持 overlay / replace")
    lines = video_utils.parse_script(script)
    if not lines:
        raise HTTPException(status_code=400, detail="台本为空，请输入至少一行文本")
    if len(lines) > _MAX_LINES:
        raise HTTPException(status_code=400, detail=f"台本行数不能超过 {_MAX_LINES} 行")

    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in ALLOWED_VIDEO_EXT:
        raise HTTPException(status_code=400, detail=f"仅支持视频格式: {', '.join(sorted(ALLOWED_VIDEO_EXT))}")

    user_dir = os.path.join(settings.videos_dir, str(user["id"]))
    os.makedirs(user_dir, exist_ok=True)
    video_path = os.path.join(user_dir, f"{uuid.uuid4().hex}{ext}")

    size = 0
    with open(video_path, "wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_VIDEO_BYTES:
                out.close()
                os.remove(video_path)
                raise HTTPException(status_code=400, detail="视频文件不能超过 100MB")
            out.write(chunk)

    task_id = uuid.uuid4().hex
    db.create_dubbing(task_id, user["id"], voice["id"], voice["name"], video_path, script, mode)
    tm.submit(lambda: _run_job(db, engine, task_id, voice, video_path, script, mode, settings))
    return {"task_id": task_id}


@router.get("/tasks")
def list_dubbing(request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    tasks = db.list_dubbing(user["id"])
    return [
        {
            "task_id": t["id"],
            "status": t["status"],
            "voice_name": t["voice_name"],
            "mode": t["mode"],
            "error": t["error"],
            "video_url": f"/api/dubbing/tasks/{t['id']}/video" if t["status"] == "done" else None,
            "created_at": t["created_at"],
            "finished_at": t["finished_at"],
        }
        for t in tasks
    ]


@router.get("/tasks/{task_id}")
def task_status(task_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    task = db.get_dubbing(task_id, user["id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task["id"],
        "status": task["status"],
        "voice_name": task["voice_name"],
        "mode": task["mode"],
        "error": task["error"],
        "video_url": f"/api/dubbing/tasks/{task_id}/video" if task["status"] == "done" else None,
        "created_at": task["created_at"],
        "finished_at": task["finished_at"],
    }


@router.get("/tasks/{task_id}/video")
def task_video(task_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    task = db.get_dubbing(task_id, user["id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] != "done" or not task.get("output_path") or not os.path.exists(task["output_path"]):
        raise HTTPException(status_code=404, detail="视频尚未生成")
    return FileResponse(task["output_path"], media_type="video/mp4")
