# Milestones

Historical measurements and verification paths below refer to developer-local artifacts. `data/` and `output/` are excluded from the public repository. The reproducible public preview uses original synthetic fixtures; see [the README](README.md).

## Public repository preparation — 2026-10-28

- Added MIT licensing, a focused product README, detailed operating guide and local publishing instructions.
- Excluded runtime libraries, downloaded content, generated artifacts, environments, secrets, database sidecars and backups. Existing local files are preserved.
- Set the shared Streamlit configuration to bind to `127.0.0.1` by default, matching the local single-user scope.
- Added an offline generator for 36 fictional articles, four fictional publishers, individual PDFs, 12 explicitly hand-authored example analyses, project memberships, personal notes and a source-anchored highlight. It requires a new or empty destination and restores its in-process storage overrides.
- Added a Windows/Python 3.13 GitHub Actions workflow with pinned official actions, Chromium installation, dependency checks, tests and synthetic demo generation. Hosted CI remains pending until the first push.
- Local validation: dependency check passed; **196 tests passed**, including the real-browser fixture and two demo isolation/overwrite regressions. Extraction completeness, independently reviewed AI quality and hosted deployment readiness remain separate unfinished targets.
- A fresh copy containing only staged public files also passed all 196 tests and generated the offline demo using the installed development environment. Staged-file review found no private/generated paths, credential-pattern matches or broken documentation links. Hash checks preserved the existing 105 articles and 105 PDFs. This verifies checkout contents, not a clean dependency install on another machine.

Updated: 2026-10-28. Product direction: a dependable local article research tool.

Statuses describe delivered and verified behavior. Benchmark targets below are proposed release gates, not achieved measurements. See [requirements](requirements.md) for acceptance criteria and [architecture](architecture.md) for implementation boundaries.

## M0 — Local MVP

Status: complete for the documented functional scope.

- Public HTML URL batches, SQLite storage, one reading PDF per article, ZIP downloads.
- Descriptive analytics and CSV export.
- Local Ollama summaries, topics, semantic passage search, and cited answers.
- Baseline verification: 25 offline tests passed; dashboard startup had no exceptions.
- Baseline data: five articles from one publisher, five PDFs, five saved analyses. This is demonstration evidence, not an extraction or AI-quality benchmark.
- Fresh model quality was not evaluated during the baseline review because Ollama was offline.

## M1 — Verified PDF exports

Status: complete, verified 2026-10-27.

Scope: PDF-01 through PDF-04; DEV-01 and DEV-02 for this change.

- Render extracted Markdown links as readable labels with clickable HTTP(S) destinations.
- Preserve basic headings, emphasis, ordered/unordered lists, quotes, code, and Markdown tables when present in saved text.
- Escape raw article markup and prevent active links to unsafe URL schemes.
- Preserve the publisher citation, retrieval time, selectable text, and page numbering.
- Replace PDFs atomically so a failed generation preserves the previous file.
- Test actual PDF text and link annotations, including multi-page output.
- Separate application dependencies from development/test dependencies; record the tested environment.
- Regenerate the existing reading PDFs from saved text after verification, without fetching publishers again.

Exit: PDF regression tests and the full offline suite pass; all existing PDFs regenerate; startup smoke test passes. Multilingual font coverage, embedded images, and faithful website archiving are outside this milestone.

Completion evidence:

- `python -m pytest -q`: **37 passed**, including generated-PDF text/URI checks, multi-page preservation, failed-write recovery, and isolated offline dashboard startup.
- `python -m pip check`: no broken requirements.
- Regenerated all five saved article PDFs without fetching publisher pages or changing saved source text/AI analyses.
- The SpaceX reading copy (`9679049c03ff8624.pdf`) changed from seven literal Markdown links and two source-link annotations to zero literal Markdown links and eleven annotations (wrapped labels can produce multiple annotations).
- Runtime/test dependencies are separated and pinned; `requirements-lock.txt` records 59 packages from the tested Windows/Python 3.13.14 environment. Clean installation on other platforms remains M5 work.
- These checks verify rendering and application wiring, not publisher coverage or fresh model accuracy.

