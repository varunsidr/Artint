# Artint: next-release plan

Status: Milestone A installation/recovery checked locally and hosted Windows/Ubuntu/Docker CI verified for `dc6ef1e`; extraction/research evaluation tooling, a private 60-case development proposal and an offline batch-review workbench are delivered. Model-status diagnostics, portable research briefs and last-result session recovery are implemented independently of retrieval. Saved-source coverage indicators and explicit durable research snapshots/backups are also delivered without inference. Full original-synthetic retrieval/answer runs and a two-source live persistence check are recorded; a completed human-approved gold corpus remains pending. Updated: 2026-11-12.

Execution steering: follow A (Linux/Docker/installation), B (reviewed extraction/evaluation), C (evaluated retrieval and saved research), then a small evidence-backed comparison. The capability groups below retain the detailed methodology; they are not a commitment to implement all future work together. Milestone A evidence, commit-specific hosted results and remaining platform limits are in [validation](validation.md). Keep evaluation baselines frozen before subsequent behaviour changes.

Working scope: an AI/SDET portfolio project that is also a useful local, single-user research application. Preserve the existing library and optional-local-AI workflow. Public multi-user hosting remains a separate decision. Phases below describe dependencies and acceptance gates, not promised dates or completed capabilities.

## Product direction

2026-11-08 steering: the user reported useful analysis but confusing unrelated sources and a settings-heavy Research screen. Deliver task/source clarity before further retrieval changes: summaries first, explicit question scope, selected-title review and secondary setup. Evaluation distractors must be labeled as test conditions, never implied story connections. See [the recorded feedback, workflow and remaining relevance work](research-workflow.md). This usability correction does not close Milestone B or certify relevance; hybrid ranking and a tested insufficient-evidence policy still follow the reviewed baseline.

Review update, 2026-11-09: the user's private progress contains six revised approvals and 54 pending cases, with story grouping unconfirmed. Preserve this partial review and its source-relevance notes; do not apply it as a completed corpus or treat the remaining cases as approved.

Help a researcher collect articles from several publishers, compare what those saved articles actually say, inspect the evidence, and retain an exportable research session. Local storage, optional local inference, portable evidence and cross-publisher comparison form a positioning hypothesis to validate with users; this is not a claim of market exclusivity.

The initial task is: collect several articles about one event or question, identify agreements and possible differences, inspect their quoted evidence, and export a brief. Saved article text is evidence of what a publisher reported, not independent proof that the report is true.

## Next development cycle

New user steering, 2026-11-11: improve topic discovery using competitor approaches and current research. Deliver this as an independent, optional experiment now; retain the reviewed-baseline requirement before question-retrieval, prompt or cache-policy changes. The first density-based discovery workspace is implemented with a map, representatives, source terms, outliers, exact-copy accounting, publication shares and a separate digest-aware cache. Its synthetic/native-browser checks do not close real-source topic/answer-quality gates. See [the implementation and research record](topic-discovery.md).

Accepted steering, 2026-11-09: prioritize a measured, dependable research workflow. Position Artint as a local evidence-preserving research application; treat BERTopic as a possible topic-discovery component. Saved per-article AI labels, corpus-level topic discovery, same-event grouping and question-specific passage retrieval solve different tasks. Broad feature scope and subjective project ratings do not establish usefulness or model quality.

1. **Complete review and measure the existing pipeline.** Continue the current private development review, retaining the six revised approvals, 54 pending decisions and source-relevance notes. Complete case/absence/story-family checks and the declared independent-review process, then freeze a newly approved corpus and current engine/configuration identity. Use the delivered harness to report retrieval coverage, sufficient multi-source evidence, human-reviewed claim support, abstention alongside useful answer coverage, latency and observed failures. Preserve prior frozen candidates. Keep the extraction-review gate open until its separate evidence exists.
2. **Improve one small research workflow against those failures.** Select 2-5 articles about the same story, ask a scoped question, inspect the supporting passages, save the result, restart/reopen it and export a brief. The source-selection and saved-evidence features already exist; demonstrate their usefulness with reviewed cases before expanding scope. Evaluate retrieval and insufficient-evidence changes against the unchanged baseline. Add claim comparison under Phase 5's separate acceptance gates; automatic event grouping is unnecessary for this first workflow.
3. **Validate the optional discovery experiment.** The user-authorized density baseline now runs independently of saved labels and question retrieval. Next compare human judgments, outliers, stability and costs on a frozen permitted real corpus; benchmark BERTopic or other candidates against the same representation and data. The current dated share comparisons describe one fitted saved corpus. Emerging-theme claims and longitudinal identity alignment require further validation.

The immediate milestone is a reproducible baseline report with declared review provenance, case/claim counts, failure examples and one inspectable same-story research brief. Existing synthetic checks and smoke runs remain diagnostics. Quality targets remain open until measured; publish improvements only after paired evaluation and the applicable held-out checks. More UI features or an additional modeling dependency are not prerequisites for this milestone.

