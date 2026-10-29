# Changelog

Changes under **Unreleased** have not been included in a tagged release. Verification below records the local pre-push checkpoint; a source push does not imply a release or a passing hosted CI run.

## Unreleased

### Added

- General analytics for any saved collection: publication trends, publisher coverage, current-analysis counts, saved topics, reading profiles, linked filters and matching CSV exports. Short date ranges use daily activity with empty days included.
- An explicit specialist AI investment view for the existing English coverage lenses, company mentions and concern/countercase passages.
- A single-article Research shortcut from an empty reading-room Analysis tab, with offline/deleted-source handling and preserved browsing filters.
- Installation and recovery documentation, a non-root Docker/Compose setup with persistent volumes and sandboxed Chromium, disposable installation validators, and Windows/Ubuntu/Docker CI definitions.
- Prospective extraction-cohort freezing and phase/hash-bound human review, eligibility accounting, second-review disagreement reports and explicit unresolved quality gates.

### Changed

- Library and Research separate general filters from topic/tag choices derived from all matching sources. Incompatible selections clear when the context changes; missing labels remain explicit.
- Pagination uses compact Previous/page-jump/Next controls. Analytics text is larger; Library and Analytics previews remove Markdown/image destinations while preserving stored sources and PDFs.
- Research answer cards expose cited passages directly. Retrieval details report searched passages, embedding reuse/creation and elapsed time.
- Embedding-cache reads use bounded SQL batches. The search model stays loaded between embedding batches and requests unload after the final batch. An identical question can reuse the last session result, with an explicit fresh-result bypass.
- Refreshed the README analytics screenshot using the original 36-article synthetic demo.

### Verification and remaining work

- Latest full Windows checkpoint: **231 passed, 1 opt-in live-server installation test skipped**. Separate browser checks cover both themes, mobile layouts, filters, CSV membership, pagination and article handoff. See the [validation record](docs/validation.md) and [milestones](milestones.md).
- Milestone A was checked on Windows, native Ubuntu/WSL2 x86_64 and a Linux Docker image. Subsequent analytics/review changes have not been revalidated on Linux/Docker; the expanded hosted workflow remains pending.
- The generation model, context/output budgets, passage construction, cosine ranking and six-passage retrieval are unchanged. Cache/SQL timing improvements do not establish answer quality.
- Human-reviewed extraction and answer-quality gates remain open. Persistent hybrid retrieval, durable research sessions and claim-level comparison are planned work.
- No new schema migration or dependency change is required for the analytics/research usability changes; schema version 6 is retained.
