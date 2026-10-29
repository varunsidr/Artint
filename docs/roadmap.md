# Artint: next-release plan

Status: Milestone A locally validated; Milestone B review tooling delivered, human review pending. General analytics and research usability fixes are implemented locally. Updated: 2026-10-29.

Execution steering: follow A (Linux/Docker/installation), B (reviewed extraction/evaluation), C (evaluated retrieval and saved research), then a small evidence-backed comparison. The capability groups below retain the detailed methodology; they are not a commitment to implement all future work together. Milestone A evidence and remaining hosted-runner gates are in [validation](validation.md). Keep evaluation baselines frozen before subsequent behaviour changes.

Working scope: an AI/SDET portfolio project that is also a useful local, single-user research application. Preserve the existing library and optional-local-AI workflow. Public multi-user hosting remains a separate decision. Phases below describe dependencies and acceptance gates, not promised dates or completed capabilities.

## Product direction

Help a researcher collect articles from several publishers, compare what those saved articles actually say, inspect the evidence, and retain an exportable research session. Local storage, optional local inference, portable evidence and cross-publisher comparison form a positioning hypothesis to validate with users; this is not a claim of market exclusivity.

The initial task is: collect several articles about one event or question, identify agreements and possible differences, inspect their quoted evidence, and export a brief. Saved article text is evidence of what a publisher reported, not independent proof that the report is true.

## What the reviews change

- Put evaluation infrastructure and an unchanged baseline ahead of retrieval/model changes.
- Validate installation and persistence before recruiting an external pilot. Docker is one installation path; it does not establish native macOS or Linux support by itself.
- Make an evidence-backed comparison of a small, user-selected story group the first differentiated feature. Retain current inspectable keyword filters as a navigation aid.
- Treat sample sizes, uncertainty, independent human review and answer coverage as part of the evaluation contract.
- Develop provider adapters, MCP, feed monitoring and richer archiving only after the main workflow is measured.

Existing work should be retained: transactional schema migrations through version 6, migration backups, article FTS5, embedding caching, portable merge restore, bounded browser capture and selected-import job state. The initial public baseline had 196 tests and a successful first Windows CI run. The latest local Windows checkpoint has 231 passing tests and one opt-in installation test skipped; the expanded hosted workflow is pending. These checks do not establish retrieval or answer quality.

Current delivery checkpoints:

| Work | State | Remaining gate |
| --- | --- | --- |
| A: installation and portability | Locally checked on Windows, Ubuntu/WSL2 x86_64 and Linux Docker | Expanded hosted CI; unsupported platforms remain explicit |
| B: extraction review tooling | Prospective freeze, phase/hash-bound reviews, eligibility and disagreement reports implemented | New eligible cohort, actual human labels/double review and research evaluation cases |
| General analytics and research usability | General/specialist separation, contextual filters, article handoff, readable previews/citations and bounded cache optimizations implemented | New changes need Linux/Docker revalidation; no answer-quality claim |
| C: evaluated retrieval and saved research | Planned | Reviewed baseline before hybrid ranking changes; durable sessions and immutable evidence |

Session reuse of the last answer is not a delivered persistent-research milestone. The cache/batching changes preserve passage construction, ranking, model defaults and generation budgets; the reviewed evaluation sequence remains in force. See [unreleased changes](../CHANGELOG.md) and [milestones](../milestones.md) for implementation evidence.

A single initial import commit is normal. Use meaningful commits and release notes going forward; do not manufacture a historical commit sequence. Maintain the unreleased changelog and publish a tag only when its documented release scope passes its gates.

## Competitor reference points

