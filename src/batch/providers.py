"""Candidate providers for batch workflows."""

from __future__ import annotations

from dataclasses import dataclass

from .models import VideoCandidate
from ..bilibili_client import parse_search_url, search_videos_page


@dataclass(slots=True)
class SearchUrlCandidateProvider:
    """Discover candidates from one Bilibili search page URL."""

    search_url: str
    limit: int = 50

    async def discover(self) -> list[VideoCandidate]:
        parsed = parse_search_url(self.search_url)
        keyword = parsed["keyword"]
        page = parsed["page"]

        # Current workflow intentionally processes only the current page.
        raw_items = await search_videos_page(keyword=keyword, limit=self.limit, page=page)

        out: list[VideoCandidate] = []
        seen: set[str] = set()
        for item in raw_items:
            bvid = item.get("bvid", "")
            if not bvid or bvid in seen:
                continue
            seen.add(bvid)
            out.append(
                VideoCandidate(
                    bvid=bvid,
                    title=item.get("title", ""),
                    author=item.get("author", ""),
                    duration=str(item.get("duration", "")),
                    url=item.get("url", ""),
                    raw=item,
                )
            )
        return out
