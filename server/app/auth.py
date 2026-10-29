"""登录与令牌：微信 code2session + 自签 HMAC-SHA256 JWT（零额外依赖）。

生产环境建议换成标准 PyJWT 与更完善的密钥管理；这里用标准库实现，
便于开箱即跑。令牌同时支持放在 Authorization 头或 ?token= 查询参数
（后者专供小程序 InnerAudioContext 播放音频时使用）。
"""
import base64
import hashlib
import hmac
import json
import time
from typing import Optional

import requests

TOKEN_TTL = 7 * 24 * 3600  # 7 天


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64url(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def create_token(user_id: int, secret: str, ttl: int = TOKEN_TTL) -> str:
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8"))
    payload = _b64url(
        json.dumps({"uid": user_id, "exp": int(time.time()) + ttl}).encode("utf-8")
    )
    signing_input = f"{header}.{payload}".encode("ascii")
    signature = _b64url(
        hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def decode_token(token: str, secret: str) -> Optional[int]:
    """校验签名与过期时间，成功返回 user_id，失败返回 None。"""
    try:
        header, payload, signature = token.split(".")
        signing_input = f"{header}.{payload}".encode("ascii")
        expected = _b64url(
            hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
        )
        if not hmac.compare_digest(signature, expected):
            return None
        data = json.loads(_unb64url(payload).decode("utf-8"))
        if data.get("exp", 0) < time.time():
            return None
        return int(data.get("uid", 0))
    except Exception:
        return None


def wx_code2session(appid: str, secret: str, code: str) -> str:
    """调用微信 jscode2session，返回 openid。"""
    resp = requests.get(
        "https://api.weixin.qq.com/sns/jscode2session",
        params={
            "appid": appid,
            "secret": secret,
            "js_code": code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    data = resp.json()
    openid = data.get("openid")
    if not openid:
        raise ValueError(f"微信登录失败: {data.get('errmsg', data)}")
    return str(openid)
