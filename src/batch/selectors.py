"""Selection strategies for discovered candidates."""

from __future__ import annotations

from dataclasses import dataclass

from .models import VideoCandidate


def _parse_selected_arg(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


@dataclass(slots=True)
class DefaultTopNSelector:
    """Default-select top N; optional override by indices/BVIDs."""

    top_n: int = 10
    selected_arg: str | None = None

    def select(self, candidates: list[VideoCandidate]) -> list[str]:
        if not candidates:
            return []

        if not self.selected_arg:
            return [x.bvid for x in candidates[: self.top_n]]

        tokens = _parse_selected_arg(self.selected_arg)
        bvids = {x.bvid for x in candidates}
        chosen: list[str] = []

        for token in tokens:
            if token.isdigit():
                idx = int(token)
                if 1 <= idx <= len(candidates):
                    chosen.append(candidates[idx - 1].bvid)
                continue

            if token in bvids:
                chosen.append(token)

        # preserve order, remove dup
        out: list[str] = []
        seen: set[str] = set()
        for bvid in chosen:
            if bvid not in seen:
                seen.add(bvid)
                out.append(bvid)
        return out
