"""音频工具：扩展名校验、时长探测、可选 ffmpeg 归一化。"""
import os
import re
import shutil
import subprocess
import wave
from typing import Optional

ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".pcm"}
_EXT_RE = re.compile(r"\.([a-zA-Z0-9]+)$")


def safe_ext(filename: str) -> Optional[str]:
    m = _EXT_RE.search(filename or "")
    if not m:
        return None
    ext = "." + m.group(1).lower()
    return ext if ext in ALLOWED_AUDIO_EXT else None


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def audio_duration(path: str) -> float:
    """尽力获取音频时长（秒）。wav 用标准库；其余用 ffprobe；都失败返回 0。"""
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        try:
            with wave.open(path, "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                return round(frames / rate, 2) if rate else 0.0
        except Exception:
            pass
    if shutil.which("ffprobe"):
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", path],
                capture_output=True, text=True, timeout=15,
            )
            return round(float(out.stdout.strip()), 2)
        except Exception:
            pass
    return 0.0


def media_type(path: str) -> str:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".wav":
        return "audio/wav"
    if ext == ".mp3":
        return "audio/mpeg"
    if ext == ".m4a":
        return "audio/mp4"
    return "application/octet-stream"


def to_wav_mono(src: str, dst: str, sample_rate: int = 22050) -> str:
    """用 ffmpeg 归一化为单声道 wav（XTTS 需要的输入格式）。无 ffmpeg 时原样返回。"""
    if not ffmpeg_available():
        return src
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-i", src, "-ac", "1", "-ar", str(sample_rate), dst],
            capture_output=True, timeout=60, check=True,
        )
        return dst
    except Exception:
        return src
