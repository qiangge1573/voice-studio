"""视频处理：ffmpeg 定位、台本解析、配音混音渲染。

ffmpeg 获取优先级：系统 PATH -> imageio-ffmpeg（pip 自带静态二进制）。
"""
import json
import os
import re
import shutil
import subprocess
from typing import List, Optional

TIMESTAMP_RE = re.compile(r"^\[(\d{1,2}):(\d{2})(?:\.(\d+))?\]\s*(.*)$")


def ffmpeg_exe() -> Optional[str]:
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def ffprobe_exe() -> Optional[str]:
    path = shutil.which("ffprobe")
    if path:
        return path
    # imageio-ffmpeg 通常不带 ffprobe，仅在极少数发行版附带时使用
    try:
        import imageio_ffmpeg
        exe = imageio_ffmpeg.get_ffmpeg_exe()
        probe = os.path.join(os.path.dirname(exe), os.path.basename(exe).replace("ffmpeg", "ffprobe"))
        return probe if os.path.exists(probe) else None
    except Exception:
        return None


def video_duration(video_path: str) -> float:
    """视频时长（秒）。优先 ffprobe，退化用 ffmpeg -i 的 stderr 解析。"""
    probe = ffprobe_exe()
    if probe:
        try:
            out = subprocess.run(
                [probe, "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                capture_output=True, text=True, timeout=30,
            )
            return round(float(out.stdout.strip()), 2)
        except Exception:
            pass
    exe = ffmpeg_exe()
    if exe:
        try:
            proc = subprocess.run([exe, "-i", video_path], capture_output=True, text=True, timeout=30)
            m = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", proc.stderr)
            if m:
                h, mn, s = int(m.group(1)), int(m.group(2)), float(m.group(3))
                return round(h * 3600 + mn * 60 + s, 2)
        except Exception:
            pass
    return 0.0


def video_has_audio(video_path: str) -> bool:
    probe = ffprobe_exe()
    if not probe:
        return True  # 无法探测时按有音轨处理，出错再报
    try:
        out = subprocess.run(
            [probe, "-v", "quiet", "-select_streams", "a", "-show_entries",
             "stream=index", "-of", "csv=p=0", video_path],
            capture_output=True, text=True, timeout=30,
        )
        return bool(out.stdout.strip())
    except Exception:
        return True


def parse_script(script: str) -> List[dict]:
    """解析配音台本：每行一条。

    支持两种写法（可混用）：
      "[mm:ss] 文本"   —— 锚定到指定时间点开始配音
      "文本"           —— 顺序接续（从上一段结束处开始，第一段从 0 开始）
    返回 [{"text": str, "anchor": float|None}]
    """
    items: List[dict] = []
    for line in (script or "").splitlines():
        line = line.strip()
        if not line:
            continue
        m = TIMESTAMP_RE.match(line)
        if m:
            sec = int(m.group(1)) * 60 + int(m.group(2))
            if m.group(3):
                sec += float("0." + m.group(3))
            items.append({"text": m.group(4).strip(), "anchor": sec})
        else:
            items.append({"text": line, "anchor": None})
    return [it for it in items if it["text"]]


def _ffmpeg_cmd(exe: str, video_path: str, seg_inputs: List[str], starts_ms: List[int],
                mode: str, video_has_audio: bool, output: str) -> List[str]:
    """构造混音命令：每个片段 adelay 定位 -> amix 成配音轨 -> 与原音轨混合。"""
    cmd = [exe, "-y"]
    cmd += ["-i", video_path]
    for seg in seg_inputs:
        cmd += ["-i", seg]

    n = len(seg_inputs)
    filters = []
    for i in range(n):
        filters.append(
            f"[{i + 1}:a]adelay=delays={starts_ms[i]}:all=1[a{i}]"
        )
    voice_in = "".join(f"[a{i}]" for i in range(n))
    filters.append(f"{voice_in}amix=inputs={n}:normalize=0[voice]")

    if mode == "overlay" and video_has_audio:
        filters.append("[0:a]volume=0.25[orig]")
        filters.append("[orig][voice]amix=inputs=2:normalize=0[aout]")
        audio_map = "[aout]"
    elif mode == "replace" or not video_has_audio:
        audio_map = "[voice]"
    else:
        audio_map = "[voice]"

    cmd += ["-filter_complex", ";".join(filters)]
    cmd += ["-map", "0:v", "-map", audio_map]
    cmd += ["-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest", output]
    return cmd


def render_dubbing(video_path: str, segments: List[dict], mode: str, output: str) -> None:
    """把配音片段按时间轴混入视频。

    segments: [{"audio_path": str, "anchor": float|None, "text": str}]
    mode: overlay(叠加,压低原声) / replace(替换原音轨)
    """
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("缺少 ffmpeg：请安装（brew install ffmpeg）或 pip install imageio-ffmpeg")

    from .audio_utils import audio_duration

    # 计算每段的实际起点：锚点优先，否则顺序接续
    cursor = 0.0
    seg_inputs, starts_ms = [], []
    for seg in segments:
        dur = audio_duration(seg["audio_path"])
        start = seg["anchor"] if seg.get("anchor") is not None else cursor
        if seg["anchor"] is not None and seg["anchor"] < cursor:
            start = cursor  # 锚点早于上一段结束，顺延
        seg_inputs.append(seg["audio_path"])
        starts_ms.append(int(start * 1000))
        cursor = start + dur

    has_audio = video_has_audio(video_path)
    cmd = _ffmpeg_cmd(exe, video_path, seg_inputs, starts_ms, mode, has_audio, output)
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if proc.returncode != 0 or not os.path.exists(output):
        raise RuntimeError(f"ffmpeg 混音失败: {proc.stderr[-400:]}")
