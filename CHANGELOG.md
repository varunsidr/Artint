# Changelog

Changes under **Unreleased** have not been included in a tagged release. Verification below records the local pre-push checkpoint; a source push does not imply a release or a passing hosted CI run.

## Unreleased

### Added

- Analytics indicators for 30-day publication momentum, leading/top-three publisher share, analysis/date coverage, publisher analysis/latest-date details, topic-by-publisher label comparison and collection metadata/capture readiness. Full-scope SQL aggregates and linked cell filters share notebook/CSV membership; unavailable checks/labels and zero baselines stay explicit. Calendar-aware caching, theme/mobile/keyboard behavior and specialist mode are retained. No new inference or source-quality score is introduced.

- Metadata-only model-status checks in Research settings and the optional installation CLI, with installed/loaded/unknown states, reported GPU/CPU memory placement, runtime/context checks and theme-aware snapshots. Added cited Markdown briefs and complete JSON research downloads that reuse the current result without inference or storage writes.
- A consolidated offline batch gold-review page with source-bound AI suggestions, original/proposed comparisons, family/visible-case selection, explicit batch decisions, flagged-case checks, pending edits, exclusions and resumable standard review exports. The private 60-case packet contains 37 suggested revisions, 22 source checks, one proposed keep and zero human decisions.
- An opt-in `-KvCacheType q8_0` Windows GPU profile and a local requested-settings manifest. The default remains `f16`; profiles do not stop existing servers, download models, change app model defaults or alter persistent/parent environment settings.
- An optional native Windows NVIDIA Ollama launcher with UUID selection, loopback binding and Flash Attention while retaining `f16` KV-cache precision. One 8 GB RTX 5050 laptop check verified full embedding-model GPU residency and partial answer-model offload at the existing 16K context; this is not a measured retrieval-quality or speed claim.

- Read-only development-source selection and machine-proposed gold authoring, with an offline browser review page, Unicode-correct evidence selection, partial review export/import, revisions/exclusions and validated application of declared human approval. The private 60-case batch remains unreviewed; its source bodies are not distributed.

- A research evaluation CLI with a versioned frozen corpus, original 24-case diagnostic fixture, top-10 retrieval/six-passage answer runs, isolated embedding caches, source/config/model snapshots, interrupted-run journals, human atomic-claim review and paired retrieval/latency reports. It calls the existing RAG functions without changing production retrieval or model behavior.

- General analytics for any saved collection: publication trends, publisher coverage, current-analysis counts, saved topics, reading profiles, linked filters and matching CSV exports. Short date ranges use daily activity with empty days included.
- An explicit specialist AI investment view for the existing English coverage lenses, company mentions and concern/countercase passages.
- A single-article Research shortcut from an empty reading-room Analysis tab, with offline/deleted-source handling and preserved browsing filters.
- Installation and recovery documentation, a non-root Docker/Compose setup with persistent volumes and sandboxed Chromium, disposable installation validators, and Windows/Ubuntu/Docker CI definitions.
- Prospective extraction-cohort freezing and phase/hash-bound human review, eligibility accounting, second-review disagreement reports and explicit unresolved quality gates.

### Changed

- New captures omit a recognized publisher-home/social/newsletter promotion template before article validation, PDF generation and research. Quoted or mixed editorial content and following article sections are preserved. Diagnostics record removal counts, and extraction evaluation fingerprints the cleanup dependency. Existing stored copies/PDFs and frozen evidence are retained.

- Retain the last completed research answer and its exports through failed requests, offline model discovery and changed/empty filters, with an original-scope label and explicit session-only clear action. New exports include original completion time and source-selection fingerprints; passage searches record their embedding model. International source links use IDNA hostnames, and near-full mixed GPU residency no longer rounds to 100%.

- New generation automatically selects 8K/16K context, reserves answer space, disables truncation/context shifting and retries a complete underestimated request at most once at 16K. Context metadata appears in new analyses, research answers and evaluator rows. Generation requires the oldest checked compatible Ollama runtime, 0.40.11. Existing saved analyses and fixed-16K evaluation snapshots are retained.
- Library and Research separate general filters from topic/tag choices derived from all matching sources. Incompatible selections clear when the context changes; missing labels remain explicit.
- Pagination uses compact Previous/page-jump/Next controls. Analytics text is larger; Library and Analytics previews remove Markdown/image destinations while preserving stored sources and PDFs.
- Research answer cards expose cited passages directly. Retrieval details report searched passages, embedding reuse/creation and elapsed time.
- Embedding-cache reads use bounded SQL batches. The search model stays loaded between embedding batches and requests unload after the final batch. An identical question can reuse the last session result, with an explicit fresh-result bypass.
- Refreshed the README analytics screenshot using the original 36-article synthetic demo.

### Verification and remaining work

- Three native GPU/cache profiles completed 36 observations on six original synthetic cases at 8K, with zero runtime failures and pending human review. Qwen3.5 9B/q8 remained partly on CPU; quantization changed some embedding retrieval inputs. The ordinary 8B/f16 profile was restored and confirmed fully GPU-resident at 8K. This launcher-only experiment does not replace the full-suite checkpoint or establish model quality.
- Latest full Windows checkpoint: **404 passed, 1 opt-in live-server installation test skipped**. Intelligence/research/gold-authoring/diagnostic/export tools also passed **159 targeted tests with 1 opt-in batch-browser test skipped** on the existing native Ubuntu/WSL2 Python 3.13 environment. A later targeted capture/cleanup/evaluation run passed **69 tests with 1 opt-in real-browser test skipped** there. Separate synthetic browser checks cover model-status snapshots, theme/mobile behavior and cited/full-result downloads without extra inference, including failure/offline/empty-filter recovery with unchanged evidence. Batch review checks remain valid and the real 60-case packet remains entirely pending. Earlier actual Qwen/GPU smokes remain separate evidence; no human support percentage is established. See the [validation record](docs/validation.md) and [milestones](milestones.md).
- Milestone A was checked on Windows, native Ubuntu/WSL2 x86_64 and a Linux Docker image. Subsequent analytics/review changes have not been revalidated on Linux/Docker; the expanded hosted workflow remains pending.
- The generation model, output budget, passage construction, cosine ranking and six-passage retrieval are unchanged. Context follows the new adaptive policy; cache/SQL and GPU placement checks do not establish answer quality.
- Human-reviewed extraction and answer-quality gates remain open. Persistent hybrid retrieval, durable research sessions and claim-level comparison are planned work.
- No new schema migration or dependency change is required for the analytics/research usability changes; schema version 6 is retained.
