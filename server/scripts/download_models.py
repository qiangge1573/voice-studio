"""模型下载辅助脚本（可选）。

- XTTS v2：由 TTS 库在首次初始化时自动下载到 ~/.local/share/tts/。
  本脚本提供手动预下载，便于离线环境。
- CosyVoice2：从 ModelScope 下载到 pretrained_models/。

用法：
    python scripts/download_models.py xtts
    python scripts/download_models.py cosyvoice
"""
import sys


def download_xtts() -> None:
    try:
        from TTS.api import TTS
    except ImportError:
        print("请先安装: pip install torch TTS>=0.22.0")
        sys.exit(1)
    print("正在下载 XTTS v2 模型（约 1.8GB，仅首次需要）…")
    TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    print("XTTS v2 模型就绪。")


def download_cosyvoice() -> None:
    try:
        import modelscope  # noqa: F401
        from modelscope import snapshot_download
    except ImportError:
        print("请先安装: pip install modelscope")
        sys.exit(1)
    print("正在从 ModelScope 下载 CosyVoice2-0.5B …")
    snapshot_download("iic/CosyVoice2-0.5B", local_dir="pretrained_models/CosyVoice2-0.5B")
    print("CosyVoice2 模型就绪。")


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else ""
    if which == "xtts":
        download_xtts()
    elif which == "cosyvoice":
        download_cosyvoice()
    else:
        print(__doc__)
