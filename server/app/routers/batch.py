"""批量合成接口：一次提交多行文本，逐条合成，按任务轮询。"""
import json
import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .. import audio_utils
from ..deps import get_current_user

router = APIRouter(prefix="/api/batch", tags=["batch"])

MAX_LINES = 100
MAX_LINE_LEN = 1000


class BatchRequest(BaseModel):
    voice_id: int
    lines: list = Field(..., min_length=1)
    language: str = "zh"


def _run_job(db, engine, task_id: str, voice: dict, items: list, language: str) -> None:
    import time
    try:
        db.update_batch(task_id, status="running")
        done = 0
        for idx, item in enumerate(items):
            try:
                if not item["text"]:
                    raise RuntimeError("空文本")
                out = engine.synthesize(voice["sample_path"], item["text"], language)
                items[idx]["status"] = "done"
                items[idx]["output_path"] = out
                items[idx]["error"] = None
            except Exception as exc:  # noqa: BLE001
                items[idx]["status"] = "failed"
                items[idx]["error"] = str(exc)[:300]
            done += 1
            db.update_batch(task_id, items=json.dumps(items, ensure_ascii=False))
        db.update_batch(
            task_id,
            status="done",
            finished_at=time.time(),
        )
    except Exception as exc:  # noqa: BLE001
        db.update_batch(task_id, status="failed", error=str(exc)[:500], finished_at=time.time())


def _task_dict(task: dict) -> dict:
    items = []
    try:
        raw = json.loads(task["items"])
    except Exception:
        raw = []
    for i, it in enumerate(raw):
        items.append(
            {
                "index": i,
                "text": it.get("text", ""),
                "status": it.get("status", "pending"),
                "error": it.get("error"),
                "audio_url": f"/api/batch/tasks/{task['id']}/items/{i}/audio"
                if it.get("status") == "done" else None,
            }
        )
    return {
        "task_id": task["id"],
        "status": task["status"],
        "voice_name": task["voice_name"],
        "error": task.get("error"),
        "items": items,
        "created_at": task["created_at"],
        "finished_at": task["finished_at"],
    }


@router.post("")
def create_batch(payload: BatchRequest, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    engine = request.app.state.engine
    tm = request.app.state.task_manager

    voice = db.get_voice(payload.voice_id)
    if voice is None or voice["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="音色不存在")

    lines = [str(x).strip() for x in payload.lines if str(x).strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="请输入至少一行文本")
    if len(lines) > MAX_LINES:
        raise HTTPException(status_code=400, detail=f"最多支持 {MAX_LINES} 行")
    for line in lines:
        if len(line) > MAX_LINE_LEN:
            raise HTTPException(status_code=400, detail=f"单行文本不能超过 {MAX_LINE_LEN} 字")

    items = [{"text": t, "status": "pending", "error": None, "output_path": None} for t in lines]
    task_id = uuid.uuid4().hex
    db.create_batch(task_id, user["id"], voice["id"], voice["name"],
                    payload.language, json.dumps(items, ensure_ascii=False))
    tm.submit(lambda: _run_job(db, engine, task_id, voice, items, payload.language))
    return {"task_id": task_id}


@router.get("/tasks")
def list_batch(request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    return [_task_dict(t) for t in db.list_batch(user["id"])]


@router.get("/tasks/{task_id}")
def task_status(task_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    task = db.get_batch(task_id, user["id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    return _task_dict(task)


@router.get("/tasks/{task_id}/items/{index}/audio")
def item_audio(task_id: str, index: int, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    task = db.get_batch(task_id, user["id"])
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    try:
        items = json.loads(task["items"])
        item = items[index]
    except Exception:
        raise HTTPException(status_code=404, detail="条目不存在") from None
    if item.get("status") != "done" or not item.get("output_path") or not os.path.exists(item["output_path"]):
        raise HTTPException(status_code=404, detail="音频尚未生成")
    return FileResponse(item["output_path"], media_type=audio_utils.media_type(item["output_path"]))