2026-11-11 execution checkpoint: actual Qwen runs completed all 24 original synthetic retrieval and answer cases without runtime failures and preserved model/request/evidence identities. One timetable-versus-passenger-count abstention mismatch is retained; all 46 generated batch claims remain pending human review. A separate two-source live brief survived save/reopen and isolated restore unchanged. These are diagnostic artifacts toward the workflow, not the missing reviewed real-source baseline. Continue the original gold review before changing prompts, ranking or cache identity; do not tune away this one synthetic failure and call the quality gate closed. See [the live diagnostic evidence](validation.md#full-synthetic-live-model-diagnostic--2026-11-11).

## What the reviews change

- Use the delivered evaluation infrastructure to complete human review and measure an unchanged baseline ahead of retrieval/model changes.
- Validate installation and persistence before recruiting an external pilot. Docker is one installation path; it does not establish native macOS or Linux support by itself.
- Make an evidence-backed comparison of a small, user-selected story group the first differentiated feature. Retain current inspectable keyword filters as a navigation aid.
- Treat sample sizes, uncertainty, independent human review and answer coverage as part of the evaluation contract.
- Develop provider adapters, MCP, feed monitoring and richer archiving only after the main workflow is measured.
- Keep BERTopic as an optional comparison backend: validate the delivered density baseline before changing methods or claiming emerging topics.

Existing work should be retained: transactional schema migrations through version 6, migration backups, article FTS5, embedding caching, portable merge restore, bounded browser capture and selected-import job state. The initial public baseline had 196 tests and a successful first Windows CI run. The latest local Windows/topic-discovery checkpoint has 509 passing tests and one opt-in live-server test skipped. Earlier schema-7 Docker evidence has 432 passes with none skipped; 159 targeted research/gold-authoring/diagnostic/export tests also passed in the existing Ubuntu/WSL2 Python 3.13 environment, with one opt-in browser test skipped. Those platform checks predate the latest optional topic-discovery change. The [hosted workflow](https://github.com/varunsidr/Artint/actions/runs/41449916277) verifies all three jobs for `dc6ef1e`, including the Docker test image, recreation persistence and recovery checks; later changes need their own hosted run. A fresh Windows installation recheck also passed on 2026-11-05. These checks do not establish retrieval or answer quality.

Current delivery checkpoints:

| Work | State | Remaining gate |
| --- | --- | --- |
| A: installation and portability | Local verification plus successful hosted Windows/Ubuntu/Docker jobs for `dc6ef1e`; fresh Windows install/recovery rechecked | Keep later commits green; native macOS, ARM64 and container GPU support remain unvalidated |
| B: extraction review tooling | Prospective freeze, phase/hash-bound reviews, eligibility and disagreement reports implemented | New eligible cohort, actual human labels/double review and research evaluation cases |
| Research evaluation foundation | Versioned gold-span corpus, 24-case original diagnostic fixture, isolated existing-pipeline runs, review packets and paired reports | Reviewed development/held-out data, independent support judgments and broader live-model measurements |
| Development gold authoring | Private 60-case machine proposal, consolidated AI-assisted corrections and offline case/batch review tools prepared | Human case/absence/family review, independent double review and a newly frozen approved development corpus; remaining sources are not a cleared held-out set |
| General analytics and research usability | General/specialist separation, contextual filters, article handoff, readable previews/citations and bounded cache optimizations implemented | New changes need Linux/Docker revalidation; no answer-quality claim |
| Experimental topic discovery | Bounded article-vector HDBSCAN, class TF-IDF terms, map/representatives, outliers, exact-copy accounting, normalized dated shares and separate digest-aware embedding cache; topic-enabled Docker runtime/UI/cache-recreation checks pass locally | Frozen real-corpus human coherence/usefulness review, method comparisons, multi-topic/event matching and matching hosted jobs remain pending |
| C: evaluated retrieval and saved research | Explicit saved results, immutable evidence, deletion/backup/restore, request fingerprints and selected-manifest observations delivered; hybrid retrieval pending | Reviewed baseline before ranking changes; complete inference/cache identity and evaluated retrieval remain follow-ups |

Explicit Save research now persists bounded snapshots with original evidence across restart and version-2 backup/restore; browser-session reuse is a separate convenience. Storage source/schema changed, and the prior frozen engine candidate remains preserved. Future measured baselines must freeze the current engine identity. Cache/batching changes preserve passage construction, ranking, model defaults and output budgets. A subsequent user-authorized context policy selects 8K/16K with checked non-truncating requests and retained run metadata; it is a new candidate configuration pending human quality comparison, with fixed-16K snapshots preserved. The reviewed evaluation sequence remains in force. See [unreleased changes](../CHANGELOG.md) and [milestones](../milestones.md) for implementation evidence.

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

Implementation checkpoint: the [research harness](research-evaluation.md) supplies the corpus contract, original 24-case diagnostic fixture, existing-pipeline runs, human atomic-review packets, paired reports and code/config/model snapshots. The private 60-case proposal and browser workbench have six revised approvals and 54 pending cases as of 2026-11-09; story grouping is unconfirmed and no completed approved corpus has been applied. It complements the extraction evaluator; completed human review/adjudication remains required. Proposals, partial review and diagnostic/three-case live smokes do not establish the targets below.

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

Delivery update: Milestone A delivered the Docker setup, diagnostics and Windows/Linux installation commands, with local verification as recorded above. Windows/Ubuntu/Docker jobs succeeded for `dc6ef1e`, including installation, restore and container recreation checks; later source changes and any additional macOS/GPU support require their own validation. The list retains the acceptance scope and remaining extensions.

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

Delivery update, 2026-11-05: explicit bounded snapshots, offline reopen/search, original quoted evidence/revision metadata, visible source-change states, deletion purging, Markdown/JSON export and version-2 backup/restore with version-1 compatibility are implemented. Available model tags/context/retrieval metadata are saved. Full prompt/weight-digest identity, run comparison and PDF briefs remain follow-ups; no measured RAG improvement or completed human gold gate is claimed.

Metadata update, 2026-11-09: new Ollama generations record message/schema and per-attempt request fingerprints, requested options, requested/reported model names and the runtime observed by the existing capability check. Nested metadata is detached from client state and preserved in JSON exports, saved research and backups. This adds no model call or ranking/prompt change; weight digests, server defaults and embedding-cache provenance remain unverified. Legacy results remain unchanged. See [request fingerprints](research-evaluation.md#request-fingerprints). The prior engine is preserved in a separate synthetic diagnostic snapshot; this is not the pending human-reviewed baseline.

Workspace follow-up, 2026-11-09: explicit new questions and passage searches also record bounded before/after selected-manifest observations, including available digests and quantization details. Changed/incomplete observations remain visible in the result and brief; JSON/saved research/backups retain full snapshots offline. Navigation, reuse and save/reopen make no new observations. Metadata failures preserve successful answers. These records expose manifest changes without certifying inference/cache weights or changing ranking, prompts or tag-keyed cache reuse. Complete model identity and evaluated cache isolation remain follow-ups. See [model inventory observations](research-evaluation.md#model-inventory-observations-in-research).

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

The topic-discovery request supersedes deferral of an initial optional corpus-navigation experiment. The shipped baseline uses scikit-learn HDBSCAN in the original normalized embedding space and class TF-IDF representations; it is not a BERTopic integration. Keep the BERTopic experiment below as a subsequent measured comparison. BERTopic's current 1.0 beta, Contextual Top2Vec, FASTopic/LX Topic and semantic-axis alternatives are assessed in [topic-discovery research](topic-discovery.md).

- **Optional BERTopic experiment, after the reviewed research baseline and dependable same-story workflow.** Freeze an authorized article corpus and compare discovered groups with the existing saved-label navigation and a simple embedding-clustering baseline. Inspect representative articles and outliers; evaluate human-rated coherence/usefulness, topic diversity, stability across seeds or corpus updates, runtime and peak system RAM/VRAM on the actual laptop. Existing retrieval vectors represent passages; define and version an article-level representation before reusing compatible embeddings. Keep jobs bounded, optional and cached. Corpus topics must not be presented as event matches or proof of answer relevance. Add 7/30/90-day trends only after checking topic alignment over time, publication-date coverage, duplicate reports and normalization by captured article volume; conclusions describe the saved corpus, not all news coverage. Integration and large-corpus scale claims require their own measured results.
- Read-only local MCP over stdio: search sources, retrieve revision-aware passages and read approved session evidence, with the same scope/size limits and source citations. Evaluate accidental disclosure, untrusted source instructions and cross-client behaviour before adding writes or network exposure.
- Additional provider adapters: a local OpenAI-compatible endpoint first if useful, then explicit opt-in remote endpoints with clear data routing and cost disclosure. Do not equate protocol compatibility with full structured-output, token-budget or embedding compatibility.
- WARC or single-file HTML preservation after the capture/evidence workflow is stable. This adds storage, active-content handling, asset fetching and viewing requirements; keep exported article PDFs described as reading copies.
- Broader type coverage, monitoring, scheduled feeds and richer annotation management according to pilot findings.
- Authentication, multi-user permissions and public hosting only under a separately approved product scope and threat model.

## Current implementation checkpoint

Milestone A packaging, installation, recovery and sandboxed runtime checks are verified locally and by successful hosted Windows/Ubuntu/Docker jobs for `dc6ef1e`. The fresh Windows recheck passed on 2026-11-05. Further source changes require matching CI; native macOS, ARM64 and container GPU support remain deferred.

Milestone B's extraction tooling and the research harness foundation are implemented. Quality gates remain open: complete a prospectively declared extraction cohort and human/double review, and author the reviewed development research cases before retrieval tuning. These review activities can proceed in parallel. The diagnostic extraction cohort has no completed human-reviewed eligible cases; the original research fixture is synthetic. Neither establishes the targets. Keep corpus collection/annotation and implementation changes separately reviewable; never invent human labels or publish a quality rate from synthetic fixtures.

Use small PRs with the problem, acceptance results, risks and migration effects. Record real evaluation results in the README only after the report exists; leave proposed targets visibly distinct. This plan does not schedule automatic commits, pushes, repository metadata changes or releases.