## M1.1 — Modern research workspace

Status: complete, verified 2026-10-27. Added in response to the dashboard design review.

Scope: UX-01 and UX-02, plus the first library usability improvements.

- Replaced the four-tab screen with focused Library, Analytics, Research, and Import views and persistent sidebar navigation.
- Added a warm light theme, restrained forest-green accents, system typography, compact article rows, and responsive layouts.
- Added text search, publisher filtering, sorting, readable PDF download names, and a reading dialog with article, analysis, and source details.
- Grouped optional model setup under Research settings; saved insights remain readable offline. Cross-source answers use numbered evidence labels.
- Made PDF ZIP generation explicit rather than rebuilding it on every dashboard rerun.
- Cleaned analytics styling and excluded URL destinations from common-term counts.
- Preserved currency as ordinary prose, paragraph spacing, and safe text rendering in the reader; image references are not fetched.
- Verification: **40 offline tests passed**. Headless Chrome exercised all views, search, reading, on-demand ZIP export, and saved analysis. A 390px mobile viewport had no horizontal overflow, and the sidebar could be closed and reopened. No browser page errors were recorded.
- Screenshots: `output/ui/library-desktop.png`, `analytics-desktop.png`, `research-desktop.png`, `import-desktop.png`, `reading-room.png`, and `library-mobile.png`.
- Existing limitations remain: no indexed/paginated library queries, no extraction coverage benchmark, and no fresh live-model evaluation in this change. M2 remains the next reliability milestone; M3 and M5 are only partially advanced by this work.

## M1.2 — Matching dark appearance

Status: complete, verified 2026-10-27.

Scope: UX-03.

- Added a sidebar Dark mode switch and matching charcoal, warm-white, and sage palette.
- Centralized semantic colors for both appearances in `app/theme.py`; page styles, native controls, dropdowns, dialogs, model settings, and Plotly charts share the selected palette.
- Retain the choice across views and restore it from `?theme=dark` or `?theme=light` after refresh. Appearance is scoped to each session; no process-global configuration changes.
- Adjusted chart margins so axis labels remain visible in both themes and themed chart hover labels.
- Preserved the light layout and paper-friendly PDF exports.
- Verification: **44 offline tests passed**, including appearance restoration, navigation, and WCAG AA contrast checks for normal text and interactive label palette pairs. Chrome checks covered all four dark screens, native dropdowns, the reading dialog, chart hover, refresh persistence, keyboard switching, separate light/dark sessions, and a 390px mobile viewport without horizontal overflow. No browser page errors were recorded.
- Previews: `output/ui/library-dark-desktop.png`, `analytics-dark-desktop.png`, `reading-room-dark.png`, `research-dark-desktop.png`, `import-dark-desktop.png`, `library-dark-mobile.png`, and `library-light-after-toggle.png`.

## M1.3 — Bounded large-library workflows

Status: complete, verified 2026-10-27.

Scope: SCALE-01 through SCALE-04; advances parts of M3 and M5.

