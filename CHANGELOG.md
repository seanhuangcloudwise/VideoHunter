# Changelog

## [Unreleased]

### Added
- **批量处理架构**：新增 `src/batch/` 可复用批处理包，采用 Provider/Selector/Processor/Reporter 四层 Protocol 接口设计
  - `models.py` — 领域模型：`VideoCandidate`、`BatchJobConfig`、`VideoProcessResult`、`BatchRunResult`
  - `interfaces.py` — 可插拔接口协议（`CandidateProvider`、`Selector`、`VideoProcessor`、`ResultReporter`）
  - `orchestrator.py` — `BatchOrchestrator`，串联四层组件
  - `providers.py` — `SearchUrlCandidateProvider`，从 B 站搜索 URL 发现候选视频
  - `selectors.py` — `DefaultTopNSelector`，支持 Top-N 默认选择或 BVID 手动指定
  - `processors.py` — `ArchivingProcessor`（字幕抓取 → 分析 → 归档）/ `SubtitleFirstProcessor`（仅获取）
  - `analyzers.py` — `SimpleTranscriptAnalyzer`，本地确定性转写分析器
  - `reporters.py` — `JsonSummaryReporter`，输出批次 JSON 汇总
  - `candidate_preview.py` — `build_search_url_preview()`，生成交互式候选列表

- **批处理外观层** `src/batch_processor.py`：`run_search_url_batch()` 一站式调用，批次结束后自动更新主题索引

- **CLI 新增两个子命令**（`main.py`）：
  - `list-candidates <url>` — 列出搜索页候选视频（含推荐标记）
  - `batch-process <url> --topic <topic>` — 批量分析并归档，支持 `--selected`、`--full-text`/`--no-full-text`、`--reprocess`

- **B 站搜索 URL 解析**（`src/bilibili_client.py`）：新增 `parse_search_url()`、`search_videos_page()`、`search_videos_from_url()`，支持 `search.bilibili.com/all` 及 `www.bilibili.com/search` 两种域名格式

- **归档工具增强**（`src/markdown_archiver.py`）：
  - `is_video_processed()` / `list_processed_bvids()` — 基于 frontmatter 扫描，兼容新文件命名
  - `_sanitize_filename()` — 生成 `[UP主] 标题` 格式的安全文件名
  - 文章文件名由 `BV号.md` 改为 `[UP主] 标题.md`
  - H1 标题格式统一为 `# [UP主] 标题`
  - `update_topic_index()` 改为扫描所有 `*.md`（排除 `_index.md`），兼容新文件命名

- **Agent 交互式选择**（`.github/agents/video-hunter.agent.md`）：集成 `vscode_askQuestions` 工具，批量分析前通过 Copilot Chat UI 以多选框形式选取目标视频、设置主题名与全文策略

### Changed
- 已归档的视频 Markdown 文件全部按新格式重命名（`BV*.md` → `[UP主] 标题.md`）
- 所有主题的 `_index.md` 汇总表已同步重建，链接指向新文件名

---

## [0.1.0] — 2025

### Added
- 初始版本：单视频分析流水线（字幕抓取 → LLM 分析 → Markdown 归档）
- 支持 B 站 CC 字幕提取与 Whisper 离线转写双通道
- `KEEP_FULL_TEXT` / `AUTO_ADD_IDEA_TIME` 配置开关
- 交互式 Topic 管理与主题索引自动维护
