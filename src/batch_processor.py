"""Compatibility facade for batch workflows.

This module keeps a simple import path while delegating to src.batch package.
"""

from __future__ import annotations

from .batch import (
    ArchivingProcessor,
    BatchJobConfig,
    BatchOrchestrator,
    DefaultTopNSelector,
    JsonSummaryReporter,
    SearchUrlCandidateProvider,
)
from .markdown_archiver import update_topic_index


async def run_search_url_batch(
    search_url: str,
    topic: str,
    selected_arg: str | None = None,
    skip_existing: bool = True,
    default_top_n: int = 10,
    limit: int = 50,
    include_full_text: bool | None = None,
    auto_add_idea_time: bool | None = None,
) -> dict:
    """Run reusable batch workflow for one Bilibili search page URL."""
    orchestrator = BatchOrchestrator(
        provider=SearchUrlCandidateProvider(search_url=search_url, limit=limit),
        selector=DefaultTopNSelector(top_n=default_top_n, selected_arg=selected_arg),
        processor=ArchivingProcessor(),
        reporter=JsonSummaryReporter(),
    )
    config = BatchJobConfig(
        topic=topic,
        skip_existing=skip_existing,
        default_top_n=default_top_n,
        subtitle_policy="skip_no_subtitle",
        include_full_text=include_full_text,
        auto_add_idea_time=auto_add_idea_time,
    )
    result = await orchestrator.run(config=config, source="search_url")

    try:
        index_path = update_topic_index(topic)
        result["index_path"] = str(index_path)
    except Exception as exc:  # noqa: BLE001
        result["index_update_warning"] = str(exc)

    return result