- Added SQLite FTS5 word-prefix search, indexed/stable sorting, publisher/status filters, and 25/50/100-record result pages with previous/next and direct page navigation.
- Dashboard startup no longer reads all article text or loads every insight in Python. List queries return bounded metadata, excerpts, and valid cached summaries. Full text is loaded for the selected reading copy or explicitly scoped research operation.
- Analytics uses SQL aggregates, bounded chart/source-index records, and an explicitly labeled on-demand 250-article term sample.
- Metadata exports are prepared only on request (25 MB cap); PDF ZIPs are bounded to the current page (100 files / 50 MB actual input).
- Research/saved-insight browsing is paginated. The UI states exactly which sources a question will search and allows up to 100 selected/matching articles; analysis batches process one 25-article page. Whole-library semantic indexing and background jobs remain unfinished.
- Applied schema version 1 with a consistent pre-upgrade backup, transactional backfill/index creation, FTS mutation triggers, deterministic connection cleanup, and export/research revision tracking.
- Verification: **61 offline tests passed**, including legacy migration/rollback, insight/embedding preservation, index updates/deletion, stale-cache filtering, stable pagination, bounded research reads, and export limits.
- Chrome exercised the isolated 10,000-record database: 25-row default, a 100-row page, analysis filter, next-page navigation without duplicates, direct page 400, indexed search, reading, filtered CSV download, analytics, saved insights, and mobile layout without overflow or page errors.
- Verified the real library after migration: all five original articles, five saved analyses, and 28 cached embeddings preserved byte-equivalent selected data via checksums. A pre-upgrade backup remains in `data/backups/`.

The synthetic benchmark report (`output/library-benchmark.json`, local artifact) records 20 publishers, 400–1,200-word bodies, summaries for half the articles, hardware/runtime, and measurement exclusions:

| Warm measurement | 1,000 articles p95 | 10,000 articles p95 |
| --- | --- | --- |
| Overview plus first-page SQL data | 17.89 ms | 236.81 ms |
| Broad keyword search | 19.77 ms | 270.07 ms |
| Selective keyword search | 1.04 ms | 2.12 ms |
| Analytics aggregates | 8.65 ms | 133.45 ms |
| Dashboard script through AppTest | 135.02 ms | 352.44 ms |

Query timings used 30 warm runs; AppTest timings used 10. The 10,000-record page contained 25 records / about 17 KB of result JSON; the database was about 120 MB. These are local synthetic measurements, not browser-paint, inference, ingestion, PDF-generation, or concurrency SLAs. The synthetic browser fixture was kept separate from the real library and removed after verification.

## M1.4 — Linked research analytics and a live topic collection

Status: complete for the scope below, verified 2026-10-28. Scope: OBS-01 through OBS-05.

- Replaced the file-description charts with a source-backed Research observatory: named collections, six coverage lenses, company/lens co-mentions, publisher mix, publication timeline, concern/countercase passage previews, and a 12-row source notebook.
- Collection, keyword, publication-window/month, publisher, lens, and company controls filter all evidence together; CSV uses the identical predicates. Missing calendar months appear as zero. Reading actions open the existing source dialog.
- Added a local Streamlit components-v2 interface with responsive layouts, matching light/dark palettes, short counter/bar/SVG transitions, debounced search, stale-response protection, focus preservation, and reduced-motion support. Article values are inserted as text into trusted static markup.
- Added research collections to Research so users can ask within the AI-bubble collection and explicitly include all 100 sources when desired. Analysis still uses the existing local model workflow; importing does not invent or automatically generate new summaries.
- Collected **100 public reading sources across 64 website hosts**, capped at five per host. Six are research abstracts; the remainder include news, commentary, institutional analysis, and interview/transcript pages. Publication metadata can be approximate. Collection cutoff: 2026-10-27.
- The live collection audit (`output/ai-bubble-collection.json`, local artifact) records **420 checked candidates: 100 saved, 159 fetch/extraction failures, 130 unsupported pages, 25 source-quality exclusions, and six duplicates**. Candidates were discovered separately and shuffled by host. This is a diverse research sample, not random sampling of the whole web, a sentiment survey, or the M2 eligible-extraction benchmark.
- Unified bounded robots/article fetching, validated redirect hops, cached robots policies, per-host pacing, and access-block handling. The resumable collection script audits readable length, relevance, cutoff, duplicate text/titles, and source-type/boilerplate exclusions.
- Applied schema version 2 with a pre-upgrade backup, named collections, memberships, versioned content-matched coverage signals, and mutation-based cache invalidation. Verified all five original articles, five saved analyses, and 28 vectors unchanged; all 100 new PDFs exist and SQLite integrity is `ok`.
- Verification: **74 offline tests passed**. Chrome checked linked lenses/matrix/publisher/month controls, keyboard selection, search/empty results, pagination, source reading, actual CSV download, collection switching, dark-theme filter retention, and a 390px reduced-motion layout without analytics overflow or browser page errors.
- Screenshots: `output/ui/observatory-light.png`, `observatory-dark.png`, and `observatory-mobile-dark.png`.

