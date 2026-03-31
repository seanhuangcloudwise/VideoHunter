"""B站视频搜索、元数据获取、字幕提取."""

from __future__ import annotations

import asyncio
import json
import re
import sys
from urllib.parse import parse_qs, urlparse
from typing import Any

from bilibili_api import search, video, Credential

from .config import BILIBILI_SESSDATA, SEARCH_LIMIT


# ── 凭证 ──────────────────────────────────────────────
def _credential() -> Credential | None:
    if BILIBILI_SESSDATA:
        return Credential(sessdata=BILIBILI_SESSDATA)
    return None


# ── 工具：BVID 解析 ──────────────────────────────────
_BV_PATTERN = re.compile(r"(BV[\w]{10})")


def extract_bvid(url_or_bvid: str) -> str | None:
    """从 URL 或纯 BVID 字符串中提取 BVID."""
    m = _BV_PATTERN.search(url_or_bvid)
    return m.group(1) if m else None


# ── 搜索视频 ──────────────────────────────────────────
async def search_videos(keyword: str, limit: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
    """按关键词搜索B站视频，返回精简元数据列表."""
    return await search_videos_page(keyword=keyword, page=1, limit=limit)


def parse_search_url(url: str) -> dict[str, Any]:
    """解析 B站搜索 URL，提取查询参数.

    Returns:
        {
            "keyword": str,
            "order": str,
            "duration": str,
            "page": int,
            "url": str,
        }
    """
    parsed = urlparse(url)
    is_search_domain = parsed.netloc in ("search.bilibili.com", "www.bilibili.com")
    is_search_path = parsed.path in ("/all", "/", "") or parsed.path.startswith("/search")
    if not is_search_domain or not is_search_path:
        raise ValueError(f"不是有效的B站搜索结果URL: {url}")

    query = parse_qs(parsed.query)
    keyword = (query.get("keyword", [""])[0] or "").strip()
    if not keyword:
        raise ValueError(f"搜索URL缺少 keyword 参数: {url}")

    page_raw = (query.get("p", ["1"])[0] or "1").strip()
    try:
        page = int(page_raw)
    except ValueError as exc:
        raise ValueError(f"搜索URL中的页码 p 非法: {page_raw}") from exc

    if page < 1:
        page = 1

    return {
        "keyword": keyword,
        "order": (query.get("order", [""])[0] or "").strip(),
        "duration": (query.get("duration", [""])[0] or "").strip(),
        "page": page,
        "url": url,
    }


async def search_videos_page(keyword: str, page: int = 1, limit: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
    """按关键词搜索指定页的视频，返回精简元数据列表."""
    resp = await search.search_by_type(
        keyword=keyword,
        search_type=search.SearchObjectType.VIDEO,
        page=page,
    )
    results = []
    for item in resp.get("result", [])[:limit]:
        # 清理 HTML 标签
        title = re.sub(r"<.*?>", "", item.get("title", ""))
        results.append({
            "bvid": item.get("bvid", ""),
            "title": title,
            "author": item.get("author", ""),
            "duration": item.get("duration", ""),
            "play": item.get("play", 0),
            "pubdate": item.get("pubdate", ""),
            "description": item.get("description", ""),
            "url": f"https://www.bilibili.com/video/{item.get('bvid', '')}",
        })
    return results


async def search_videos_from_url(search_url: str, limit: int = SEARCH_LIMIT) -> list[dict[str, Any]]:
    """从 B站搜索 URL 拉取当前页视频列表。"""
    parsed = parse_search_url(search_url)
    return await search_videos_page(
        keyword=parsed["keyword"],
        page=parsed["page"],
        limit=limit,
    )


# ── 获取视频详情 ──────────────────────────────────────
async def fetch_video_info(bvid: str) -> dict[str, Any]:
    """获取单个视频的完整元数据."""
    v = video.Video(bvid=bvid, credential=_credential())
    info = await v.get_info()
    return {
        "bvid": bvid,
        "title": info.get("title", ""),
        "author": info.get("owner", {}).get("name", ""),
        "duration": info.get("duration", 0),
        "pubdate": info.get("pubdate", ""),
        "description": info.get("desc", ""),
        "view": info.get("stat", {}).get("view", 0),
        "like": info.get("stat", {}).get("like", 0),
        "url": f"https://www.bilibili.com/video/{bvid}",
        "cid": info.get("cid", 0),
        "pages": info.get("pages", []),
    }


# ── 获取字幕文本 ──────────────────────────────────────
async def fetch_subtitle(bvid: str, cid: int | None = None) -> dict[str, Any]:
    """尝试获取视频字幕，返回 {"found": bool, "text": str, "segments": list}.

    策略（按优先级）：
    1. bilibili-api 内置 get_subtitle（CC字幕）
    2. dm/view 弹幕接口（AI 自动字幕，最可靠）
    3. player API 直取

    所有自定义 HTTP 请求均复用 bilibili-api 内部 session，
    避免因新建 httpx.AsyncClient 读取系统代理配置导致的 TLS 握手超时。
    """
    from bilibili_api.utils.network import get_client

    _UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    v = video.Video(bvid=bvid, credential=_credential())

    if cid is None:
        info = await v.get_info()
        cid = info.get("cid", 0)

    # 获取 aid（dm/view 接口需要）
    aid = None
    try:
        vinfo = await v.get_info()
        aid = vinfo.get("aid")
    except Exception:
        pass

    subtitles = []

    # 复用 bilibili-api 内部 session（已正确配置代理/timeout）
    bili_session = get_client().get_wrapped_session()

    # ── 方式 1：bilibili-api 内置接口（CC字幕）──
    try:
        subtitle_info = await v.get_subtitle(cid)
        subtitles = subtitle_info.get("subtitles", [])
    except Exception:
        pass

    # ── 方式 2：dm/view 弹幕接口（AI 自动字幕，最可靠）──
    if not subtitles and aid:
        try:
            headers = {
                "User-Agent": _UA,
                "Referer": f"https://www.bilibili.com/video/{bvid}",
            }
            if BILIBILI_SESSDATA:
                headers["Cookie"] = f"SESSDATA={BILIBILI_SESSDATA}"
            resp = await bili_session.get(
                f"https://api.bilibili.com/x/v2/dm/view?type=1&oid={cid}&pid={aid}",
                headers=headers,
            )
            dm_data = resp.json()
            subtitles = dm_data.get("data", {}).get("subtitle", {}).get("subtitles", [])
        except Exception:
            pass

    # ── 方式 3：player API ──
    if not subtitles:
        try:
            headers = {
                "User-Agent": _UA,
                "Referer": "https://www.bilibili.com",
            }
            if BILIBILI_SESSDATA:
                headers["Cookie"] = f"SESSDATA={BILIBILI_SESSDATA}"
            resp = await bili_session.get(
                f"https://api.bilibili.com/x/player/v2?bvid={bvid}&cid={cid}",
                headers=headers,
            )
            pdata = resp.json()
            subtitles = pdata.get("data", {}).get("subtitle", {}).get("subtitles", [])
        except Exception:
            pass

    if not subtitles:
        return {"found": False, "text": "", "segments": []}

    # 优先中文字幕
    chosen = subtitles[0]
    for s in subtitles:
        if "zh" in s.get("lan", ""):
            chosen = s
            break

    subtitle_url = chosen.get("subtitle_url", "")
    if not subtitle_url:
        return {"found": False, "text": "", "segments": []}

    # 确保 URL 有 https 协议前缀
    if subtitle_url.startswith("http://"):
        subtitle_url = "https://" + subtitle_url[7:]
    elif subtitle_url.startswith("//"):
        subtitle_url = "https:" + subtitle_url

    headers = {"User-Agent": _UA, "Referer": f"https://www.bilibili.com/video/{bvid}"}
    if BILIBILI_SESSDATA:
        headers["Cookie"] = f"SESSDATA={BILIBILI_SESSDATA}"

    resp = await bili_session.get(subtitle_url, headers=headers)
    data = resp.json()

    segments = []
    lines = []
    for item in data.get("body", []):
        text = item.get("content", "")
        start = item.get("from", 0)
        end = item.get("to", 0)
        segments.append({"start": start, "end": end, "text": text})
        lines.append(text)

    return {
        "found": True,
        "text": "\n".join(lines),
        "segments": segments,
        "language": chosen.get("lan", "unknown"),
    }


# ── CLI 封装 ──────────────────────────────────────────
def _run(coro):
    return asyncio.run(coro)


def cli_search(keyword: str, limit: int = SEARCH_LIMIT) -> str:
    """CLI: 搜索视频并返回 JSON."""
    results = _run(search_videos(keyword, limit))
    return json.dumps(results, ensure_ascii=False, indent=2)


def cli_fetch_info(bvid: str) -> str:
    """CLI: 获取视频详情并返回 JSON."""
    info = _run(fetch_video_info(bvid))
    return json.dumps(info, ensure_ascii=False, indent=2)


def cli_fetch_subtitle(bvid: str) -> str:
    """CLI: 获取字幕并返回 JSON."""
    result = _run(fetch_subtitle(bvid))
    return json.dumps(result, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    # 支持直接调用：python -m src.bilibili_client search <keyword>
    #               python -m src.bilibili_client info <bvid>
    #               python -m src.bilibili_client subtitle <bvid>
    if len(sys.argv) < 3:
        print("用法: python -m src.bilibili_client <search|info|subtitle> <keyword_or_bvid>")
        sys.exit(1)

    cmd, arg = sys.argv[1], sys.argv[2]
    if cmd == "search":
        print(cli_search(arg))
    elif cmd == "info":
        print(cli_fetch_info(arg))
    elif cmd == "subtitle":
        print(cli_fetch_subtitle(arg))
    else:
        print(f"未知命令: {cmd}")
        sys.exit(1)
