"""FastAPI 依赖：数据库、引擎、当前用户。"""
from fastapi import Depends, Header, HTTPException, Query, Request

from .auth import decode_token
from .config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request):
    return request.app.state.db


def get_engine(request: Request):
    return request.app.state.engine


def get_task_manager(request: Request):
    return request.app.state.task_manager


def get_current_user(
    request: Request,
    authorization: str = Header(default=""),
    token: str = Query(default=""),
) -> dict:
    """从 Authorization 头或 ?token= 中解析用户。"""
    settings: Settings = request.app.state.settings
    raw = authorization or token
    if raw.startswith("Bearer "):
        raw = raw[7:]
    user_id = decode_token(raw, settings.jwt_secret) if raw else None
    # 同时携带头与查询参数时，头无效则回退查询参数（小程序音频播放只传 ?token=）
    if user_id is None and token and token != raw:
        user_id = decode_token(token, settings.jwt_secret)
    if user_id is None:
        raise HTTPException(status_code=401, detail="未登录或令牌已失效")
    db = request.app.state.db
    user = db.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user