The new observatory benchmark (`output/observatory-benchmark.json`, local artifact) uses separate dense synthetic libraries with all six lenses and three company matches per article, 20 publishers, 400–1,200-word bodies, and 15 warm runs:

| SQL snapshot measurement | 1,000 stored / 917 date-eligible | 10,000 stored / 9,167 date-eligible |
| --- | --- | --- |
| Whole selection p95 | 134.20 ms | 1,505.41 ms |
| Lens + company + page p95 | 195.47 ms | 2,343.95 ms |
| Source rows returned | 12 | 12 |
| Snapshot JSON | about 11.6 KB | about 11.6 KB |

These timings exclude browser paint, network, PDF generation, inference, and concurrency. Revision-keyed caching avoids repeated aggregate work for the same selection; a new broad 10,000-record filter still takes seconds. The earlier M1.3 analytics measurement describes the previous aggregate function. Persistent indexed facets/aggregate reuse are candidates for the next scale pass, not delivered performance claims.

## M1.5 — Reliable return navigation and useful library filters

Status: complete, verified 2026-10-28. Scope: UX-04 and the remaining date-filter portion of LIB-01.

- Fixed the Library → Analytics → Library failure: pagination no longer depends on widget state that Streamlit removes when a view is hidden. Missing legacy state is initialized defensively; page changes and direct page input use durable view state. Research pagination shares the fix.
- Preserved library controls across view changes, including custom dates, using session-persistent native widgets and saved values. Filter changes still reset pagination; returning to the same selection preserves the page.
- Replaced the narrow toolbar/floating filter button with labeled full-width search, collection, multi-publisher, and sort controls, plus a stable expandable panel. Added analysis status, publication windows/custom/unknown dates, reading length, coverage theme, company, and saved-topic filters, active-selection labels, and one clear action. Clear retains sorting and page size.
- Added publication-date and shortest-read sorting; undated records sort last by publication. Custom ranges exclude unknown dates, support either bound, and warn on reversed bounds. Reading bands and metadata exports use the same SQL predicates as visible results.
- Verification: **83 offline tests passed**, covering navigation/page restoration, missing-state repair, compound filter/date persistence, clear/reset, custom-date errors, reading boundaries, sorting, and CSV parity. Chrome verified three Library/Analytics round trips with page 2 retained, combined filters, persistent custom dates, an open panel during editing, light/dark controls and calendar, empty results, and a 390px layout with no toolbar overflow or browser page errors.
- Previews: `output/ui/library-filters-light.png`, `library-filters-dark.png`, `library-calendar-dark.png`, and `library-filters-mobile.png`.

## M1.6 — Clear chart interactions and visual hierarchy

Status: complete, verified 2026-10-28. Scope: UX-05.

