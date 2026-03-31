"""Video processors for batch orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field

from .analyzers import SimpleTranscriptAnalyzer
from .models import BatchJobConfig, FailureType, VideoProcessResult, VideoStatus
from ..bilibili_client import fetch_subtitle, fetch_video_info
from ..markdown_archiver import is_video_processed, write_video_doc


@dataclass(slots=True)
class SubtitleFirstProcessor:
    """Fetch metadata + subtitle, apply skip policies.

    This processor is source-agnostic and intentionally does not do LLM analysis.
    It returns normalized status for orchestration and later workflow steps.
    """

    async def process_one(self, bvid: str, config: BatchJobConfig) -> VideoProcessResult:
        if config.skip_existing and is_video_processed(bvid, config.topic):
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.SKIPPED,
                reason="already archived",
                source_type="existing",
            )

        try:
            meta = await fetch_video_info(bvid)
        except Exception as exc:  # noqa: BLE001
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.FAILED,
                reason=f"fetch_video_info failed: {exc}",
                failure_type=FailureType.FETCH_FAILED,
            )

        try:
            subtitle = await fetch_subtitle(bvid, meta.get("cid"))
        except Exception as exc:  # noqa: BLE001
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.FAILED,
                reason=f"fetch_subtitle failed: {exc}",
                failure_type=FailureType.FETCH_FAILED,
                meta=meta,
            )

        if not subtitle.get("found"):
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.SKIPPED,
                reason="subtitle not found",
                failure_type=FailureType.NO_SUBTITLE,
                source_type="none",
                meta=meta,
            )

        return VideoProcessResult(
            bvid=bvid,
            status=VideoStatus.DONE,
            reason="subtitle fetched",
            source_type="subtitle",
            meta={
                **meta,
                "subtitle": {
                    "found": True,
                    "text": subtitle.get("text", ""),
                    "segments": subtitle.get("segments", []),
                    "language": subtitle.get("language", "unknown"),
                },
            },
        )


@dataclass(slots=True)
class ArchivingProcessor:
    """Fetch subtitle text, run analyzer, and archive markdown documents."""

    analyzer: SimpleTranscriptAnalyzer = field(default_factory=SimpleTranscriptAnalyzer)

    async def process_one(self, bvid: str, config: BatchJobConfig) -> VideoProcessResult:
        if config.skip_existing and is_video_processed(bvid, config.topic):
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.SKIPPED,
                reason="already archived",
                source_type="existing",
            )

        try:
            meta = await fetch_video_info(bvid)
        except Exception as exc:  # noqa: BLE001
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.FAILED,
                reason=f"fetch_video_info failed: {exc}",
                failure_type=FailureType.FETCH_FAILED,
            )

        try:
            subtitle = await fetch_subtitle(bvid, meta.get("cid"))
        except Exception as exc:  # noqa: BLE001
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.FAILED,
                reason=f"fetch_subtitle failed: {exc}",
                failure_type=FailureType.FETCH_FAILED,
                meta=meta,
            )

        if not subtitle.get("found"):
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.SKIPPED,
                reason="subtitle not found",
                failure_type=FailureType.NO_SUBTITLE,
                source_type="none",
                meta=meta,
            )

        transcript_text = subtitle.get("text", "")
        transcript_segments = subtitle.get("segments", [])

        try:
            outline, key_ideas = self.analyzer.analyze(
                transcript_text=transcript_text,
                segments=transcript_segments,
                title=meta.get("title", bvid),
                duration=meta.get("duration", 0),
            )
        except Exception as exc:  # noqa: BLE001
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.FAILED,
                reason=f"analyze failed: {exc}",
                failure_type=FailureType.ANALYSIS_FAILED,
                source_type="subtitle",
                meta=meta,
            )

        try:
            doc_path = write_video_doc(
                topic=config.topic,
                meta=meta,
                outline=outline,
                key_ideas=key_ideas,
                transcript_text=transcript_text,
                transcript_segments=transcript_segments,
                source_type="subtitle",
                include_full_text=config.include_full_text,
                auto_add_idea_time=config.auto_add_idea_time,
            )
        except Exception as exc:  # noqa: BLE001
            return VideoProcessResult(
                bvid=bvid,
                status=VideoStatus.FAILED,
                reason=f"archive failed: {exc}",
                failure_type=FailureType.ARCHIVE_FAILED,
                source_type="subtitle",
                meta=meta,
            )

        return VideoProcessResult(
            bvid=bvid,
            status=VideoStatus.DONE,
            reason="archived",
            source_type="subtitle",
            output_path=str(doc_path),
            meta=meta,
        )
