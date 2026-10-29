"""云 TTS 引擎：火山引擎（豆包语音）音频生成 HTTP —— few-shot 声音复刻。

一次请求完成：参考音频（样本）+ 文本 -> 合成语音，无需训练流程，
与"样本即音色"的零样本克隆架构一致。

接口（官方文档 6561/2550782）：
    POST https://openspeech.bytedance.com/api/v3/tts/create
    鉴权: X-Api-Key: <API Key>（火山引擎控制台 -> 豆包语音 -> API Key 管理）
    请求: {"model":"seed-audio-1.0","text_prompt":文本,"audio_data":参考音频base64,
            "audio_config":{format,sample_rate},"watermark":{...}}
    响应: {"audio":"<base64>","url":"临时地址(2h)","duration":...}

合规：默认开启 aigc_watermark（合成结尾附音频节奏标识，即 AI 生成内容标识）。
"""
import base64
import json
import os
import uuid

import requests

from .base import VoiceEngine

_ENDPOINT = "https://openspeech.bytedance.com/api/v3/tts/create"
_MODEL = "seed-audio-1.0"
_REF_MAX_BYTES = 10 * 1024 * 1024  # 参考音频 ≤10MB
_REF_MAX_SECONDS = 30.0  # 参考音频 ≤30s


class VolcTTSEngine(VoiceEngine):
    """火山引擎 few-shot 云合成（演示/生产通用）。"""

    name = "cloud"

    def __init__(self, api_key: str, outputs_dir: str = "", sample_rate: int = 24000, fmt: str = "mp3"):
        if not api_key:
            raise RuntimeError("未配置 VOLC_API_KEY，无法使用云 TTS 引擎")
        self._api_key = api_key
        self.outputs_dir = outputs_dir or os.path.join(os.getcwd(), "data", "outputs")
        self._sample_rate = sample_rate
        self._fmt = fmt

    def synthesize(self, sample_path: str, text: str, language: str) -> str:
        if os.path.getsize(sample_path) > _REF_MAX_BYTES:
            raise RuntimeError(f"参考音频超过 10MB 限制（当前 {os.path.getsize(sample_path)//1024}KB），请用更短的样本")
        audio_b64 = base64.b64encode(open(sample_path, "rb").read()).decode("ascii")

        body = {
            "model": _MODEL,
            "text_prompt": text,
            "audio_data": audio_b64,
            "audio_config": {
                "format": self._fmt,
                "sample_rate": self._sample_rate,
            },
            "watermark": {"aigc_watermark": True},
        }
        resp = requests.post(
            _ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "X-Api-Key": self._api_key,
                "X-Api-Request-Id": str(uuid.uuid4()),
            },
            json=body,
            timeout=180,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"云 TTS 失败(HTTP {resp.status_code}): {resp.text[:300]}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise RuntimeError("云 TTS 返回非 JSON 响应") from exc

        audio_b64 = data.get("audio")
        if not audio_b64:
            raise RuntimeError(f"云 TTS 失败: code={data.get('code')} message={data.get('message')}")

        os.makedirs(self.outputs_dir, exist_ok=True)
        out = os.path.join(self.outputs_dir, f"{uuid.uuid4().hex}.{self._fmt}")
        with open(out, "wb") as f:
            f.write(base64.b64decode(audio_b64))
        return out