- Replaced the tall browser outline on clicked timeline columns with a point-sized keyboard focus ring; selection remains on the dot and Enter/Space still filters the month.
- Fixed event-handler accumulation across component renders. The previous render is explicitly disposed before the next render, so later clicks and key presses no longer toggle a filter twice.
- Replaced native chart hover boxes with theme-aware cards for timeline points, company/theme cells, coverage bars, and publishers. Cards show exact current counts and context, wrap long content, stay within the viewport, follow scrolling, and dismiss with Escape. Filtered percentages use the active selection.
- Added coordinated blue/purple/teal/amber/clay/slate coverage accents across bars, matrix columns, and source tags, plus distinct panel surfaces and warmer/cooler passage-card borders. Corrected selected sidebar hover contrast.
- Verification: **85 offline tests passed**, including text/panel and chart-mark contrast checks. Chrome verified clicked/keyboard dots in light/dark/mobile, one update per Enter/Space activation, all four hover-card types in both themes, Escape dismissal, 390px tooltip bounds, updated filtered percentages, and the linked-filter/export/reader/navigation regression checks with no browser page errors.
- Previews: `output/ui/observatory-colors-light.png`, `observatory-colors-dark.png`, `observatory-tooltip-dark-1.png`, and `observatory-mobile-tooltip-dark.png`.

## M1.7 — Topic discovery and selected-source collections

Status: complete for the local personal-use scope, verified 2026-10-28. Scope: DISC-01 through DISC-03; advances the import portion of M5.

- Added Search articles with up to five topics, optional highlighted/required preview keywords, 5/10/25/50/100/custom 1–100 result targets, publisher presets (including Guardian/Hindu), extra domains, requested language, reported dates/custom bounds and ordering.
- Used a real free Bing News RSS source after the keyless GDELT endpoint proved unavailable/rate-limited and the Guardian test API key was rejected. No account/key is required for the chosen source. RSS use is restricted to personal, non-commercial aggregation; a licensed adapter is needed for a commercial hosted tool.
- Requests are bounded/paced; duplicate URLs/titles and nonmatching publisher/date/required-preview-keyword results are removed. Previews are safely escaped/highlighted and show actual found/requested counts, provider/date/language limitations and partial errors. No previews become library articles automatically.
- Added ten-result pages, persistent individual/page/all selection, named collections, and explicit imports of up to 100 selected URLs. Exact saved URLs are reused. Background workers retain per-item outcomes, owner leases, stop-after-current requests, and restart recovery. The UI remains navigable; activity stops polling when no batch is active and retains its expanded state on completion.
- Applied backed-up schema version 3 for import queues without rebuilding article/FTS/facet/AI caches. Article/membership/item completion is one SQLite commit; PDF replacement remains a separate atomic filesystem operation. Full scheduler, generalized jobs, automatic retry policy and broader restore remain open.
- Verification: **113 offline tests passed**, covering provider parsing, safe links/highlights/XML, query filters, partial results/deduplication, explicit import boundaries, selection persistence, lease recovery without UI polling, cancellation, failed PDFs, collection reuse/routing and migration backup.
- Live free-source checks: 5/5 results for AI bubble; 100/100 results from 52 publisher domains for artificial intelligence (13 RSS pages, about 16 seconds); a strict Guardian/Hindu + keyword + reported-date search found only 1/10 and correctly reported the shortfall. These are availability checks, not an extraction-quality benchmark or a promise for all future searches.
- Chrome used an isolated database/PDF directory to search, filter Guardian sources, highlight keywords, retain selection through navigation, select/clear results, and explicitly import a real Guardian article while browsing other views. The import produced one new reading PDF with no failures, and its collection opened correctly in Library. Light/dark and 390px layouts had no horizontal form overflow or browser page errors.
- Previews: `output/ui/discovery-empty-dark.png`, `discovery-results-dark.png`, `discovery-results-light.png`, and `discovery-mobile-dark.png`. The real library's article/insight/vector records are preserved; QA imports stay isolated.

## M1.8 — Browser-assisted article capture

Status: complete, verified 2026-10-28. Scope: ING-05 and ING-06.

