"""登录接口：微信 code2session；dev_mode 下接受 code=dev。"""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from ..auth import create_token, wx_code2session

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    code: str = ""
    nickname: str = ""


@router.post("/login")
def login(payload: LoginRequest, request: Request):
    settings = request.app.state.settings
    db = request.app.state.db

    if settings.dev_mode and payload.code in ("dev", ""):
        openid = "dev-openid"
    else:
        try:
            openid = wx_code2session(
                settings.wechat_app_id, settings.wechat_app_secret, payload.code
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    user = db.get_user_by_openid(openid)
    if user is None:
        user = db.create_user(openid, (payload.nickname or "")[:30])

    token = create_token(user["id"], settings.jwt_secret)
    return {
        "token": token,
        "user": {"id": user["id"], "nickname": user["nickname"]},
    }
