"""音频下载与 CPU 转写（无字幕时的兜底方案）."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any

from .config import TMP_DIR, WHISPER_MODEL


def _ensure_tmp() -> Path:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    return TMP_DIR


# ── 音频下载 ──────────────────────────────────────────
async def _download_audio_async(bvid: str, out_m4a: Path) -> None:
    """用 bilibili-api 获取音频流 URL，并通过内部 session 下载保存为 m4a。"""
    from bilibili_api import video
    from bilibili_api.utils.network import get_client
    from .bilibili_client import _credential

    _UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    v = video.Video(bvid=bvid, credential=_credential())
    info = await v.get_info()
    cid = info.get("cid")

    url_data = await v.get_download_url(cid=cid)
    dash = url_data.get("dash", {})
    audio_tracks = dash.get("audio", []) or []
    if not audio_tracks:
        raise RuntimeError(f"未找到音频流: {bvid}")

    best = sorted(audio_tracks, key=lambda x: x.get("bandwidth", 0), reverse=True)[0]
    audio_url = best.get("baseUrl") or best.get("base_url") or (best.get("backupUrl") or [""])[0]
    if not audio_url:
        raise RuntimeError(f"音频流 URL 为空: {bvid}")

    session = get_client().get_wrapped_session()
    headers = {
        "User-Agent": _UA,
        "Referer": f"https://www.bilibili.com/video/{bvid}",
    }
    resp = await session.get(audio_url, headers=headers)
    out_m4a.write_bytes(resp.content)


def download_audio(bvid: str) -> Path:
    """下载视频音频轨到临时目录，返回音频文件路径（m4a）。

    使用 bilibili-api 内部 session 下载音频流，无需 ffmpeg。
    """
    tmp = _ensure_tmp()
    out_wav = tmp / f"{bvid}.wav"

    if out_wav.exists():
        return out_wav

    # faster-whisper 底层用 av 库，直接支持 m4a，无需 ffmpeg 转码
    out_m4a = tmp / f"{bvid}.m4a"
    if not out_m4a.exists():
        asyncio.run(_download_audio_async(bvid, out_m4a))
    return out_m4a


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
