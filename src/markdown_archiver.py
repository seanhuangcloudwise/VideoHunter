"""Markdown 归档：单视频文档生成与主题汇总表维护."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import OUTPUT_DIR, KEEP_FULL_TEXT, AUTO_ADD_IDEA_TIME


def _sanitize_dirname(name: str) -> str:
    """将主题名转为安全目录名."""
    name = re.sub(r'[\\/:*?"<>|]', "_", name)
    return name.strip()[:80]


def _sanitize_filename(author: str, title: str) -> str:
    """生成安全的文件名 stem：[author] title"""
    raw = f"[{author}] {title}"
    safe = re.sub(r'[\\/:*?"<>|\0]', "_", raw)
    return safe.strip()[:120]


def _topic_dir(topic: str) -> Path:
    d = OUTPUT_DIR / _sanitize_dirname(topic)
    d.mkdir(parents=True, exist_ok=True)
    return d


def _video_docs(topic: str):
    """Yield all video .md files (excludes _index.md) under a topic dir."""
    d = _topic_dir(topic)
    return [p for p in d.glob("*.md") if p.name != "_index.md"]


def is_video_processed(bvid: str, topic: str) -> bool:
    """Return whether one BVID has already been archived under a topic."""
    for md in _video_docs(topic):
        text = md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        if fm.get("bvid") == bvid:
            return True
    return False


def list_processed_bvids(topic: str) -> set[str]:
    """Return all archived BVIDs under a topic directory."""
    result: set[str] = set()
    for md in _video_docs(topic):
        text = md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        bvid = fm.get("bvid", "")
        if bvid:
            result.add(bvid)
    return result


def _to_hhmmss(seconds: float) -> str:
    total = max(0, int(seconds))
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+|[，。！？、,.!?:;\-—\"'“”‘’（）()【】\[\]]", "", text)


def _find_time_range_for_quote(
    quote: str,
    transcript_segments: list[dict[str, Any]],
) -> tuple[str, str] | None:
    if not quote or not transcript_segments:
        return None

    nq = _normalize_text(quote)
    if len(nq) < 4:
        return None

    best_idx = -1
    best_score = 0

    for idx, seg in enumerate(transcript_segments):
        seg_text = _normalize_text(str(seg.get("text", "")))
        if not seg_text:
            continue

        score = 0
        if nq in seg_text or seg_text in nq:
            score = min(len(nq), len(seg_text))
        else:
            # 用滑窗子串匹配，降低转写差异的影响
            window = nq[:12] if len(nq) >= 12 else nq
            if window and window in seg_text:
                score = len(window)

        if score > best_score:
            best_score = score
            best_idx = idx

    if best_idx < 0:
        return None

    start = float(transcript_segments[best_idx].get("start", 0))
    end = float(transcript_segments[best_idx].get("end", start))

    # 适度扩展到相邻片段，提升可读性
    if best_idx + 1 < len(transcript_segments):
        next_end = float(transcript_segments[best_idx + 1].get("end", end))
        end = max(end, next_end)

    return _to_hhmmss(start), _to_hhmmss(end)


def _inject_time_for_key_ideas(
    key_ideas: str,
    transcript_segments: list[dict[str, Any]] | None,
) -> str:
    if not key_ideas or not transcript_segments:
        return key_ideas

    lines = key_ideas.splitlines()
    out: list[str] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        out.append(line)

        if "> 关联发言:" in line:
            has_time_next = i + 1 < len(lines) and "> 时间:" in lines[i + 1]
            if not has_time_next:
                quote = line.split(":", 1)[1].strip().strip('"')
                time_range = _find_time_range_for_quote(quote, transcript_segments)
                if time_range:
                    out.append(f"   > 时间: {time_range[0]}-{time_range[1]}")

        i += 1

    return "\n".join(out)


# ── 单视频文档 ────────────────────────────────────────
def write_video_doc(
    topic: str,
    meta: dict[str, Any],
    outline: str,
    key_ideas: str,
    transcript_text: str,
    transcript_segments: list[dict[str, Any]] | None = None,
    source_type: str = "subtitle",
    include_full_text: bool | None = None,
    auto_add_idea_time: bool | None = None,
) -> Path:
    """
    写入单个视频的 Markdown 解析文档。

    Args:
        topic:           主题名称
        meta:            视频元数据 (title, author, bvid, url, duration, pubdate, ...)
        outline:         LLM 生成的分层提纲（Markdown 格式）
        key_ideas:       LLM 生成的中心思想（Markdown 格式）
        transcript_text: 完整字幕/转写文本
        transcript_segments: 结构化分段文本（用于自动补全时间范围）
        source_type:     "subtitle" | "transcribe"
        include_full_text: 是否保留完整文本，None 时读取全局配置 KEEP_FULL_TEXT
        auto_add_idea_time: 是否自动补全观点时间范围，None 时读取配置 AUTO_ADD_IDEA_TIME

    Returns:
        写入的文件路径
    """
    d = _topic_dir(topic)
    bvid = meta.get("bvid", "unknown")
    author = meta.get("author", "")
    title = meta.get("title", bvid)
    filepath = d / f"{_sanitize_filename(author, title)}.md"

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration = meta.get("duration", 0)
    if isinstance(duration, (int, float)):
        mins, secs = divmod(int(duration), 60)
        duration_str = f"{mins}分{secs}秒"
    else:
        duration_str = str(duration)

    keep_text = KEEP_FULL_TEXT if include_full_text is None else include_full_text
    add_time = AUTO_ADD_IDEA_TIME if auto_add_idea_time is None else auto_add_idea_time
    final_key_ideas = _inject_time_for_key_ideas(key_ideas, transcript_segments) if add_time else key_ideas

    if keep_text:
        full_text_section = f"""
