"""CosyVoice2 引擎（阿里 FunAudioLLM）：中文克隆效果一流。

安装：
    git clone https://github.com/FunAudioLLM/CosyVoice && cd CosyVoice
    pip install -r requirements.txt && pip install -e .
    modelscope download --model iic/CosyVoice2-0.5B pretrained_models/CosyVoice2-0.5B

参考音频会被重采样为 16kHz 单声道作为 prompt。
"""
import os
import uuid

from .base import VoiceEngine


class CosyVoiceEngine(VoiceEngine):
    name = "cosyvoice"

    def __init__(self, model_dir: str, device: str = "cpu", outputs_dir: str = ""):
        self.outputs_dir = outputs_dir or os.path.join(os.getcwd(), "data", "outputs")
        try:
            import torch  # noqa: F401
            import torchaudio  # noqa: F401
            from cosyvoice.cli.cosyvoice import CosyVoice2
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "CosyVoice 引擎需要按官方 README 安装 torch/torchaudio/cosyvoice 并下载模型"
            ) from exc
        print(f"[cosyvoice] 加载 CosyVoice2（model_dir={model_dir}）…")
        self._cv = CosyVoice2(
            model_dir, load_jit=False, load_trt=False, fp16=(device == "cuda")
        )
        self._sample_rate = self._cv.sample_rate

    def synthesize(self, sample_path: str, text: str, language: str) -> str:
        import torch
        import torchaudio

        prompt_16k, sr = torchaudio.load(sample_path)
        if sr != 16000:
            prompt_16k = torchaudio.transforms.Resample(sr, 16000)(prompt_16k)
        if prompt_16k.shape[0] > 1:
            prompt_16k = torch.mean(prompt_16k, dim=0, keepdim=True)

        os.makedirs(self.outputs_dir, exist_ok=True)
        out = os.path.join(self.outputs_dir, f"{uuid.uuid4().hex}.wav")

        # inference_zero_shot 返回生成块；这里取第一块（stream=False 通常仅一块）
        for chunk in self._cv.inference_zero_shot(text, prompt_16k, stream=False):
            torchaudio.save(out, chunk["tts_speech"], self._sample_rate)
            break
        return out
