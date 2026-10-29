"""历史记录接口。"""
import os

from fastapi import APIRouter, Depends, HTTPException, Request

from ..deps import get_current_user

router = APIRouter(prefix="/api/history", tags=["history"])


@router.get("")
def list_history(request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    tasks = db.list_tasks(user["id"])
    return [
        {
            "task_id": t["id"],
            "status": t["status"],
            "text": t["text"],
            "voice_name": t["voice_name"],
            "language": t["language"],
            "error": t["error"],
            "audio_url": f"/api/tts/tasks/{t['id']}/audio" if t["status"] == "done" else None,
            "created_at": t["created_at"],
            "finished_at": t["finished_at"],
        }
        for t in tasks
    ]


@router.delete("/{task_id}")
def delete_history(task_id: str, request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    task = db.get_task(task_id, user["id"])
    if task is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    db.delete_task(task_id, user["id"])
    if task.get("output_path") and os.path.exists(task["output_path"]):
        try:
            os.remove(task["output_path"])
        except OSError:
            pass
    return {"ok": True}
