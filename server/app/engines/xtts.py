"""XTTS v2 引擎（Coqui TTS）：多语言零样本克隆，中文支持良好。

安装：pip install torch TTS>=0.22.0，首次初始化自动下载模型
（tts_models/multilingual/multi-dataset/xtts_v2，约 1.8GB）。
建议 GPU 推理；CPU 可用但较慢。
"""
import os
import uuid

from .base import VoiceEngine

# 语言代码映射：小程序侧传简码 -> XTTS 的语言代码
_LANG_MAP = {
    "zh": "zh-cn", "en": "en", "ja": "ja", "ko": "ko",
    "fr": "fr-fr", "de": "de", "es": "es", "it": "it",
    "pt": "pt", "ru": "ru", "ar": "ar",
}


class XTTSEngine(VoiceEngine):
    name = "xtts"

    def __init__(self, device: str = "cpu", outputs_dir: str = ""):
        self.outputs_dir = outputs_dir or os.path.join(os.getcwd(), "data", "outputs")
        try:
            from TTS.api import TTS
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "XTTS 引擎需要安装依赖：pip install torch TTS>=0.22.0"
            ) from exc
        print(f"[xtts] 加载 XTTS v2（device={device}），首次运行会自动下载模型…")
        self._tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

    def synthesize(self, sample_path: str, text: str, language: str) -> str:
        os.makedirs(self.outputs_dir, exist_ok=True)
        out = os.path.join(self.outputs_dir, f"{uuid.uuid4().hex}.wav")
        lang = _LANG_MAP.get(language or "zh", "zh-cn")
        self._tts.tts_to_file(
            text=text,
            speaker_wav=sample_path,
            language=lang,
            file_path=out,
        )
        return out