| Area | Relevant tools | Comparison question |
| --- | --- | --- |
| Self-hosted capture and preservation | [Linkwarden](https://docs.linkwarden.app/), [Karakeep](https://docs.karakeep.com/), [ArchiveBox](https://github.com/ArchiveBox/ArchiveBox) | How easy is capture, and what remains accessible when the original changes? |
| Local/personal AI research | [Khoj](https://docs.khoj.dev/), [AnythingLLM](https://docs.anythingllm.com/) | Can the user retrieve evidence, understand the answer and retain the workflow? |
| Cross-publisher news comparison | [Ground News](https://help.ground.news/en/articles/3189505) | How clearly are differences between reports presented and attributed? |
| Reading and reference workflows | [Readwise Reader](https://readwise.io/read), [Zotero](https://www.zotero.org/support/quick_start_guide) | How much effort does saving, annotating and citing take? |

These are feature/workflow references, not measured performance rankings. [Karakeep already exposes an MCP server](https://docs.karakeep.com/integrations/mcp/); MCP availability is an interoperability capability, not a defensible uniqueness claim. Ground News already offers comparison summaries. Artint must validate the usefulness of its particular local, evidence-preserving workflow.

## Phase 1: reproducible evaluation and baseline

Deliver the evaluation contract before changing the current chunking, semantic search, prompts or model defaults. Record the current source revision as the baseline, with a frozen corpus and configuration. Extend the existing extraction evaluator instead of creating a competing extraction-report format.

Deliverables:

- A versioned case schema: question, answerability, story group, source revisions, acceptable evidence spans/sets, required facts, exclusions, reviewer and label provenance.
- Gold evidence uses source text hashes and character spans, independent of the implementation's current `article_id:P1` chunks. Allow multiple valid evidence sets and distinguish sufficient multi-source evidence from a single relevant passage.
- CLI commands for retrieval-only runs, answer runs, human review and paired report generation. Store machine-readable results, a readable summary, per-case failures and configuration fingerprints.
- A small original synthetic CI set (initially 24 cases) validates the harness offline. Synthetic results are labelled as engineering diagnostics, not real-world quality evidence.
- Build a reviewed development set of approximately 60 questions, including at least 20 unanswerable cases. Use it to tune the system.
- Build a separately frozen held-out set targeting at least 200 questions, including 100 unanswerable cases. Include single-source, multi-source, conflicting-report and long-document cases; tags can overlap. Keep story families and syndicated/near-duplicate sources together when splitting to avoid leakage. This is a review workload and expansion target, not a guarantee of statistical precision.
- Freeze candidate configurations before held-out scoring. Do not tune against the held-out failures; version and replenish the test set for later development cycles.

Evaluation contract:

| Measure | Definition and reporting rule |
| --- | --- |
| Retrieval recall@5/@10 | Fraction of annotated relevant evidence units recovered, under a declared passage/context budget. Report per query and by case type. |
| MRR@10 | Rank of the first relevant result. Also report multi-evidence coverage: one relevant hit does not establish an answer to a multi-source question. |
| Claim support | Fraction of atomic generated claims fully supported by their cited saved passages. Partial support, missing citations, contradicted claims and unverifiable claims are separate failure categories. Report the actual claim denominator. |
| Citation quality | Report whether cited spans support each claim and whether all externally checkable claims are cited. Valid citation IDs alone are not a support score. |
| Abstention | Correct refusal on unanswerable cases, with its own case count. Also measure useful answer coverage on answerable cases so refusing everything cannot score well overall. |
| Extraction | Human-reviewed body completeness, title/date/author provenance and boilerplate checks on at least 100 predeclared eligible articles across at least 10 publishers. Retain attempted URLs, exclusions, access failures and per-publisher outcomes. |
| Performance | Retrieval and generation latency separately; cold/warm runs, hardware, corpus size, peak memory and configuration. |

The existing 95% supported-claim, 90% correct-abstention and 90% eligible-extraction targets remain aspirations until measured. Report counts and 95% confidence intervals. Claims within a question and questions about the same story are correlated: use a documented cluster-aware interval/paired comparison method, rather than treating every generated claim as an independent sample. Report uncertainty for per-type and per-publisher results too; a larger total does not make a small subgroup conclusive.

Distinguish an observed rate reaching a target from evidence establishing that target. A lower confidence bound below the target means the stronger claim is not established. Increase sample size or narrow the claim when uncertainty remains large; do not stop collecting because a favourable point estimate appears.

Human review is a dependency. Use a written rubric, hide model identity from reviewers where practical, double-label at least 20% of cases/claims, record agreement and adjudicate disagreements. A model may suggest labels, but cannot establish its own faithfulness score. Without human labels, publish automated diagnostics and leave the quality gates open.

Publish original/licensed fixtures, aggregate results, hashes and configuration. Publisher HTML, full reading text and private annotations stay local unless redistribution is explicitly permitted. Model identity includes the available model digest, quantization, runtime, prompt/chunk/retrieval versions and generation settings; temperature zero does not guarantee identical outputs.

Exit: another developer can reproduce a baseline run from permitted fixtures, understand every metric denominator and failure, and distinguish synthetic checks, automated diagnostics and human-reviewed results. This phase does not require the quality targets to pass.

## Phase 2: portable local installation and release hygiene

This follows the initial baseline and can progress while human labelling continues. It must precede the external pilot.

Delivery update: Milestone A delivered the Docker setup, diagnostics and Windows/Linux installation commands, with local verification as recorded above. Windows/Ubuntu/Docker CI definitions are present; expanded hosted runs, later-change revalidation and any macOS/GPU support remain separate gates. The list retains the acceptance scope and remaining extensions.

- Extend Python 3.13 CI to Windows, Ubuntu and macOS. Validate browser fixtures, Unicode paths, SQLite/FTS, PDF output, migrations, backups and actual restore behaviour on each supported environment. Record architecture and OS; do not infer universal support from one runner.
- Add a Dockerfile, `.dockerignore` and compose configuration. Include Chromium and required system libraries. Exclude local libraries, captures, secrets and generated artifacts from the build context. Use an unprivileged runtime and persistent app volumes.
- Start the app bound to host loopback by default. Library/notes/exports work without Ollama. Offer an optional CPU Ollama service/profile and a documented native-host endpoint; do not expose the model service publicly or silently download large models.
- Make GPU support an optional, separately validated path. Container access to a GPU differs by host; Docker success is not a claim of native Apple GPU acceleration.
- Verify first launch, health, restart persistence, a synthetic capture/reading flow, backup/restore across supported paths, and filesystem capabilities required by restore. Test named volumes and document bind-mount restrictions.
- Add Linux/macOS commands and an installation/model diagnostic. Validate a fresh install, not only an existing virtual environment.
- Maintain the changelog; add `pyproject.toml` for tooling and incremental Ruff checks. Add type checks to new evaluation/index/session interfaces first. Keep dependency declarations coherent; do not introduce a second unsynchronized dependency list.
- Report real test coverage and important untested boundaries. Add a coverage badge only when generated by a reproducible workflow. Prepare repository description/topics and a short synthetic demo recording for the release.

Proposed repository description for the current capabilities: "Local article research workspace with optional local AI, cited answers, coverage analytics, and portable research libraries."

Proposed topics: `python`, `streamlit`, `sqlite`, `ollama`, `rag`, `research`, `local-first`, `information-retrieval`, `article-extraction`. Add `llm-evaluation` when the harness is delivered, and update the description with claim comparison only after that feature ships.

Exit: a new user can follow the documented install path, run the application, restart it and recover a backup on the declared supported platforms. CI verifies those paths. Publish an explicitly scoped release; model quality remains reported separately.

## Phase 3: persistent hybrid retrieval

Requires the baseline and development evidence set. Preserve existing source/annotation fingerprints and use backed-up, tested migrations.

- Persist passages with stable revision-aware identities, source offsets and chunking versions. Add passage-level FTS5 and explicit index status. A source change invalidates derived index entries without silently rewriting old research evidence.
- Combine lexical and semantic candidates with reciprocal rank fusion, declared candidate/context budgets, duplicate/syndication handling and source-diversity controls.
- Keep a measured portable vector baseline. Add `sqlite-vec` or another index only after dependency, precision and performance checks justify it on all declared targets. It is an implementation candidate, not a prerequisite for hybrid retrieval.
- Show a retrieval trace: query, scope, index/model versions, lexical/semantic ranks, fusion/reranker result, selected evidence and omitted context. Similarity scores are not confidence in truth.
- Measure a reranker as a separate experiment against the hybrid baseline. Include it only when its quality gain justifies latency/memory; record failures and regressions.
- Add bounded, recoverable indexing jobs and visible stale/pending status. Retrieval must not rebuild the complete library or re-embed unchanged passages on every question.
- Introduce a narrow model-client protocol when needed by the harness/index work, retaining Ollama as default. Cache identity must include provider, model digest and embedding dimensions. Do not add multiple providers before the baseline exists.

Exit: fixed development comparisons show where hybrid retrieval helps or regresses; a frozen candidate receives a held-out report with uncertainty. Warm retrieval reuses its index, stale evidence is visible, and library browsing stays usable during indexing. Do not claim a quality improvement from speed or CI success alone.

## Phase 4: saved research sessions and exportable evidence

- Persist questions, source selections/revisions, retrieval traces, answers/abstentions, model/prompt settings and timestamps.
- Preserve immutable quoted evidence and source metadata for each saved answer. Distinguish old evidence from the latest article copy. Deletion and export must explain what retained session evidence contains and offer an explicit purge path; avoid hidden retention of deleted article text.
- Allow sessions to reopen, compare runs and export a Markdown brief plus structured citations. Add PDF brief export after the Markdown/evidence contract is stable. A research brief is separate from each article's reading PDF.
- Extend portable backups with a versioned session/evidence contract and tests for restore, idempotency, changed sources and supported older backups. Bound stored text and archive sizes.

Exit: capture -> organize -> ask -> inspect -> save -> restart -> reopen -> export works on the declared install paths. Exported statements resolve to their saved source revision even if the current article changes.

## Phase 5: evidence-backed cross-publisher comparison

Start with 2-5 user-selected articles about the same event. Manual selection avoids making unvalidated story clustering a prerequisite for the first useful comparison.

- Extract attributed claims with exact source spans, subject, quantity/unit, reporting period, qualifiers and speaker/source attribution where available. Preserve uncertainty and distinguish an article quoting someone from endorsing their claim.
- Align comparable claims and display a source-by-claim table with quoted evidence. Categories can include compatible statements, different measurements, potential conflict, not found in this saved copy and insufficient evidence.
- Do not equate different periods, units, estimates or revisions with contradictions. Do not label an outlet dishonest, biased or wrong from model disagreement. A missing claim is not proof of deliberate omission, especially when capture is incomplete.
- Surface capture warnings, document revision, syndicated/duplicate reporting and the article's publication date. Compare saved reports; do not imply representative coverage of the whole web.
- Build a reviewed claim-alignment/relationship set, including numeric/date mismatches and false-conflict cases. Evaluate extracted-claim support and relationship precision/recall, including abstention and human corrections, before promotion beyond preview.
- Add automatic story grouping only after event-match evaluation. Extend languages only with labelled cases and reviewed evidence for each language; switching to an LLM does not establish multilingual quality.

Exit: users can verify each comparison against its quoted text; unsupported relationships and false contradictions are measured. Keep it labelled experimental while these gates remain open.

## Phase 6: qualitative pilot and capture improvements

Recruit approximately five target users after portable installation and saved-session workflows pass. Run a two-week qualitative study with declared tasks and consented observations. Record setup failures, completion steps, citation errors, return use and user explanations. Describe these as observations about this cohort, not statistically established retention or market demand. Compare task times only when the tasks and method are comparable.

Use observed capture friction to choose a bookmarklet or extension, saved searches and feed subscriptions. First establish the bounded authenticated local capture interface; never expose a writable unauthenticated localhost endpoint to arbitrary webpages. A URL handoff must not execute page-supplied scripts or bypass access checks. Build retry/restart/cancellation semantics on the existing local job approach.

Exit: document what users could complete, where they failed and which change is justified next. Revisit positioning and the default workflow before adding broad integrations.

## Later options

- Read-only local MCP over stdio: search sources, retrieve revision-aware passages and read approved session evidence, with the same scope/size limits and source citations. Evaluate accidental disclosure, untrusted source instructions and cross-client behaviour before adding writes or network exposure.
- Additional provider adapters: a local OpenAI-compatible endpoint first if useful, then explicit opt-in remote endpoints with clear data routing and cost disclosure. Do not equate protocol compatibility with full structured-output, token-budget or embedding compatibility.
- WARC or single-file HTML preservation after the capture/evidence workflow is stable. This adds storage, active-content handling, asset fetching and viewing requirements; keep exported article PDFs described as reading copies.
- Broader type coverage, monitoring, scheduled feeds and richer annotation management according to pilot findings.
- Authentication, multi-user permissions and public hosting only under a separately approved product scope and threat model.

## Current implementation checkpoint

Milestone A is locally verified and stops at packaging, installation and sandboxed runtime checks. Expanded hosted CI still needs an authorized push; macOS is deferred rather than inferred from Docker.

Milestone B's tooling is implemented in the existing evaluator. Its quality gate remains open: complete a prospectively declared eligible cohort, human labels and independent double review, then prepare the research evaluation cases and frozen baseline. The current diagnostic cohort has no completed human-reviewed eligible cases and cannot establish the extraction target. Build reviewed development evidence before changing extraction/retrieval behaviour. Keep corpus collection/annotation and implementation changes separately reviewable; never invent human labels or publish a quality rate from synthetic fixtures.

Use small PRs with the problem, acceptance results, risks and migration effects. Record real evaluation results in the README only after the report exists; leave proposed targets visibly distinct. This plan does not schedule automatic commits, pushes, repository metadata changes or releases.