- Added Auto / HTML-only capture to manual imports, selected search imports and the CLI. Auto starts with HTML and opens a fresh headless browser only for a likely incomplete JavaScript page. Discovery remains free RSS.
- Added intercepted, bounded public-resource fetching, validated resource redirects and a disabled direct-network route. Blocks, robots failures, known access gates and ordinary network failures do not trigger browser retry. Browser documents that redirect report an actionable final-URL instruction.
- Capture snapshots retain visible reading content and metadata, excluding hidden content, scripts and JSON article payloads. Source details identifies HTML extraction versus browser rendering.
- Schema version 4 adds capture provenance and persistent batch mode after a consistent backup. Existing articles, content fingerprints, saved insights and embeddings are preserved.
- Verification: **132 offline tests passed**, with the optional real-browser test skipped by default. The real Chrome fixture also passed separately, exercising JavaScript rendering from a worker thread, stylesheet-based hidden text, a public resource redirect, private-request blocking and extracted links. `pip check` reports no broken requirements.
- Chrome UI verification covers manual and background browser imports into isolated SQLite/PDF storage, capture setting persistence, source details, both themes and mobile controls. Fixtures are synthetic; this does not establish live publisher success rates or extraction completeness.
- The full suite with browser tests enabled passed **133 tests**. The isolated browser reading PDF has one page and 1,620 selectable characters. The real dashboard still returns five live free-search previews; no real-library imports were performed. Migration checksum verification preserved all **105 articles, five insights and 28 embeddings**. Reports: `output/ui/browser-mode-verification.json` and `output/ui/browser-ui-verification.json`; screenshots: `browser-import-dark.png`, `browser-source-details-dark.png`, `browser-search-dark.png`, `browser-search-light.png`, and `browser-search-mobile.png` under `output/ui/`. Temporary QA storage/server were removed after verification.
- Python Playwright is pinned in the application and environment snapshots; this workspace uses installed Chrome. Bundled Chromium installation is optional when no Chrome/Edge is available.

## M2 — Reliable ingestion

Status: in progress. Bounded network policy, visible/persisted capture diagnostics and a paired 100-source diagnostic run are delivered. The declared eligible-body/metadata review and shared canonical/version behavior remain open.

Scope: ING-01 through ING-04.

- Delivered: bound robots requests and redirects; share URL validation and request policies.
- Delivered in M1.8: conditional browser rendering with capture provenance and persistent import mode. Live publisher completeness and metadata evaluation remain open.
- Delivered in M2.1: structured capture findings and actionable persisted import failure categories.
- Collector delivered: tracking-parameter cleanup, identical/near-duplicate bodies, and regional title duplicates. Shared canonical identity/version behavior in ordinary imports remains planned.
- Add publisher fixtures for redirects, malformed HTML, metadata, body completeness, blocked pages, and oversized responses.
- A heterogeneous live collection of 100 sources is available with failures/exclusions retained. Next: define an eligible article benchmark and independently review body completeness and metadata accuracy; the collection does not establish a 90% success rate.

Exit: at least 90% of the declared eligible sample passes the reviewed extraction checklist; every failed/partial extraction is reported; no expected blocked/non-HTML case is silently accepted. Publish the dataset definition, evaluation date, and results.

## M2.1 — Inspectable capture checks and paired evaluation

Status: complete for ING-07 and ING-08 engineering scope, verified 2026-10-28. This does not complete the M2 reviewed-quality gate.

