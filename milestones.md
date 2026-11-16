# Milestones

Historical measurements and verification paths below refer to developer-local artifacts. `data/` and `output/` are excluded from the public repository. The reproducible public preview uses original synthetic fixtures; see [the README](README.md).

Accepted execution order: A portability/clean installation -> B reviewed extraction/evaluation -> C evaluated persistent retrieval and saved research -> a small evidence-backed cross-publisher comparison -> qualitative pilot and justified integrations. Preserve an unchanged evaluation baseline before changing capture/retrieval/model behaviour. See the [detailed plan](docs/roadmap.md) for methodology and release gates.

2026-11-09 priority update: complete the current human development review and publish a reproducible existing-pipeline baseline, then improve a 2-5-article same-story question/evidence/save/reopen/export workflow against measured failures. Evaluation tooling and saved research are already delivered; reviewed quality results remain pending. BERTopic stays a later optional corpus-navigation experiment, with usefulness, stability and local resource measurements required before integration. Topic discovery does not establish event matches or passage relevance. See [the next development cycle](docs/roadmap.md#next-development-cycle).

## Finer subtopics and local deployment — 2026-11-17

Delivered one bounded leaf-density refit inside each eligible parent theme, source-derived labels with generic reporting words filtered, child/remaining-source browsing and reader access for unassigned articles. Parent memberships, publication denominators and the original vector cache remain compatible. The 112-article library retained its 89/3 parent groups and 20 unassigned articles; the large parent now has five candidate children (9/5/4/3/3 articles), with 65 members retaining only the parent. All 612 vectors were reused. These candidate groups still need human usefulness review; BERTopic comparisons and answer-quality gates remain pending.

Verification: **516 Windows tests passed, two opt-in live checks skipped; 518 Linux tests passed with no skips**, plus warm-cache recreation. The Linux test-image retry used verified cached dependencies after a PyPI timeout, not a fresh dependency-install pass. The final panel-identity fix passed 40 targeted checks and real Chrome subtopic/remainder/export/dark/mobile acceptance. The backed-up local stack is healthy at **127.0.0.1:8502**; all stored tables, all 112 PDF manifests and 113 native file hashes were preserved. Private receipts, backups and the pending review packet are under `output/subtopics-20261116T182607Z/`. See the [detailed checkpoint](docs/validation.md#finer-subtopic-checkpoint--2026-11-17).

## Optional topic-enabled Docker validation — 2026-11-12

Completed both local Docker variants in disposable projects. Topics enabled: **512 Linux tests passed without skips**, plus a separate warm-cache browser check after app recreation. Lightweight default: **511 passed with one intentionally skipped topic-only UI check**, with the optional backend confirmed absent. Both passed installation/browser confinement, PDF/search/notes/saved-research restore and recreation.

A separate real-model smoke from the built image reached host Ollama 0.40.15 through the Compose host-gateway route, discovered three themes in the fictional fixture and reused all vectors with unchanged memberships. All storage was temporary; no container GPU or personal library was used. Both cleanups preserved 26 pre-existing containers and 10 volumes. The user stack/settings were not updated. The reusable `--topics` validator and base/topics CI matrix are implemented; hosted results and real-source coherence remain separate gates. See [Docker evidence](docs/validation.md#topic-enabled-docker-checkpoint--2026-11-12).

## Optional corpus topic discovery — 2026-11-12

User-authorized optional discovery is delivered independently of pending answer review: normalized article vectors, native HDBSCAN, source-derived class TF-IDF terms, representative/source inspection, outliers, exact-copy accounting, PCA exploration and adjacent-window publication shares. It runs only on explicit submission. A separate digest/endpoint/version cache and atomic new-vector commitment preserve normal retrieval caches and labels. Native setup and optional container build configuration are documented; labels, topic identity over refits and multilingual/event quality remain experimental.

Verification: **509 full Windows tests passed, one opt-in live-server test skipped**, with browser fixtures enabled. A separate real Chrome preview passed light/dark/mobile and point-to-theme selection. The live original fixture has 34 saved copies/32 distinct bodies and four expected themes; input-order memberships and warm-cache reuse pass. The final core calls took 2.667 seconds initially and 0.071 seconds cached on this small fixture, with stable observed model identity. No production-scale speed/coherence claim follows. Artifacts are `output/topic-discovery-20261111-release-check/`; research and remaining gates are in [topic discovery](docs/topic-discovery.md) and [validation](docs/validation.md#topic-discovery-checkpoint--2026-11-12).

## Full synthetic local-model run and persistence check — 2026-11-11

Executed the frozen original synthetic corpus through actual local Qwen models: **24 retrieval cases and 24 answer cases, zero runtime failures**, stable before/after inventories and 8K answer contexts. Answer pipeline median/p95: **2.861/6.723 seconds** in this one shared-cache diagnostic. One of eight declared-unanswerable questions returned timetable claims for actual passenger counts; preserve `cedar-3` for review. No prompt/ranking change follows automatically.

Prepared 24 fully pending answer reviews and 46 generated claims as initial review units, plus exact evidence packets and readable briefs. A separate two-source live question retained its original answer/evidence/metadata through explicit save, storage reopen and isolated portable restore. The personal library and private 60-case gold-review progress were not opened or changed. No quality target, independent support judgment or new full-suite/CI pass is claimed. Local evidence is `output/evaluations/research-20261111-live-baseline/checkpoint.md`; [validation](docs/validation.md#full-synthetic-live-model-diagnostic--2026-11-11) records hardware, timing boundaries and the still-running normal native Ollama profile.

## Workspace model observations — 2026-11-09

Delivered selected-manifest observations around explicitly requested new research questions and passage searches, with bounded metadata-only GETs, observation times, valid digests and whitelisted quantization/model details. Stable/changed/unavailable outcomes are retained in full JSON, saved research and portable backups; changed/incomplete notes stay in UI and Markdown briefs. Metadata failure preserves a successful answer. Navigation/source selection, identical-result reuse, saving, exporting and offline reopen do not reobserve models. Fresh results take new observations without rewriting old evidence or implying cache invalidation.

Verification: **475 full Windows tests passed with browser fixtures enabled, one opt-in live-server test skipped**. All 16 inference/evaluation source hashes match the separately preserved pre-change fixture snapshot. A real loopback inventory smoke found Ollama offline and correctly returned unavailable; the service was not started. Private receipts are in `output/research-model-observation-20261109/`. Stable/change cases are scripted tests, not a runtime quality benchmark. Complete inference/cache identity, human review and new Docker/hosted checks remain pending. See [validation](docs/validation.md#model-observation-checkpoint--2026-11-09).

## Request metadata foundation — 2026-11-09

Delivered versioned fingerprints for actual Ollama messages/schema and each attempted chat payload, per-attempt settings, requested/reported model names and observed runtime. Analyses/answers detach nested metadata from client state; full JSON, saved sessions and portable backups retain it. No additional HTTP calls or inference, ranking/prompt changes, schema migration or dependency is required. Older results remain readable. Exact weight identity, server defaults and reused embedding provenance remain unverified; this does not close AI-04's complete model-identity work or any human-quality gate.

Verification: **130 targeted tests passed; 447 full Windows tests passed with browser fixtures enabled, one opt-in live-server test skipped**. Preserved separate before/after engine snapshots and a 24-case paired synthetic diagnostic: zero failed runs, identical passages/fixture answers and zero retrieval-metric deltas. Artifacts are under `output/evaluations/research-20261109-{before,after}-request-metadata/` and `output/evaluations/research-20261109-request-metadata-comparison/`. This is diagnostic evidence; Docker/hosted CI and human quality remain pending. See [validation](docs/validation.md) and [request fingerprint semantics](docs/research-evaluation.md#request-fingerprints).

## Research source choice and workflow clarity — 2026-11-09

User feedback: analysis was reported as useful, but unrelated SAP/SpaceX-style test sources and a settings-first Research screen made the workflow confusing. This is qualitative feedback, not human gold approval or a measured quality claim. See [the feedback and short workflow](docs/research-workflow.md).

Delivered: Research shows collection/search before collapsed secondary filters, defaults to Article summaries, separates Ask a question and renders model setup after the workspace. Empty source selection means no question/batch sources; an explicit include-all option is bounded at 100. Source-context changes revoke selection/include-all. Selected titles can be inspected, single-article summaries narrow to the chosen group, and summary batches are capped at 25. Summary generation requires no embedding model. Existing offline summaries, saved research, result reuse, exports and reader handoff are retained.

Quick review now explains why development cases contain unrelated distractors and puts other-story copies in a clearly labeled group. All frozen case/source IDs and absence-check scopes remain unchanged. The existing quick-review page presentation was refreshed at the same file URL, preserving its payload/data hashes and browser progress key; a prior HTML copy was retained. No real human decisions were created.

The user's separately downloaded private progress was inspected: six user-confirmed revisions, 54 pending cases, story grouping unconfirmed. Their unrelated-source and uncertain-outcome notes are retained as supplied. The file is Git-ignored and has not been applied to a new approved corpus; this partial human review does not close Milestone B.

Verification: full Windows suite **436 passed, one opt-in live-server check skipped**; final targeted dashboard/batch-review suite **61 passed** with real browser tests enabled. Chrome checked a separate two-article fictional library: summaries open first, settings follow tasks, empty scope blocks submission, and selecting the ERP source excludes satellite-story text from the actual exported result. Light/dark/390px layout and no browser errors passed; the fixture uses a canned loopback model, not real quality evidence. The review packet passed three layout checks with no remote requests or human labels. Native article/PDF content and frozen proposals are preserved. Docker/hosted CI were not rerun for this UI-only checkpoint; the reviewed baseline and relevance/ranking improvements remain pending.

## Saved research and original evidence — 2026-11-05

Status: delivered explicit **Save research** and **Research → Saved research**. Answers, abstentions and passage searches reopen offline after restart, with immutable question/evidence/available run metadata, 20-row question search, identical-snapshot deduplication, source-change notices and confirmed deletion. Storage limits are 1,000 results, 256 KB per result and 64 MB total. An independent history revision invalidates prepared backups without invalidating source reuse. Source deletion previews and atomically purges related saved results/quotes; previous downloaded exports/backups remain independent copies.

Schema 7 adds session/source-link/state tables under the existing pre-upgrade backup and transaction. Library backup v2 validates records/link integrity, accepts v1, deduplicates restored snapshots, preserves original citations and handles local-ID remaps/conflicts/capacity rollback. Exact model-weight/prompt identity and comparisons remain follow-ups; original available tags/context metadata are preserved. Production retrieval, prompts, chunking and model/context/cache settings are unchanged, while the storage source/engine fingerprint changes explicitly. The prior frozen candidate remains intact, all 60 human decisions remain pending, and no reviewed RAG-quality improvement is claimed.

Verification: **431 Windows tests passed, one opt-in live-server test skipped**; **432 Docker tests passed, none skipped**. Functional dashboard AppTest navigation now consistently uses its existing 20-second startup allowance rather than defaulting later steps to three seconds; this is not a production latency change. Original hand-authored installer evidence survived actual container recreation and portable restore. A separate original 36-article/fake-model browser flow covered explicit/duplicate save, offline reopen, restart into a restored library, changed-source disclosure, byte-equivalent result fields except export time, light/dark/mobile behavior, backup download and confirmed deletion without more model POSTs. Fixtures were stopped after checks.

The running `artint` stack at **127.0.0.1:8502** was backed up and updated. Its original empty library remained empty, schema 7 and a pre-v7 SQLite backup were confirmed, and the Saved research view passed a browser check. The native 112-article/PDF library remains hash-identical. Private evidence is under `output/research-history-20261105/`; no commit/push or human label was created. See [usage](docs/usage.md#save-and-reopen-research) and [validation](docs/validation.md).

## Separate persistent Artint stack — 2026-11-05

Status: added the default Compose project name `artint` and a tracked local-settings example. Started the persistent local stack on **127.0.0.1:8502** with only the Artint service, its own `artint_default` network and `artint_library`/`artint_pdfs` volumes. It uses SQLite without Supabase. The local `.env` remains ignored. No native library migration was performed; the new container opens with an independent empty library.

Effective Compose config verified loopback/port/volume separation and confirmed explicit `-p` still changes the validation namespace. The running app passed health and a real Chrome UI check with zero page errors. Container mounts contain only its own named volumes, and all existing container IDs remained present. The app is left running. Private reports/screenshots are under `output/artint-stack-20261105/`. The personal library/PDFs and frozen research source hashes remain unchanged. This configuration change is locally checked; the existing hosted green run covers the preceding commit and the next push needs its own CI result. See [installation](docs/installation.md#separate-artint-stack-and-local-settings) and [validation](docs/validation.md).

## Local Docker installation/recovery follow-up — 2026-11-05

Status: completed the local disposable Compose validation on Docker Desktop Linux engine 29.7.2 after startup authorization. **405 tests passed with no skips**, including browser policy/batch fixtures and the live UI. Actual Chromium sandbox status, runtime confinement, isolated backup/restore, force-recreation persistence, PDF/search/notes and test-image startup all passed. No runtime code or dependency change was needed.

The validator removed its containers, network and volumes. An independent cleanup check found no remaining project containers/volumes and confirmed all 19 pre-existing container IDs remain present. Docker Desktop is left running; stopping it would stop unrelated workloads. Private logs/reports are under `output/release-validation-20261105/`. The personal library/PDFs and frozen research source hashes are unchanged. See [validation](docs/validation.md).

## Installation, recovery and hosted CI verification — 2026-11-05

Status: verified the successful [three-job hosted run](https://github.com/varunsidr/Artint/actions/runs/41449916277) matches current implementation commit `dc6ef1e`. Windows and Ubuntu jobs passed dependency installation/checks, browser sandbox checks, the regression suite, synthetic demo/research fixtures, isolated PDF/search/restore and live native UI steps. Docker's job passed the disposable container validator, which checks non-root/loopback/sandbox settings, isolated restore, force-recreation persistence and the test image's full suite/live UI. Public job/step conclusions were checked; authenticated runner logs were not downloaded and no new hosted test counts are inferred.

A separate clean Git archive/fresh Microsoft Store CPython 3.13.14 Windows environment passed runtime dependency installation/checks, the existing installed Chrome path, offline backup/restore, **404 tests with one opt-in installation test skipped**, and the separate passing live search/reading/notes/PDF test. A deeply nested first path failed installing `lxml`; a shorter isolated path succeeded without system-setting changes. One three-second Analytics AppTest timeout passed alone and on a serial full recheck without runtime/test changes. These first attempts remain in the private record. Updated setup/publishing docs explain the short-path workaround and `python -m venv` alternative when `py` is absent.

Private evidence: `output/release-validation-20261105/`. The canonical personal library/PDFs and frozen core research source hashes remain unchanged. Docker Desktop was left stopped during this earlier step; the subsequent authorized local Docker follow-up above records its separate validation. No models, publisher content, releases or additional pushes were required. Human-reviewed extraction/research quality and unsupported-platform gates remain separate. See [validation](docs/validation.md).

## Coverage analytics and collection readiness — 2026-11-02

Status: added four indicators for adjacent 30-day publication volume, leading/top-three publisher concentration, analysis coverage and date availability. Publisher rows add analysis percentage/latest publication date. General analytics adds a six-topic/five-publisher saved-label matrix with all-publisher reach and linked source inspection, plus author/label/capture-check/flag/unknown readiness counts. Duplicate labels count once per article; stale analyses contribute no topics. Missing labels do not establish publisher omissions, capture flags do not establish factuality, and publisher labels do not establish ownership or independence. Every aggregate uses the full active source scope and its notebook/CSV predicates; no model runs automatically. Cache keys now include calendar day.

Verification: **404 Windows tests passed, one opt-in installation test skipped**. **18 targeted native Ubuntu/WSL2 analytics tests passed**. Separate Chrome checks on an isolated original 36-article demo exercised cell selection by keyboard, matching CSV membership, status/empty states, specialist switching, themed tooltips/Escape, light/dark layouts, 390px table scrolling and text sizes of at least 12px without page errors/overflow. Its synthetic readiness records are not quality measurements. Public competitor references and metric definitions are in [usage](docs/usage.md). Existing library/PDFs and frozen core research source hashes remain unchanged; human gold review and the measured RAG baseline remain pending. See [validation](docs/validation.md).

## Targeted publisher promotion cleanup ? 2026-11-02

Status: normal and browser captures remove complete standalone blocks matching the publisher-home/social/newsletter template reported in the TechTrendsKE article. Cleanup is link-aware and conservatively preserves quotations, mixed reporting, structural containers and subsequent article headings/paragraphs. New text, link metadata, reading PDFs and research passages receive the cleaned body; capture coverage uses the same DOM rule and records its version/count. Extraction reports/review evidence fingerprint the new dependency and reject incompatible resumes/frozen-helper replay.

Verification: **398 Windows tests passed, one opt-in installation test skipped**; **69 targeted native Ubuntu/WSL2 capture/cleanup/evaluation tests passed, one opt-in browser test skipped**. Cases cover promotion position/wrappers, split blocks, malformed links, quotation/editorial preservation, minimum body length, PDF/RAG evidence and remaining missing-content diagnostics. One affected already-saved article was identified read-only. Existing library/PDFs and frozen research artifacts remain unchanged; saved-copy reprocessing is a separate operation. These are regression checks, not a reviewed extraction-quality percentage. See [validation](docs/validation.md).

## Research result recovery and provenance ? 2026-11-02

Status: failed requests preserve the last completed answer and downloads. Offline inventory and changed/empty filters keep that result visible with its original scope; an explicit clear action removes only session result/error state. New answer/passage-search exports record completion time, selected/loaded source IDs, fingerprints of the loaded copies, library revision, mode, models and applicable context policy. Export timestamps are separate. Markdown links handle international domains/paths, ports and IPv6 while JSON preserves original URLs. Near-full mixed GPU memory stays labelled as mixed rather than rounding to 100%.

Windows: **377 passed, one opt-in installation test skipped**. Targeted native Ubuntu/WSL2: **159 passed, one opt-in batch-browser test skipped**. An isolated 36-article synthetic browser check verified failed-request/offline/empty-filter recovery, unchanged downloaded evidence, explicit clearing, no extra model POST on export, both themes and 390px layout. No actual model inference was run. Personal-library/PDF and frozen core-source hashes remain unchanged; all 60 real human decisions remain pending. Durable sessions, reviewed gold data and the measured baseline remain future work. See [validation](docs/validation.md).

## Research diagnostics and portable briefs — 2026-11-02

Status: added explicit model-status snapshots in Research settings and `check_install.py --ollama`, distinguishing installed, loaded, missing, offline and unknown residency states. Checks read bounded metadata only, report the selected server's memory placement/context/runtime, preserve default model-service-independent installation checks and never load a model or infer the client's GPU identity. The UI follows light/dark variables, escapes metadata, supports narrow-screen scrolling and clears stale endpoint/model snapshots.

Research answers/passage searches now export a cited Markdown brief and complete versioned JSON without another model call, page rerun or storage write. Original URLs/exact cited passages are retained; missing references and unsafe links are rejected, and model/source markup remains literal. These are downloadable snapshots, not durable saved research sessions or verified answer-quality improvements.

Frozen inference/storage source hashes, model/context/cache defaults and all personal library/PDF hashes remain unchanged. The private 60-case batch remains entirely pending for later human review. Actual browser checks used an isolated original 36-article demo and simulated metadata/answers; they establish workflow behavior, not GPU performance or model quality. See [validation](docs/validation.md) for current regressions and platform limits.

## Consolidated batch review — 2026-11-02

Status: pre-reviewed all 60 proposed cases as AI-assisted authoring and prepared one offline batch page for later human checking: **37 suggested revisions, 22 flagged source checks, one proposed keep**, with **zero human decisions**. The flags include all 20 proposed unanswerable cases plus two cases with image-caption/capture concerns. Proposed revisions replace generic expected-fact placeholders, correct choices-versus-participants and prices-versus-demand denominators, fix speaker attribution and forecast/period wording, add missing supporting spans, remove irrelevant evidence and permit corroborating passages as alternatives where appropriate. These remain proposals about saved copies, not verified external facts or approved gold labels.

Added `prepare-batch-review`, a source/case-hash-bound suggestions contract and an offline overview grouped by story family. Users can compare original/proposed cases, inspect all 23 scoped source copies, select/filter cases and record reviewed selections together, exclude with reasons, preserve pending edits and export/resume the standard review JSON. Flagged-case confirmation and source-family review remain separate explicit actions. Initial selections, decisions and reviewer identity remain empty. The private ready packet is `output/development-eval-20261102/batch-review-ready/`; earlier single-case packets/proposals are preserved.

Production RAG, model settings, library data and the prior engine snapshot remain unchanged. Review tooling source has changed and will be fingerprinted separately by subsequent runs; this is not a silent replacement of the frozen candidate. Human review, approved-corpus freeze, independent review and the measured baseline remain next. See [batch instructions](docs/research-evaluation.md#review-suggestions-as-one-batch) and [validation](docs/validation.md).

## First guided gold-review session — 2026-10-31

Resumed 2026-11-02: no exported human decisions were found in the review session or the targeted Downloads review files. All 60 decisions remain pending. A separate code/config candidate was captured under `output/research-baseline-20261102/engine-candidate-01/` with verified file hashes and the expected 8B/f16/adaptive-context settings. This snapshots the engine only: no human-approved corpus was frozen and no measured baseline was run. The local model service was unavailable during the read-only identity check; it was not started. The first case's suggested revision and reviewer provenance are awaiting actual user judgment.

Status: validated the existing 60-case/23-source development proposal and partial review contract; all 60 labels/decisions remain unreviewed/pending. Prepared an offline review session with machine pre-review notes for `roman-glass-q1/q2/q3` and a separate suggested Q1 revision. The suggestion corrects cooling-temperature wording and proposes a sufficient evidence set aligned with the three required facts; it is not applied or counted as human-approved gold. The original corpus hash, source texts, case scopes and proposal files are preserved.

Private session artifacts are under `output/development-eval-20261031/review-session-01/`, including a short start guide, all full scoped source copies inside the review page, pending review JSON, suggested case JSON and structural/browser checks. Chrome checks passed visible notes, three full scoped copies, light/dark/mobile layout, zero remote requests/page errors and zero decisions created. Human case/absence/family review is the next required input; the baseline/quality gate remains unestablished. No production app/model/retrieval changes were made for this session.

## Opt-in cache profile and model comparison — 2026-10-31

Status: `-KvCacheType q8_0` implemented as an optional native Windows GPU profile, with default `f16`, requested-settings manifests, actual cache/offload verification and unchanged app model defaults. Compared Qwen3 8B/f16, Qwen3.5 9B/f16 and Qwen3.5 9B/q8 on six declared original synthetic questions with two shared-cache repeats each: 36 successful observations, all at 8K. Quantized 9B still used mixed CPU/GPU memory and was slower than 8B in this small diagnostic. Server-wide quantization changed some retrieved passages even though measured synthetic recall/sufficiency was unchanged. Human support reviews remain pending; no model-quality improvement or default promotion is established. The ordinary 8B/f16 server was restored. See [the experiment record](docs/validation.md#opt-in-kv-cache-experiment--2026-10-31) for timings, abstention behavior, limits and recovery checks.

## Adaptive context and native GPU checks — 2026-10-31

Status: automatic 8K/16K generation context implemented with a disclosed UTF-8 estimate, 1,600-token answer reserve and 512-token margin. Checked Ollama controls disable prompt truncation/context shifting. An underestimated 8K request retries its complete evidence at 16K; oversized 16K requests fail without saving a shortened answer. Actual token counts can also trigger expansion to preserve answer space. Model defaults, output budget, retrieved passages and cache precision are retained. Existing fixed-16K evaluator snapshots remain preserved; this is a new generation-policy candidate pending human quality comparison.

Five live synthetic application checks covered initial 8K, initial 16K, overflow retry, actual-token answer-reserve retry and 16K rejection. Three original synthetic Qwen research cases completed with 8K metadata captured by the evaluator; these are operational checks, not an answer-support score. The RTX 5050 loaded `qwen3:8b` entirely on CUDA at 8K, versus mixed CPU/GPU placement at 16K. Installed `qwen3.5:9b` still used mixed memory at 8K; a small cold/warm comparison does not establish general model quality or performance. The default remains `qwen3:8b`. See [validation](docs/validation.md) for verification and limits.

Milestone B remains in development gold review with zero human-approved cases. These hardware/context changes do not complete the reviewed baseline or authorize skipping it before hybrid retrieval work.

## Development proposals and human gold-review workbench — 2026-10-30

Status: real-source development proposals prepared; **zero human-approved cases**. Used an explicit prospective 20-group selection from the 112-source personal library, read through a SQLite read-only transaction without migrations. The private candidate corpus has 60 questions (40 proposed answerable, 20 proposed unanswerable), 23 source copies from 17 publishers and 19 proposed story families. The remaining 89 sources are unassigned, not certified independent held-out data. Source types/capture completeness and grouping still need human review.

Added `prepare-development`, `prepare-gold-review` and `apply-gold-review` to the existing research CLI. Drafting uses installed local Qwen and bounded original-text anchors, records model/source snapshots and preserves failed groups. All expected facts and absence judgments remain unreviewed. A spot check found negative drafts about known distractor facts; machine refinements and their original versions were retained rather than calling them human-adjudicated. Only exact span identity, not semantic correctness or absence, is machine-validated.

The self-contained local review page provides full scoped text, proposed evidence highlights, question/fact edits, Unicode-correct text selection for new spans, revisions/exclusions, family-map review and partial JSON download/import. It supports light/dark and mobile without publisher requests or a local server. Applying declared human decisions creates a new corpus only after all cases/grouping are checked and hashes/scopes/spans/provenance agree. Optional independent-review disagreements block application. The tool invokes no model as judge, requires declared human provenance and certifies no quality target; reviewer identities are not authenticated.

Verification: **286 Windows tests passed, 1 opt-in live-server installation test skipped**; **55 targeted research/gold-authoring tests passed** in the existing Ubuntu/WSL2 Python 3.13 environment. Separate Chrome checks passed edits, export/resume, literal markup, emoji/code-point evidence offsets, both themes, 390px layout, zero remote requests and the actual 60-case page with zero approvals. All table/PDF hashes for the existing 112-article library remain preserved; application RAG/UI source is unchanged. A full test run during model drafting hit an existing three-second Streamlit timeout; the full rerun passed after drafting finished. The existing Ollama installation was started on loopback for authoring, with no model downloads. Docker/hosted CI remain unverified for these changes.

Next human action: review the private candidate cases and source-family grouping, independently double-review a subset, correct/exclude ambiguous cases and apply decisions to a new corpus. Freeze that approved development corpus before running the baseline and tuning retrieval. The proposed 60/20 counts do not mean the reviewed-development target or any model-quality gate has passed. See [authoring instructions](docs/research-evaluation.md#prepare-real-development-proposals-and-review-gold-labels).

## Research evaluation foundation — 2026-10-30

Status: first harness implemented locally; human-reviewed quality gates remain open. Baseline source revision `4ef742b` is recorded per run from Git; exact pipeline/harness source snapshots also identify uncommitted work. The existing application RAG functions, model defaults, prompts, chunking and ranking are unchanged.

Added `scripts/evaluate_research.py` and its small tooling package: versioned case/schema validation, prospective corpus freeze, source/capture hashes and gold character spans, alternative sufficient evidence sets, isolated cold/shared embedding caches, retrieval/answer runs, model/runtime/config fingerprints, per-case failures and interrupted journals. Reports include recall/sufficiency, MRR, declared response/abstention diagnostics, timing and story-clustered intervals. Human review packets retain atomic claims, citation support, required facts, pending labels and declared independent reviewers. Compatible run pairs are compared from frozen source spans independently of later chunking. No report certifies a release quality percentage.

The original public corpus contains **24 synthetic cases across eight fictional families** (16 answerable, eight unanswerable) and 16 original sources. It exercises multi-source, conflicting, numeric, temporal, alternative, Unicode, injected-source and long-document cases. The fixture engine is a scripted diagnostic rather than Qwen or a semantic quality benchmark. Private corpus/answer/review data remains under ignored `output/`.

Verification: unchanged Windows baseline **231 passed, 1 skipped**; with the new harness **268 passed, 1 opt-in live-server installation test skipped**. The **37 targeted harness tests** and a 24-case offline answer run also passed on the existing Ubuntu/WSL2 Python 3.13.14 environment; this is not a fresh installation or full post-change Linux app validation. Actual local Qwen embedding retrieval and `qwen3:8b` answers each completed three declared synthetic cases without pipeline failures. Review packets remain pending with no human support rate. All real-library table/PDF hashes were preserved. Docker packaging/CI were updated, but the new test image was not built because the Docker daemon is stopped; hosted jobs were not run by a push.

Next: author and human-review approximately 60 development questions (at least 20 unanswerable), retain a separately frozen held-out plan, and finish the independent extraction review. Only then use measured candidates to change retrieval. Persistent hybrid indexing, durable research sessions and claim-level comparison remain future work. See [research evaluation instructions](docs/research-evaluation.md).

## Documentation preparation before push — 2026-10-29

Updated the README, architecture, acceptance requirements, operating guide, roadmap, publishing instructions and validation record to distinguish current general analytics/research usability from planned evaluated retrieval. Added an [unreleased changelog](CHANGELOG.md) and refreshed the general-analytics screenshot from the original isolated 36-article synthetic demo, with no publisher/model calls. Corrected the legacy extraction-review instructions and initial-repository publishing steps. Runtime dependencies and schema version 6 are unchanged. No commit, push, tag, release or image publication is performed by this documentation update.

## General analytics and research usability — 2026-10-29

Status: implemented locally. Analytics now defaults to general collections and supports any topic: publication activity, publisher distribution, current default-model analysis coverage, saved topic labels, analysis-status filtering and reading profiles. Short spans use zero-filled daily bins; longer spans retain bounded monthly data. Topic/status/day filters share notebook/export membership. AI investment lenses, aliases, argument cards and bubble wording require the explicit specialist view. Missing saved topics are disclosed instead of replaced with investment labels. Analytics labels are at least 12px; source previews remove Markdown/image destinations without changing saved text.

An empty reading-room analysis links directly to Research focused on the exact article, preserves existing filters and starts no automatic analysis. Offline/deleted articles are handled. Pagination uses compact Previous/page-jump/Next controls with a mobile-safe jump menu. Answer cards expose their cited source passages directly.

Research batches embedding-cache reads (256 hashes per SELECT) and keeps the same embedding model loaded between 16-input batches, requesting unload after the final batch. Exact repeated questions may reuse the last session answer while mode/source revision/models/endpoint are unchanged, with a fresh-result bypass and visible retrieval/timing details. The model, generation budgets, input passages, cosine ranking and six-passage retrieval are preserved; persistent indexing, durable research sessions and reviewed answer-quality improvements remain Milestone C/M4 work.

Verification: **231 tests passed, 1 opt-in live-server installation test skipped**, including actual browser extraction. Separate synthetic live-UI checks cover general/specialist mode changes, topics/status/day filters, CSV membership, readable labels, light/dark/mobile layouts, compact pagination and article handoff. All table hashes and **112 real article/PDF hashes** were preserved. Dependency and whitespace checks passed. New changes have not been pushed, released or revalidated on Docker/Linux.

Developer-local performance evidence (`output/research-ux/`, excluded from Git): an alternating eight-repeat 2,000-vector cache lookup returned identical vectors with 2,000 SELECTs reduced to eight; median cache lookup was 93.7ms before and 20.8ms after. This is cache-only, not an overall model-speed claim. The existing public `scripts/benchmark_observatory.py` now measures general and specialist modes explicitly, with dense synthetic topic labels and an optional output filename. General SQL snapshot medians were 39.8ms for 1,000 seeded articles (917 matched date bounds) and 446.2ms for 10,000 (9,167 matched), over 15 rounds. Browser paint, network, PDF generation, model inference and concurrency are excluded. No fresh Qwen-answer or human-support benchmark was run; Milestone B's reviewed-quality gate remains open.

## Context-aware filter correction — 2026-10-29

Status: implemented and verified before Milestone B work. Library/Research split general and topic filters; scoped SQL derives current saved labels/tags from all matching articles rather than the global library or first page. Stale labels clear across topic/model/metadata changes, compatible values survive navigation, and unanalysed scopes show an explicit empty state. AI investment Library lenses/companies are opt-in and contextual. Discovery wording separates topic refinements from general controls.

Verification checkpoint: 209 tests passed with the separate live-server test skipped; synthetic browser checks passed layoffs -> glass -> Library, dark/light themes, mobile width and absent-analysis states. The current 106-article library was hash-baselined separately from Milestone A. A fresh Docker rerun was not executed because its daemon was stopped; earlier A results remain historical evidence.

## B — Reviewed extraction/provenance — tooling started 2026-10-29

Status: review tooling implemented; human-reviewed quality gate remains open. Extended `scripts/evaluate_extraction.py` with prospective candidate/protocol freeze, exclusive phase/hash-bound review creation, reading-copy integrity checks, explicit eligibility/exclusion/failed-capture accounting, source-kind/host strata, descriptive Wilson intervals and second-review disagreement reporting. Existing phase results and the legacy checklist are preserved. No extraction heuristics were changed to chase scores.

The current 100-source diagnostic cohort has 78 captures, 22 failures and **zero human-reviewed eligible cases**. Its new phase checklist has 100 pending rows, a null reviewed pass rate and a false gate. It remains a convenience sample; a new prospectively declared eligible cohort and actual human labels/double review are needed. See [review instructions](docs/extraction-evaluation.md).

Combined verification: **220 tests passed, 1 opt-in live-server test skipped**; dependency checks pass. Synthetic browser checks confirm layoffs/glass scope changes, stale-selection repair, unavailable AI controls hidden, light/dark themes and mobile width. Rare labels remain selectable outside the global top-100 overview. All real-library table hashes and 106 PDF hashes are preserved. Docker revalidation remains not run while its daemon is stopped. Changes remain local.

## A — Linux, Docker and clean-install reliability — 2026-10-29

Status at the original checkpoint: local validation complete for Windows, Ubuntu 26.04 WSL2 x86_64 and the Debian/Python 3.13 Docker image. Follow-up on 2026-11-05 verified successful hosted Windows/Ubuntu/Docker jobs for `dc6ef1e`; the Ubuntu conditional AppArmor setup and sandbox-check steps report success. Individual conditional-branch execution is not inferred from the public step summary; native macOS, ARM64 and GPUs are not declared supported. See [commands and matrix](docs/validation.md).

- Reused existing SQLite/PDF configuration, CLI, worker, extraction policy and optional Ollama. Retained schema version 6 and verified hashes for all original tables and 105 reading PDFs.
- Added a digest-pinned Python/browser multi-stage image, recorded Linux runtime dependencies, deny-by-default Docker context, loopback-only Compose service and isolated persistent volumes. Runtime/test targets are separate.
- Explicitly enabled Chromium sandboxing; verified namespace/PID/network/seccomp status. Kept non-root, dropped capabilities, no-new-privileges and read-only runtime while adding only the documented namespace-local `chroot` syscall allowance to the upstream profile.
- Added read-only install diagnostics, isolated PDF/search/restore checks and disposable native/container live UI validation. Added Ubuntu and Docker CI definitions alongside Windows with pinned actions and a scoped Ubuntu AppArmor allowance rather than global policy disablement.
- Results: Windows and fresh native Ubuntu each passed **203 tests with 1 opt-in live-server test skipped**, plus a separate passing live UI test. Docker passed **all 204 tests**, including real capture and live search/notes/PDF. Synthetic demo, force-recreation persistence, backup/restore, hard links and actual private-file context exclusions passed.
- Documented install, optional model networking, explicit migration, recovery, clean removal, download/cache issues and supported versus unverified paths. No remote push, release or image publication was performed.
- Next: the independently reviewed extraction/evaluation milestone. Installation tests establish no extraction or AI quality percentage.

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

- Deliver a versioned evaluation harness and unchanged baseline first. Original synthetic cases validate the harness without establishing model quality. Build a reviewed development set, then expand toward at least 200 held-out questions including 100 unanswerable cases, keeping story families and duplicates together across splits.
- Add keyword/semantic hybrid retrieval, source diversity, and evaluation-driven reranking.
- Add token-aware budgets and staged summaries for long articles.
- Persist research history and export research briefs with evidence references.
- Version model identity, prompts, chunking, and caches for reproducible evaluation.

Exit targets: at least 95% of evaluated atomic answer claims supported by their cited text; at least 90% correct abstention on the unanswerable subset. Report actual question/claim denominators, answerable-case coverage, retrieval recall@5/@10, MRR@10, multi-evidence coverage, rubric, model, hardware, latency and failures. Human labels and adjudication, including a double-labelled subset, are required for quality claims. Use cluster-aware 95% confidence intervals; distinguish an observed target from one established by its lower confidence bound. Automated citation-ID validation or model self-grading alone cannot satisfy this gate. Preserve immutable session evidence with explicit retention/purge semantics and a versioned portable backup contract.

## M4.1 — Evidence-backed cross-publisher comparison

Status: proposed; depends on evaluated retrieval and saved sessions.

Scope: AI-05. Begin with 2-5 user-selected articles about one event. Extract attributed claims with exact source spans, units, periods and qualifiers; present a source-by-claim comparison with inspectable evidence. Distinguish possible conflict, different measurements and insufficient evidence. Retain capture warnings and document revisions. Automatic story grouping, truth/bias labels and multilingual quality claims require separate evaluation.

Exit: report human-reviewed claim support, relationship precision/recall and false-conflict errors. Comparisons remain experimental until their gates pass and are included in the session/export/backup contract.

## M5 — Responsive, installable local beta

Status: in progress. Bounded browsing/analytics/exports, backed-up schema migrations, portable merge restore and deletion recovery, isolated 1,000/10,000-record measurements, and persistent selected-discovery import batches with leases/progress/cancellation are delivered. Generalized ingestion/analysis/index jobs, automatic retry policies, persistent semantic passage indexing, broader cross-process recovery, automated release checks, and clean-install validation remain planned.

Scope: OPS-01 through OPS-04 and DEV-01 through DEV-03. Portable installation proceeds after the baseline and before the external pilot; human evaluation labelling can continue alongside it.

- Durable local jobs with progress, cancellation, bounded retries, and restart recovery.
- Persistent passage indexing; bounded database reads and on-demand ZIP generation.
- Versioned database migrations and tested backup/restore.
- Automated checks and a clean-install guide using a reproducible dependency snapshot.
- Windows/Ubuntu/macOS CI and declared fresh-install environments; Docker/compose with persistent volumes and optional Ollama. Verify actual restart/restore behaviour and filesystem assumptions. Validate GPU paths separately.
- Record performance on a 1,000-article library and declared reference hardware.

Exit targets: warm keyword search p95 below one second; library first page below two seconds; fetching and model generation do not block library browsing. Model latency is measured separately from application overhead. Validate installation on the declared supported Python/OS combinations before claiming support.

## M6 — User pilot

Status: planned; choose the initial audience before recruitment.

- Observe at least five target users completing capture -> organize -> research -> export.
- Run a two-week qualitative pilot after portable installation and saved-session workflows pass; document setup failures, task completion, citation errors, repeat usage, missing capabilities and user explanations. Report time comparisons only with a declared comparable-task method.
- Use the results to choose integrations, monitoring features, and pricing experiments.

Exit: document the observed workflows, failure points and the next product decision they justify. Return use in a five-person cohort is qualitative evidence, not a statistically established retention rate or proof of market fit. Choose capture integrations and monitoring features from these findings.

## Optional hosted release

Status: deferred; not required for the local beta.

Requires explicit product scope plus authentication, tenant isolation, quotas, safe network egress, deployment monitoring, backup recovery, and security review. API/worker extraction and a server database are justified by hosting/concurrency needs or measured limits, not by a milestone date.
