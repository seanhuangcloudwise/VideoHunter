"""Result reporters for batch workflow outputs."""

from __future__ import annotations

from .models import BatchRunResult, FailureType, VideoStatus


class JsonSummaryReporter:
    """Build CLI-friendly JSON result with details."""

    def build(self, run_result: BatchRunResult) -> dict:
        summary = run_result.summary()

        details = []
        skipped_no_subtitle = []
        failed = []

        for item in run_result.processed:
            one = {
                "bvid": item.bvid,
                "status": item.status.value,
                "reason": item.reason,
                "failure_type": item.failure_type.value if item.failure_type else None,
                "source_type": item.source_type,
                "output_path": item.output_path,
            }
            details.append(one)

            if item.status == VideoStatus.SKIPPED and item.failure_type == FailureType.NO_SUBTITLE:
                skipped_no_subtitle.append(item.bvid)
            if item.status == VideoStatus.FAILED:
                failed.append({"bvid": item.bvid, "reason": item.reason})

        return {
            "summary": summary,
            "details": details,
            "skipped_no_subtitle_bvids": skipped_no_subtitle,
            "failed_items": failed,
            "next_action_hint": (
                "有无字幕跳过项，可在用户确认后对这些 BVID 执行 transcribe 兜底。"
                if skipped_no_subtitle
                else "无无字幕跳过项。"
            ),
        }
