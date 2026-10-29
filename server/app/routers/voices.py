"""音色库接口：上传声音样本、列表、试听、删除。"""
import os
import shutil
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse

from .. import audio_utils
from ..deps import get_current_user

router = APIRouter(prefix="/api/voices", tags=["voices"])

MAX_BYTES = 10 * 1024 * 1024  # 10MB


def _voice_dict(voice: dict) -> dict:
    data = dict(voice)
    data["sample_url"] = f"/api/voices/{voice['id']}/sample"
    data.pop("sample_path", None)
    data.pop("user_id", None)
    return data


@router.post("")
def create_voice(
    request: Request,
    file: UploadFile = File(...),
    name: str = Form(...),
    lang: str = Form("zh"),
    consent: int = Form(0),
    user: dict = Depends(get_current_user),
):
    settings = request.app.state.settings
    db = request.app.state.db

    name = (name or "").strip()
    if not (1 <= len(name) <= 20):
        raise HTTPException(status_code=400, detail="音色名称需为 1-20 个字符")
    if consent != 1:
        raise HTTPException(status_code=400, detail="请确认您拥有该声音的使用/授权权利")
    if lang not in ("zh", "en", "ja", "ko", "fr", "de", "es", "it", "pt", "ru", "ar"):
        raise HTTPException(status_code=400, detail="不支持的语言")

    ext = audio_utils.safe_ext(file.filename or "")
    if ext is None:
        raise HTTPException(status_code=400, detail="仅支持 mp3 / wav / m4a / aac / ogg 音频")

    user_dir = os.path.join(settings.samples_dir, str(user["id"]))
    os.makedirs(user_dir, exist_ok=True)
    dest = os.path.join(user_dir, f"{uuid.uuid4().hex}{ext}")

    size = 0
    with open(dest, "wb") as out:
        while True:
            chunk = file.file.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_BYTES:
                out.close()
                os.remove(dest)
                raise HTTPException(status_code=400, detail="音频文件不能超过 10MB")
            out.write(chunk)

    duration = audio_utils.audio_duration(dest)
    voice = db.create_voice(user["id"], name, dest, duration, lang, consent)
    return _voice_dict(voice)


@router.get("")
def list_voices(request: Request, user: dict = Depends(get_current_user)):
    db = request.app.state.db
    voices = db.list_voices(user["id"])
    return [_voice_dict(v) for v in voices]


@router.get("/{voice_id}/sample")
def sample_audio(
    voice_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
):
    db = request.app.state.db
    voice = db.get_voice(voice_id)
    if voice is None or voice["user_id"] != user["id"] or not os.path.exists(voice["sample_path"]):
        raise HTTPException(status_code=404, detail="音色不存在")
    return FileResponse(voice["sample_path"], media_type=audio_utils.media_type(voice["sample_path"]))


@router.delete("/{voice_id}")
def delete_voice(
    voice_id: int,
    request: Request,
    user: dict = Depends(get_current_user),
):
    db = request.app.state.db
    voice = db.get_voice(voice_id)
    if voice is None or voice["user_id"] != user["id"]:
        raise HTTPException(status_code=404, detail="音色不存在")
    db.delete_voice(voice_id, user["id"])
    if os.path.exists(voice["sample_path"]):
        try:
            os.remove(voice["sample_path"])
        except OSError:
            pass
    return {"ok": True}
