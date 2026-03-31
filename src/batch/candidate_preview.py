"""Helpers to preview selectable candidates for Agent/CLI flows."""

from __future__ import annotations

from .providers import SearchUrlCandidateProvider


async def build_search_url_preview(search_url: str, default_top_n: int = 10, limit: int = 50) -> dict:
    """Return candidate list for one page with default selection marks."""
    provider = SearchUrlCandidateProvider(search_url=search_url, limit=limit)
    candidates = await provider.discover()

    items = []
    for idx, item in enumerate(candidates, start=1):
        label = f"[{item.author}] {item.title}"
        items.append(
            {
                "index": idx,
                "selected": idx <= default_top_n,
                "bvid": item.bvid,
                # label is what vscode_askQuestions returns as the selected value
                "label": label,
                "description": f"{item.bvid} · {item.duration}",
                "author": item.author,
                "url": item.url,
            }
        )

    return {
        "found_on_page": len(items),
        "default_selected": min(default_top_n, len(items)),
        "items": items,
        "selection_hint": "选择后 Agent 会自动从 items 列表中将选中的标题映射回 BVID 再执行批处理。",
    }