---

## 完整文本

<details>
<summary>展开查看完整{('字幕' if source_type == 'subtitle' else '转写')}文本</summary>

{transcript_text}

</details>
"""
    else:
        full_text_section = """
---

## 完整文本

_已按用户选择省略完整文本，仅保留提纲与核心观点。_
"""

    content = f"""---
bvid: "{bvid}"
title: "{meta.get('title', '')}"
author: "{meta.get('author', '')}"
url: "{meta.get('url', '')}"
duration: "{duration_str}"
pubdate: "{meta.get('pubdate', '')}"
source: "{source_type}"
analyzed_at: "{now}"
keep_full_text: "{str(keep_text).lower()}"
---

# [{meta.get('author', '')}] {meta.get('title', bvid)}

> **UP主**: {meta.get('author', '')} | **时长**: {duration_str} | **播放**: {meta.get('view', meta.get('play', ''))}
>
> **链接**: {meta.get('url', '')}

---

## 中心思想

{final_key_ideas}

---

## 视频时间轴图

{outline}

{full_text_section}

---

_解析时间: {now} | 文本来源: {source_type}_
"""
    filepath.write_text(content, encoding="utf-8")
    return filepath


# ── 主题汇总表 ────────────────────────────────────────
def update_topic_index(topic: str) -> Path:
    """
    扫描主题目录下所有视频 md 文件，重建 _index.md 汇总表。
    幂等操作：每次调用都重新生成。
    """
    d = _topic_dir(topic)
    index_path = d / "_index.md"

    video_docs = sorted(p for p in d.glob("*.md") if p.name != "_index.md")
    if not video_docs:
        index_path.write_text(f"# {topic}\n\n_暂无已解析视频。_\n", encoding="utf-8")
        return index_path

    rows = []
    for doc in video_docs:
        # 从 frontmatter 提取元数据
        text = doc.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        title = fm.get("title", doc.stem)
        author = fm.get("author", "")
        duration = fm.get("duration", "")
        source = fm.get("source", "")
        analyzed_at = fm.get("analyzed_at", "")
        bvid = fm.get("bvid", doc.stem)
        rows.append(f"| [{title}]({doc.name}) | {author} | {duration} | {source} | {analyzed_at} |")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    table = "\n".join(rows)

    content = f"""---
topic: "{topic}"
video_count: {len(video_docs)}
updated_at: "{now}"
---

# {topic} — 视频解析汇总

> 共 **{len(video_docs)}** 个视频 | 最后更新: {now}

| 视频标题 | UP主 | 时长 | 来源 | 解析时间 |
|----------|------|------|------|----------|
{table}
"""
    index_path.write_text(content, encoding="utf-8")
    return index_path


def _parse_frontmatter(text: str) -> dict[str, str]:
    """简易解析 YAML frontmatter."""
    fm: dict[str, str] = {}
    if not text.startswith("---"):
        return fm
    parts = text.split("---", 2)
    if len(parts) < 3:
        return fm
    for line in parts[1].strip().splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            fm[key.strip()] = val.strip().strip('"')
    return fm
