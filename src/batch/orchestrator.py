"""Application service orchestrating reusable batch workflow."""

from __future__ import annotations

from .interfaces import CandidateProvider, ResultReporter, Selector, VideoProcessor
from .models import BatchJobConfig, BatchRunResult


class BatchOrchestrator:
    """Provider -> Selector -> Processor -> Reporter."""

    def __init__(
        self,
        provider: CandidateProvider,
        selector: Selector,
        processor: VideoProcessor,
        reporter: ResultReporter,
    ) -> None:
        self.provider = provider
        self.selector = selector
        self.processor = processor
        self.reporter = reporter

    async def run(self, config: BatchJobConfig, source: str) -> dict:
        candidates = await self.provider.discover()
        selected_bvids = self.selector.select(candidates)

        result = BatchRunResult(
            source=source,
            topic=config.topic,
            discovered_count=len(candidates),
            selected_bvids=selected_bvids,
        )

        for bvid in selected_bvids:
            item = await self.processor.process_one(bvid, config)
            result.processed.append(item)

        result.finalize()
        return self.reporter.build(result)
