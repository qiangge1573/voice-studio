"""合成接口：提交文本 -> 异步任务 -> 轮询状态 -> 播放音频。"""
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .. import audio_utils
from ..deps import get_current_user

router = APIRouter(prefix="/api/tts", tags=["tts"])

MAX_TEXT = 1000


class SynthesizeRequest(BaseModel):
    voice_id: int
    text: str
    language: str = "zh"


def _run_job(db, engine, task_id: str, sample_path: str, text: str, language: str) -> None:
    try:
        db.update_task(task_id, status="running")
        out_path = engine.synthesize(sample_path, text, language)
        db.update_task(task_id, status="done", output_path=out_path, finished_at=__import__("time").time())
    except Exception as exc:  # noqa: BLE001
        db.update_task(
            task_id,
            status="failed",
            error=str(exc)[:500],
            finished_at=__import__("time").time(),
        )


@router.post("/synthesize")
def synthesize(payload: SynthesizeRequest, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    engine = request.app.state.engine
    tm = request.app.state.task_manager

    voice = db.get_voice(payload.voice_id)
    if voice is None or voice["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="音色不存在")
    text = (payload.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="请输入要合成的文本")
    if len(text) > MAX_TEXT:
        raise HTTPException(status_code=400, detail=f"文本不能超过 {MAX_TEXT} 字")

    task_id = uuid.uuid4().hex
    db.create_task(task_id, user["id"], voice["id"], voice["name"], text, payload.language)
    tm.submit(lambda: _run_job(db, engine, task_id, voice["sample_path"], text, payload.language))
    return {"task_id": task_id}


@router.get("/tasks/{task_id}")
def task_status(task_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    task = db.get_task(task_id, user["id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return {
        "task_id": task["id"],
        "status": task["status"],
        "text": task["text"],
        "voice_name": task["voice_name"],
        "language": task["language"],
        "error": task["error"],
        "audio_url": f"/api/tts/tasks/{task_id}/audio" if task["status"] == "done" else None,
        "created_at": task["created_at"],
        "finished_at": task["finished_at"],
    }


@router.get("/tasks/{task_id}/audio")
def task_audio(task_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    task = db.get_task(task_id, user["id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    if task["status"] != "done" or not task.get("output_path") or not os.path.exists(task["output_path"]):
        raise HTTPException(status_code=404, detail="音频尚未生成")
    return FileResponse(task["output_path"], media_type=audio_utils.media_type(task["output_path"]))
