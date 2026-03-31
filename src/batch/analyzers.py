"""Pluggable transcript analyzers for batch workflows."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


def _to_hhmmss(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _pick_key_lines(transcript_text: str, segments: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()

    if segments:
        for seg in segments:
            text = str(seg.get("text", "")).strip()
            if len(text) < 8:
                continue
            key = text[:80]
            if key in seen:
                continue
            seen.add(key)
            candidates.append({
                "text": text,
                "start": float(seg.get("start", 0)),
                "end": float(seg.get("end", 0)),
            })
            if len(candidates) >= limit:
                return candidates

    for raw in transcript_text.splitlines():
        text = raw.strip()
        if len(text) < 8:
            continue
        key = text[:80]
        if key in seen:
            continue
        seen.add(key)
        candidates.append({"text": text, "start": 0.0, "end": 0.0})
        if len(candidates) >= limit:
            break

    return candidates


@dataclass(slots=True)
class SimpleTranscriptAnalyzer:
    """Deterministic local analyzer used as default fallback.

    It produces a timeline and key ideas without external paid APIs.
    Workflows can replace this with another analyzer implementation later.
    """

    def analyze(
        self,
        transcript_text: str,
        segments: list[dict[str, Any]],
        title: str,
        duration: int | float | str,
    ) -> tuple[str, str]:
        outline = self._build_outline(segments=segments, transcript_text=transcript_text, title=title)
        key_ideas = self._build_key_ideas(transcript_text=transcript_text, segments=segments)
        return outline, key_ideas

    def _build_outline(self, segments: list[dict[str, Any]], transcript_text: str, title: str) -> str:
        if not segments:
            preview = [x.strip() for x in transcript_text.splitlines() if x.strip()][:4]
            points = "\n".join(f"- {x}" for x in preview) if preview else "- 文本较短，建议人工复核原视频。"
            return (
                "```mermaid\n"
                "timeline\n"
                f"    title {title[:40]} 时间轴\n"
                "    00:00:00-00:00:00 : 文本概览\n"
                "              : 未获得有效分段时间戳\n"
                "```\n\n"
                f"{points}"
            )

        n = len(segments)
        phases = min(6, max(4, n // 12 if n >= 12 else 4))
        phases = min(phases, n)
        chunk = max(1, math.ceil(n / phases))

        lines = ["```mermaid", "timeline", f"    title {title[:40]} 时间轴"]
        for i in range(0, n, chunk):
            block = segments[i : i + chunk]
            start = float(block[0].get("start", 0))
            end = float(block[-1].get("end", start))
            sample = str(block[0].get("text", "")).strip().replace("\n", " ")
            sample = sample[:24] if sample else "内容推进"
            stage_no = i // chunk + 1
            lines.append(f"    {_to_hhmmss(start)}-{_to_hhmmss(end)} : 阶段{stage_no}")
            lines.append(f"              : {sample}")

        lines.append("```")
        return "\n".join(lines)

    def _build_key_ideas(self, transcript_text: str, segments: list[dict[str, Any]]) -> str:
        lines = _pick_key_lines(transcript_text, segments, limit=5)
        if not lines:
            return "1. **观点**: 文本内容不足，建议补充字幕后重试。"

        out: list[str] = []
        for idx, item in enumerate(lines, start=1):
            quote = item["text"]
            quote = quote[:80] + ("..." if len(quote) > 80 else "")
            out.append(f"{idx}. **观点**: 该片段体现了视频中的关键表达。")
            out.append(f"   > 关联发言: \"{quote}\"")
            if item["end"] > item["start"]:
                out.append(f"   > 时间: {_to_hhmmss(item['start'])}-{_to_hhmmss(item['end'])}")
            out.append("")

        return "\n".join(out).strip()
