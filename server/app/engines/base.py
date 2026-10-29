"""语音克隆/合成引擎抽象。"""
from abc import ABC, abstractmethod


class VoiceEngine(ABC):
    """统一引擎接口。

    采用"零样本克隆"范式（与 VoiceStudio / XTTS 一致）：不额外训练，
    合成时直接以参考音频（speaker_wav）为音色条件。
    """

    name = "base"

    @abstractmethod
    def synthesize(self, sample_path: str, text: str, language: str) -> str:
        """以 sample_path 为音色参考，把 text 合成为语音。

        返回生成音频的绝对路径（.wav 或 .mp3）。
        子类需自行保证输出目录存在。
        """
        raise NotImplementedError
