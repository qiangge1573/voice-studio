"""Mock 引擎：不依赖任何模型，用正弦波按文本长度生成"占位语音"。

用途：在没有 GPU / 未安装推理模型时，把「录音 -> 上传 -> 建音色 ->
文本合成 -> 播放 -> 历史」整条链路跑通，用于接口联调与小程序开发。
输出的音频不是人声，仅用于流程验证，勿用于演示 AI 效果。
"""
import hashlib
import math
import os
import struct
import uuid
import wave

from .base import VoiceEngine


def _make_wav(path: str, duration: float, base_freq: float) -> str:
    sample_rate = 16000
    n = int(sample_rate * duration)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n):
            t = i / sample_rate
            # 简单包络：淡入淡出，避免爆音
            envelope = min(1.0, t / 0.05, (duration - t) / 0.05)
            value = 0.35 * envelope * math.sin(2 * math.pi * base_freq * t)
            frames += struct.pack("<h", int(value * 32767))
        wf.writeframes(bytes(frames))
    return path


class MockEngine(VoiceEngine):
    name = "mock"

    def __init__(self, outputs_dir: str = ""):
        self.outputs_dir = outputs_dir or os.path.join(os.getcwd(), "data", "outputs")
        print("[mock] 正在使用 MockEngine：生成占位音频用于流程联调，请勿当作真实合成效果。")

    def synthesize(self, sample_path: str, text: str, language: str) -> str:
        # 用文本长度和内容派生时长与音高，让不同输入产生可区分的输出
        duration = max(1.2, 0.5 + 0.28 * len(text))
        freq = 220 + (int(hashlib.md5(text.encode("utf-8")).hexdigest(), 16) % 500)
        os.makedirs(self.outputs_dir, exist_ok=True)
        out = os.path.join(self.outputs_dir, f"{uuid.uuid4().hex}.wav")
        return _make_wav(out, min(duration, 20.0), freq)
