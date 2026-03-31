"""Ports for reusable batch workflows."""

from __future__ import annotations

from typing import Protocol

from .models import BatchJobConfig, BatchRunResult, VideoCandidate, VideoProcessResult


class CandidateProvider(Protocol):
    """Discover candidates for one workflow input."""

    async def discover(self) -> list[VideoCandidate]:
        ...


class Selector(Protocol):
    """Select final BVID set from candidates."""

    def select(self, candidates: list[VideoCandidate]) -> list[str]:
        ...


class VideoProcessor(Protocol):
    """Process one selected video."""

    async def process_one(self, bvid: str, config: BatchJobConfig) -> VideoProcessResult:
        ...


class ResultReporter(Protocol):
    """Render final output object for CLI/Agent."""

    def build(self, run_result: BatchRunResult) -> dict:
        ...
