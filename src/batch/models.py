"""Domain models for reusable batch video processing."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class VideoStatus(str, Enum):
    """Lifecycle status for one candidate in a batch run."""

    DISCOVERED = "discovered"
    SELECTED = "selected"
    PROCESSING = "processing"
    DONE = "done"
    SKIPPED = "skipped"
    FAILED = "failed"


class FailureType(str, Enum):
    """Normalized failure categories for reporting and retries."""

    FETCH_FAILED = "fetch_failed"
    NO_SUBTITLE = "no_subtitle"
    ANALYSIS_FAILED = "analysis_failed"
    ARCHIVE_FAILED = "archive_failed"
    UNEXPECTED = "unexpected"


@dataclass(slots=True)
class VideoCandidate:
    """Video candidate discovered from any source provider."""

    bvid: str
    title: str
    author: str
    duration: str
    url: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BatchJobConfig:
    """Config for one batch run."""

    topic: str
    skip_existing: bool = True
    subtitle_policy: str = "skip_no_subtitle"
    default_top_n: int = 10
    include_full_text: bool | None = None
    auto_add_idea_time: bool | None = None


@dataclass(slots=True)
class VideoProcessResult:
    """Execution result for a single video in the batch."""

    bvid: str
    status: VideoStatus
    reason: str = ""
    failure_type: FailureType | None = None
    source_type: str | None = None
    output_path: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BatchRunResult:
    """Aggregated run result for one batch job."""

    source: str
    topic: str
    discovered_count: int
    selected_bvids: list[str]
    processed: list[VideoProcessResult] = field(default_factory=list)
    started_at: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    finished_at: str = ""

    def finalize(self) -> None:
        self.finished_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def summary(self) -> dict[str, Any]:
        processed = 0
        skipped_existing = 0
        skipped_no_subtitle = 0
        failed = 0
        done_items: list[str] = []

        for item in self.processed:
            if item.status == VideoStatus.DONE:
                processed += 1
                done_items.append(item.bvid)
            elif item.status == VideoStatus.SKIPPED:
                if item.failure_type == FailureType.NO_SUBTITLE:
                    skipped_no_subtitle += 1
                else:
                    skipped_existing += 1
            elif item.status == VideoStatus.FAILED:
                failed += 1

        return {
            "source": self.source,
            "topic": self.topic,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "found_on_page": self.discovered_count,
            "selected": len(self.selected_bvids),
            "processed": processed,
            "skipped_existing": skipped_existing,
            "skipped_no_subtitle": skipped_no_subtitle,
            "failed": failed,
            "done_bvids": done_items,
            "selected_bvids": self.selected_bvids,
        }
