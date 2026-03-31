"""音频下载与 CPU 转写（无字幕时的兜底方案）."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .config import TMP_DIR, WHISPER_MODEL


def _ensure_tmp() -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    return TMP_DIR


# ── 音频下载 ──────────────────────────────────────────
def download_audio(bvid: str) -> Path:
    """用 yt-dlp 下载视频音频轨到临时目录，返回 wav 文件路径."""
    tmp = _ensure_tmp()
    out_path = tmp / f"{bvid}.wav"

    if out_path.exists():
        return out_path

    url = f"https://www.bilibili.com/video/{bvid}"
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format", "wav",
        "-o", str(tmp / f"{bvid}.%(ext)s"),
        "--no-playlist",
        "--quiet",
        url,
    ]
    subprocess.run(cmd, check=True)

    # yt-dlp 可能生成中间格式再转换，找到最终 wav
    if not out_path.exists():
        # 查找同名任意音频文件
        for f in tmp.glob(f"{bvid}.*"):
            if f.suffix in (".wav", ".m4a", ".mp3", ".opus", ".webm"):
                if f.suffix != ".wav":
                    # ffmpeg 转换为 wav
                    subprocess.run(
                        ["ffmpeg", "-i", str(f), "-ar", "16000", "-ac", "1", str(out_path), "-y"],
                        check=True, capture_output=True,
                    )
                    f.unlink()
                else:
                    out_path = f
                break

    if not out_path.exists():
        raise FileNotFoundError(f"音频下载失败: {bvid}")
    return out_path


# ── Whisper 转写 ──────────────────────────────────────
def transcribe(audio_path: Path, model_size: str = WHISPER_MODEL) -> dict[str, Any]:
    """用 faster-whisper 在 CPU 上转写音频，返回结构化结果."""
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    segments_iter, info = model.transcribe(
        str(audio_path),
        language="zh",
        vad_filter=True,           # 开启 VAD 防幻觉
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )

    segments = []
    lines = []
    for seg in segments_iter:
        segments.append({
            "start": round(seg.start, 2),
            "end": round(seg.end, 2),
            "text": seg.text.strip(),
        })
        lines.append(seg.text.strip())

    return {
        "text": "\n".join(lines),
        "segments": segments,
        "language": info.language,
        "duration": round(info.duration, 1),
    }


# ── 完整流程：下载 + 转写 ────────────────────────────
def download_and_transcribe(bvid: str) -> dict[str, Any]:
    """下载音频并转写，完成后清理临时文件."""
    audio_path = download_audio(bvid)
    try:
        result = transcribe(audio_path)
    finally:
        # 清理临时音频
        if audio_path.exists():
            audio_path.unlink()
    return result


# ── CLI ───────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python -m src.audio_transcriber <bvid>")
        sys.exit(1)

    bvid = sys.argv[1]
    result = download_and_transcribe(bvid)
    print(json.dumps(result, ensure_ascii=False, indent=2))
