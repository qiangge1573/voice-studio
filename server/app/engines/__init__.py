"""引擎工厂：按配置选择 cloud / mock / xtts / cosyvoice。

- ENGINE=cloud：火山引擎云 TTS（few-shot 声音复刻）。未配置 VOLC_API_KEY 时
  自动回退到 mock 并打印醒目警告——保证 demo/联调阶段无密钥也能跑通全流程，
  配置密钥后即为真实云合成。
"""
from .base import VoiceEngine
from .mock import MockEngine


def get_engine(settings) -> VoiceEngine:
    engine = (settings.engine or "cloud").lower()
    outputs_dir = settings.outputs_dir
    if engine == "cloud":
        if not settings.volc_api_key:
            print(
                "\n[cloud] ⚠️ 未配置 VOLC_API_KEY，已回退到 MockEngine（占位音频）。"
                "\n[cloud] 获取密钥：火山引擎控制台 -> 豆包语音 -> API Key 管理。"
                "\n[cloud] 配置后：.env 写入 VOLC_API_KEY=xxx 并设置 ENGINE=cloud 即启用真实云合成。\n"
            )
            return MockEngine(outputs_dir)
        from .cloud import VolcTTSEngine
        print("[cloud] 使用火山引擎云 TTS（seed-audio-1.0 few-shot 复刻）")
        return VolcTTSEngine(settings.volc_api_key, outputs_dir)
    if engine == "mock":
        return MockEngine(outputs_dir)
    if engine == "xtts":
        from .xtts import XTTSEngine
        return XTTSEngine(settings.device, outputs_dir)
    if engine == "cosyvoice":
        from .cosyvoice import CosyVoiceEngine
        return CosyVoiceEngine(settings.cosyvoice_model_dir, settings.device, outputs_dir)
    raise ValueError(f"未知引擎: {settings.engine}（可选 cloud / mock / xtts / cosyvoice）")