- Added stable failure categories/actions, bounded article-metadata fallbacks, explicit published-date preference, comment exclusion and an 80-unit excerpt guard with CJK-aware counting.
- Added versioned diagnostics for unavailable metadata, possible missing/extra body content and decoding damage. Lists/tables/quotes are included in reference blocks. A conservative article-region fallback removes substantial outside text only if detected source-block coverage is retained.
- Manual import results, background batches and the reading room expose findings. Legacy saved copies are explicitly unassessed. Schema version 5 adds diagnostics and item error codes after a consistent backup; annotation-only changes do not invalidate AI fingerprints.
- Froze 100 previously saved sources across 64 hosts before fixes. The live run captured 78, encountered 19 subscription/access gates and three network failures. Ninety-seven cached HTML responses were replayed through baseline/current extractors; the three uncached network failures were retained without replay. This is a convenience sample with known abstracts and heterogeneous page types, not a declared eligible benchmark.
- Paired results: four missing author fields recovered; five dates changed to explicit publication metadata; one Amundi reading copy reduced from 810 to 277 readable units with detected source-block coverage retained at 100%. Date changes still need source review, including time-zone boundaries. Capture availability remained 78/100. Five captures remain flagged versus six under the same baseline diagnostics.
- Added resumable phase reports, source/code/response hashes, offline network exclusion, a local cache budget, paired comparisons and a reviewer checklist. Automated findings do not establish body completeness or factual accuracy. No independently reviewed success rate is claimed.
- Verification: the full suite with Chrome enabled passes **158 tests**; dependency checks pass. Chrome covers manual warnings, access-failure guidance, background review/failure counts, reader details and light/dark/390px layouts with no page errors. Existing 105 articles, five insights and 28 embeddings are preserved; UI/PDF mutations use isolated storage.
- Reports: paired findings (`output/evaluations/ai-bubble-20261028/comparison.md`, local artifact), `baseline.json`, `improved.json`, `manifest.json` and `review.csv` in the same directory. Local publisher caches/readings are ignored by version control and have no assumed redistribution license. Verification artifacts: `output/ui/capture-quality-verification.json` and `capture-quality-ui-verification.json`.

Next exit work: review eligibility and body/metadata correctness against originals, expand to at least 100 eligible reviewed sources across 10 publishers, resolve failures/partial captures, and publish the actual reviewed pass rate against the 90% target.

## M3 — Everyday article library

Status: complete for the documented local single-user scope, verified 2026-10-28.

Scope: LIB-01 through LIB-05.

- Keyword search without Ollama, source/date filters, sorting, pagination.
- Added Notes & highlights to the reading room: editable notes, normalized personal tags, project collection creation and membership editing. Save applies organization atomically; annotations do not alter source text, reading PDFs or AI fingerprints.
- Highlights retain exact quotes, offsets and source-text hashes. Users can select repeated occurrences, edit highlight notes and remove highlights. Changed text makes anchors visibly outdated. Mapped current passages are marked in the Article tab; source/annotation strings remain escaped.
- Added personal tag chips and a persistent tag filter using the same SQL predicates for counts, pages and metadata CSV. Source keyword search remains separate from personal notes.
- Added confirmed individual deletion with annotation/membership/facet/FTS/insight cleanup. Only the exact managed, unshared PDF is staged for removal. A validated deletion journal recovers interruptions; caught database failure restores the PDF. External/shared files and content-addressed vector caches are retained.
- Added version-1 portable JSON/ZIP backups, integrity inspection and a non-overwriting merge restore. Relative PDF entries are rebased to the current managed folder. Existing text/nonempty notes are preserved; incompatible text revisions are skipped, and repeated restores add no duplicate articles or highlights. Restore has no publisher/model requests and executes no SQL or code from the archive.
- Applied backed-up schema version 6 for personal tables, indexes, revision triggers and deletion recovery. Backups/deletion/restore coordinate file operations in the local app process; active import batches block destructive/restore actions.
- Verification: **194 tests passed** with Chrome capture enabled; dependency checks pass. Tests cover text anchors and revisions, safe rendering, tag/query/export parity, deletion rollback/recovery, shared/external file protection, portable round trips, malformed/traversal/linked/corrupt/oversized archives, case-safe destination IDs, Windows device-name rejection and idempotent merge.
- Chrome completed the isolated workflow: notes, tags, collection creation, exact passage marking, highlight-note editing, full ZIP download, confirmed deletion, upload inspection, restore and reload persistence. Matching light/dark controls and a 390px reader have no horizontal overflow or page errors. Measured new form/backup button text contrast is at least **5.48:1**.
- Verified the real library unchanged after migration: **105 articles, five analyses, 28 vectors, one collection and 100 memberships**. A full portable backup restored all **105 PDFs** into another managed directory with identical checksums and preserved source/analysis/vector/membership data; repeating restore added zero articles/PDFs. The portable baseline ZIP and pre-v6 SQLite backup are retained under `data/backups/`.
- Evidence: `output/ui/personal-library-verification.json`, `personal-library-ui-verification.json` and `personal-library-contrast-verification.json`. Final previews include `personal-library-highlight-dark.png`, `personal-library-forms-dark-final.png`, `personal-library-forms-light-final.png`, `personal-library-backup-dark-final.png`, `personal-library-backup-light-final.png`, `personal-library-restore-light.png` and `personal-library-notes-mobile.png` under `output/ui/`.

Exit: an offline user can find, organize, annotate, export, restore, and remove articles without editing SQLite or filesystem paths.

Limits: article notes 20,000 characters; 20 tags/200 highlights per article; ten visible highlights per page. Portable backups are bounded to 10,000 articles, 128 MB metadata, 20 MB per PDF, 250 MB ZIP/512 MB expanded data and section record limits. Rename/delete collection management, richer annotation search and cross-process crash-proof restore coordination remain future enhancements. A sudden restore-process loss can leave staging/orphan files; reapplying the same intact backup can adopt matching owned destination files. M2 independent extraction review and M4 AI-quality evaluation remain open.

## M4 — Evaluated AI research

Status: planned.

Scope: AI-01 through AI-04.

- Create a reviewed set of at least 50 questions, including comparisons, conflicting sources, and unanswerable questions.
- Add keyword/semantic hybrid retrieval, source diversity, and evaluation-driven reranking.
- Add token-aware budgets and staged summaries for long articles.
- Persist research history and export research briefs with evidence references.
- Version model identity, prompts, chunking, and caches for reproducible evaluation.

Exit targets: at least 95% of evaluated answer claims supported by their cited text; at least 90% correct abstention on the unanswerable subset. Report sample sizes, rubric, model, hardware, latency, and failures. Automated citation-ID validation alone cannot satisfy this gate.

## M5 — Responsive, installable local beta

Status: in progress. Bounded browsing/analytics/exports, backed-up schema migrations, portable merge restore and deletion recovery, isolated 1,000/10,000-record measurements, and persistent selected-discovery import batches with leases/progress/cancellation are delivered. Generalized ingestion/analysis/index jobs, automatic retry policies, persistent semantic passage indexing, broader cross-process recovery, automated release checks, and clean-install validation remain planned.

Scope: OPS-01 through OPS-03 and DEV-01 through DEV-03.

- Durable local jobs with progress, cancellation, bounded retries, and restart recovery.
- Persistent passage indexing; bounded database reads and on-demand ZIP generation.
- Versioned database migrations and tested backup/restore.
- Automated checks and a clean-install guide using a reproducible dependency snapshot.
- Record performance on a 1,000-article library and declared reference hardware.

Exit targets: warm keyword search p95 below one second; library first page below two seconds; fetching and model generation do not block library browsing. Model latency is measured separately from application overhead. Validate installation on the declared supported Python/OS combinations before claiming support.

## M6 — User pilot

Status: planned; choose the initial audience before recruitment.

- Observe at least five target users completing capture -> organize -> research -> export.
- Run a two-week pilot; document repeat usage, time saved, missing capabilities, and willingness to pay.
- Use the results to choose integrations, monitoring features, and pricing experiments.

Exit: at least three of five participants use the tool on multiple days in week two, and the next product decision is backed by observed workflows. This is a learning gate, not proof of market fit.

## Optional hosted release

Status: deferred; not required for the local beta.

Requires explicit product scope plus authentication, tenant isolation, quotas, safe network egress, deployment monitoring, backup recovery, and security review. API/worker extraction and a server database are justified by hosting/concurrency needs or measured limits, not by a milestone date.
