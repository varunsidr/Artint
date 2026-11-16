# Research evaluation harness

Updated: 2026-10-31. This is developer tooling around the **current** Artint RAG pipeline, separate from the [extraction review workflow](extraction-evaluation.md). The harness calls application functions rather than implementing separate ranking or generation. It adds no dependencies or database migration. Current generation uses the [adaptive 8K/16K policy](../architecture.md); prior fixed-16K run snapshots remain preserved as separate configurations, and human-reviewed quality comparison is pending.

The first corpus contains **24 original synthetic questions across eight fictional story families**, with 16 answerable and eight unanswerable questions. It includes numeric/temporal distinctions, conflicting reports, multiple sources, alternative evidence, Unicode, source instructions and late evidence in a long document. These purposive fixtures check the evaluation machinery; they are not representative or held-out evidence of real-world model quality. No publisher content is included.

## Run an offline diagnostic

Run from the repository folder containing `app/` and `requirements.txt`, using the existing Python 3.13 environment. Each output directory/file must be new; existing runs or labels are never overwritten.

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py validate --corpus tests/fixtures/research/synthetic-v1.json
.\.venv\Scripts\python.exe scripts/evaluate_research.py freeze --corpus tests/fixtures/research/synthetic-v1.json --output output/evaluations/my-frozen-corpus
.\.venv\Scripts\python.exe scripts/evaluate_research.py run --corpus output/evaluations/my-frozen-corpus/corpus.json --output output/evaluations/my-retrieval --engine fixture --mode retrieval
.\.venv\Scripts\python.exe scripts/evaluate_research.py run --corpus output/evaluations/my-frozen-corpus/corpus.json --output output/evaluations/my-answers --engine fixture --mode answers
```

On Bash use `.venv/bin/python` instead of `.\.venv\Scripts\python.exe`. The fixture engine uses deterministic hashed word-count vectors and echoes a matching passage's first sentence or abstains. It reads no gold labels to produce its outputs. It is neither Qwen nor a second production retriever; reported fixture scores establish no semantic-retrieval or LLM-quality claim.

Open `report.md` for the summary and `report.json` for case results. Each run also contains its validated `corpus.json`, `config.json`, exact pipeline/harness source copies under `engine-snapshot/`, and an incrementally flushed `results.jsonl`. An interrupted run retains completed journal rows but has no certified final report; automatic resume is not implemented. Use a new output directory for a rerun.

All embedding reads/writes use disposable SQLite storage, with the configured application database restored after the run. No article/PDF/note is inserted, deleted or reprocessed. Even a configured `ARTICLE_LIBRARY_DB` is not used for evaluation. The harness fetches no source URLs. Artifacts contain source text and model output: keep real corpora, reviews and reports under ignored `output/`; only authorized original/licensed fixtures belong in Git.

## Run the actual local pipeline

Start Ollama and install the existing models first. This example selects three declared cases instead of implying a full-corpus run:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py run --corpus tests/fixtures/research/synthetic-v1.json --output output/evaluations/my-qwen-retrieval --engine ollama --mode retrieval --cache shared --case alder-1 --case larch-1 --case orbit-2
.\.venv\Scripts\python.exe scripts/evaluate_research.py run --corpus tests/fixtures/research/synthetic-v1.json --output output/evaluations/my-qwen-answers --engine ollama --mode answers --cache shared --case alder-1 --case orbit-2 --case sora-3
```

Omit the `--case` options to run all 24. Defaults are `qwen3:8b`, `qwen3-embedding:0.6b`, and `http://127.0.0.1:11434`. `--model`, `--embedding-model`, `--base-url` and `--timeout` configure a run explicitly; the CLI does not silently inherit `OLLAMA_BASE_URL`. Source passages are sent to the chosen endpoint only with `--engine ollama`. It does not pull models, start services or change model defaults.

The harness records installed model digests/details before and after execution, the Ollama runtime version when available, actual chat/embedding request settings, Python/dependency/platform identity and source fingerprints. Answer rows also retain the generation-policy version, estimated budget, actual context/token counts when reported, and context-attempt outcomes, including failed context attempts. Requests explicitly disable truncation/context shifting; generation checks the runtime floor before inference. Model inventory uses Ollama's [list-models API](https://docs.ollama.com/api/tags); runtime version uses the [documented version endpoint](https://github.com/ollama/ollama/blob/main/docs/api.md#version). A changed model identity makes the run invalid. Missing models or connection failures produce explicit failed case rows and a nonzero CLI exit code.

`--cache cold` creates a new embedding cache per case/repeat. It does **not** clear OS caches or unload an already resident model. `--cache shared` reuses one isolated cache across questions; report rows show actual hits, creations and embedding calls. `--repeats 2` repeats the selected cases; 1–5 repeats and at most 1,000 total case/repeat observations are allowed. Repetitions are not independent samples.

## Request fingerprints

New `OllamaClient` generation metadata includes `generation.request_identity` with version `ollama-chat-request-v1`, requested/reported model names, the runtime observed by the client's existing capability check, and SHA-256 fingerprints of the actual messages and response schema. Each `generation.attempts` entry records its own request fingerprint and requested generation options, so an 8K-to-16K retry has a distinct identity without changing the evidence. Network failures retain their attempted request metadata in the evaluation journal/report. The runtime capability check is cached per client; it is not a before/after runtime audit for every question.

Fingerprints hash UTF-8 JSON serialized with `ensure_ascii=False`, sorted object keys, compact separators and non-finite numbers rejected. The complete request hash covers the JSON payload, including messages, schema, requested model, context/output settings and existing stream/think/keep-alive/truncation controls. It is not a hash of HTTP transport bytes. Metadata retains hashes instead of another prompt/source-text copy, and adds no inventory calls or inference.

Article analyses and answers detach this metadata from mutable client state. Full-result JSON, explicit saved research and portable backup/restore preserve it. Older results and scripted/injected clients can lack it; no request identity is inferred for them. Plain passage searches do not generate a chat request and have no chat-request fingerprint.

This records requested configuration, not complete model identity or deterministic reproduction. `request_identity.model_digest` is explicitly null: the normal application does not verify weight digests, server-side defaults or which weight revision produced a reused embedding. The harness's separate before/after inventory checks still supply run-level model digests; they do not establish provenance of an older application cache. Matching request fingerprints establish neither identical output nor supported claims. Mutable-tag cache isolation and complete model identity remain follow-ups.

## Model inventory observations in Research

Each explicitly submitted new Research question or passage search records `model_observation` version `ollama-model-observation-v1`. The workspace reads the selected models from Ollama's [installed-model inventory](https://docs.ollama.com/api/tags) before and after successful execution. Answers observe the chat and embedding names; passage searches observe only the embedding name. No observation is added merely by opening Research, selecting sources, reusing a result, saving, exporting or reopening it. Article summaries and direct CLI/library calls do not acquire this workspace-level observation automatically.

Each snapshot retains its UTC observation time, selected names, installed/unknown status, valid 64-character manifest digests and available bounded format/family/parameter-size/quantization details. Other installed models and arbitrary server detail fields are excluded. Each GET uses the existing metadata reader's 3-second connection/read timeouts, 1 MiB response limit, 512-model bound and disabled redirects. Duplicate selected names are ambiguous and unavailable; aliases are not guessed. Metadata errors are recorded without failing an otherwise successful research result. The result's total elapsed time includes these two reads; retrieval timing remains separate.

- `stable`: every selected manifest has a valid digest at both observations and those digests match.
- `changed`: an observed selected digest differs or a selected model's known installed status changes. A known change remains visible even if another selected digest is unavailable.
- `unavailable`: a complete stable comparison cannot be established, including missing/malformed digests, metadata failures and partial observations.

Changed inventories produce a visible run warning; incomplete observations produce a short notice. These conditions also travel with the Markdown brief, while full snapshots/details remain in JSON, saved research and portable backups. Saved results retain the original observation offline. A fresh result takes new observations without rewriting the previous result. A failed new inference does not attach its observations to the previous completed answer.

These are server-reported installed-manifest observations, not authenticated proof of which weights were resident during inference. A change and reversal between observations can go undetected. `generation.request_identity.model_digest` remains null; stable inventory does not certify server defaults, embedding-cache provenance, deterministic output or claim support. **Generate a fresh result does not invalidate the tag-keyed embedding cache.** Cache isolation remains a separately evaluated change after the reviewed baseline. The CLI evaluation harness retains its existing independent run-level identity checks.

## Optional native Windows cache-profile comparison

Use a new output directory for every profile. The [Windows GPU launcher](installation.md#optional-native-windows-nvidia-inference) defaults to `f16`; explicitly use `-KvCacheType q8_0` to test quantization after stopping your existing server. Retain `profile.json` and inspect the actual runner cache/offload lines alongside the run, since the standard Ollama API does not expose server KV-cache settings. The profile applies to embeddings too; compare retrieved passage IDs and retrieval metrics rather than assuming identical inputs to answer generation.

For a small original synthetic diagnostic, run the same declared cases twice on each profile:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py run --corpus tests/fixtures/research/synthetic-v1.json --output output/evaluations/9b-q8-experiment --engine ollama --mode answers --model qwen3.5:9b --cache shared --repeats 2 --timeout 180 --case alder-1 --case alder-3 --case harbor-2 --case orbit-2 --case sora-3 --case larch-1
.\.venv\Scripts\python.exe scripts/evaluate_research.py prepare-review --run output/evaluations/9b-q8-experiment --output output/evaluations/9b-q8-review
```

Repeat with distinct outputs on `qwen3:8b`/`f16` and `qwen3.5:9b`/`f16` to separate model and cache effects. Keep runtime, corpus, case IDs, repeats, cache mode, hardware load and context policy consistent. Shared-cache repeats do not guarantee a particular model stays resident: record actual load/evaluation timings if measuring warm generation. These six synthetic cases and pending labels are diagnostics only; no human support score or default-model promotion follows automatically. Restore the normal `f16` launcher profile after testing unless deliberately adopting the experimental profile.

## Corpus and gold evidence contract

Export the versioned JSON Schema for authoring:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py schema --output output/evaluations/research-corpus.schema.json
```

The synthetic fixture is a complete authoring example. Each source has an ID, story family, title, provenance URL, capture timestamp, source type, exact saved text and SHA-256 of its UTF-8 bytes. Each case records question, story family, split, source scope, answerability, tags, required facts, label provenance and explicit eligibility/exclusion reason.

Gold evidence uses **zero-based, half-open Unicode character offsets** into the original frozen text, its hash and an exact quote. It is independent of `article_id:P1` chunk IDs. Evidence units have stable per-case IDs. `acceptable_sets` lists alternative sufficient sets: every unit in one set is needed; recovering any complete alternative suffices. Unanswerable cases have no sufficient evidence sets or required facts.

Use `kind=development` / `split=development` for development data and separate `heldout` files for held-out data. Synthetic labels remain synthetic. Proposed labels use `label.kind=unreviewed`; real human gold labels require a declared reviewer and timezone-aware timestamp. The harness validates declarations but cannot authenticate a person's identity or prove the annotations are correct.

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py check-splits --development output/evaluations/development.json --heldout output/evaluations/heldout.json
```

This rejects shared story families and exact text copies. Humans must group related/syndicated/near-duplicate reports consistently; the checker does not discover all such relationships. Corpus JSON is capped at 16 MiB, source text at 8 MiB total, with at most 256 sources, 1,000 cases and 100 source IDs per case. Source URLs are provenance only and are never fetched.

The next data task is approximately **60 reviewed development questions including at least 20 unanswerable**, followed by a separately frozen held-out set targeting 200 questions including 100 unanswerable. These are review-workload targets, not completed datasets or guarantees of statistical precision. Preserve the current baseline before tuning retrieval.

## Prepare real development proposals and review gold labels

`prepare-development` reads an existing library using SQLite `mode=ro` and `query_only`; it does not run application migrations or change articles, PDFs, notes or cached analyses. It uses an explicit selection file and an already running local Ollama model to draft two proposed answerable questions and one proposed unanswerable question per group. Models must already be installed; the CLI does not start a service or download weights. Missing models/services stop before creating a new output directory.

Selection JSON has this shape; replace the sample IDs with saved IDs from a Library metadata export:

```json
{
  "schema_version": 1,
  "name": "My development proposals",
  "protocol": "Describe source selection, intended coverage, exclusions and review requirements before drafting.",
  "groups": [
    {"id": "story-one", "story_group": "event-family-one", "source_ids": ["SAVED_ID_ONE"], "distractor_ids": ["SAVED_ID_TWO"]},
    {"id": "story-two", "story_group": "event-family-two", "source_ids": ["SAVED_ID_TWO"], "distractor_ids": ["SAVED_ID_ONE"]}
  ]
}
```

Use 20 groups for 60 proposals. Each group has 1–4 target sources and up to four distinct distractors from the selected target pool. Related/syndicated reports need a common proposed story family, even when used in different groups. The source-family map is a proposal until a person checks it.

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py prepare-development --database data/articles.db --selection output/evaluations/selection.json --output output/evaluations/my-development-draft
.\.venv\Scripts\python.exe scripts/evaluate_research.py prepare-gold-review --corpus output/evaluations/my-development-draft/corpus.json --output output/evaluations/my-gold-review
```

Open `output/evaluations/my-gold-review/review.html` in a browser. It is a self-contained local page, works without a server or model, follows the browser's light/dark preference, and fetches no assets or publisher pages. It shows the full scoped saved sources with proposed spans highlighted. You can accept, revise or exclude a case; edit its question/facts/evidence; select source text to add exact evidence spans; review source families; and download partial decisions as JSON. Use **Load saved review** to resume: unsaved browser-memory changes do not survive a reload. Unicode offsets count code points, including text containing emoji, rather than JavaScript UTF-16 units.

The draft directory preserves the selection, source snapshot, source audit, sampled anchors, per-group proposal journal, model identity, and unassigned-source metadata. Source types remain `other` until separately reviewed; capture findings are not an extraction-completeness score. Unselected sources are **not** automatically safe held-out data. The model sees bounded sampled anchors; a fact absent there may exist elsewhere in the full scoped text. Source-anchored quotes can still support an incorrectly worded question or proposed fact. Treat every label, particularly unanswerability, as unreviewed. Failed groups stay visible; fewer than 60 successful proposals are not reported as 60.

The 2026-10-30 private development batch contains 60 machine-proposed cases (40 proposed answerable, 20 proposed unanswerable), 23 saved sources from 17 publishers and 19 proposed story families. The remaining 89 articles are unassigned. Draft-negative questions that referred to known distractor facts were revised as further machine proposals with the originals retained; this is not human adjudication or proof of absence. All 60 remain unreviewed. Real bodies and decisions stay in ignored `output/` and are not distributed with this guide.

After a person has checked every case, required fact, source scope and family map, download their review JSON and apply it into a **new** directory:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py apply-gold-review --corpus output/evaluations/my-development-draft/corpus.json --review output/evaluations/my-gold-review/gold-review.export.json --output output/evaluations/my-reviewed-development
```

The browser downloads to its configured download location; move the file to the example path or pass its actual path. The CLI refuses pending decisions, absent human identity/time, stale hashes, silent case edits, altered source scopes or invalid source spans. Edits require the explicit `revise` decision. Exclusions require reasons and remain in the corpus. Human-approved labels are applied only to a new corpus; the source proposal is preserved. A corrected count below 60/20 is reported honestly, not forced to match the target. Counts and gold approval still establish no model-quality score.

For independent gold review, create a second pending review page for another person. Use `--second-review PATH` when applying decisions. The second file may leave cases pending, but completed decisions require a different declared reviewer and checked source-family grouping. Disagreements block application until human adjudication; the CLI does not resolve them. Names/timestamps remain declarations rather than authentication. Check held-out independence separately, freeze the approved development corpus, and then run the unchanged RAG baseline before tuning retrieval.

## Review suggestions as one batch

Use `prepare-batch-review` when you have AI-assisted corrections for several proposed cases and want one consolidated page:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py prepare-batch-review --corpus output/development/corpus.json --suggestions output/development/batch-suggestions.json --output output/development/batch-review
```

Start with **`start-review.html`**. Enter your name, read the question and expected answer beside the quoted evidence, and choose **Looks correct**, **Needs changes** or **Not sure**. Five questions appear at a time; complete as few or as many as you want. Full saved articles open inline, with the proposed evidence highlighted. Needs changes and Not sure retain pending labels and optional notes; only Looks correct records an approval. Flagged/missing-answer cases require an explicit full-source check. Browser storage saves progress when available; **Save progress** downloads the existing review format and **Resume from file** reloads it. Storage failure is visible and file saving remains available. No source is fetched and no model runs. Source-family grouping remains unfinished until separately reviewed; the simple screen cannot certify it.

Development cases may deliberately include unrelated distractor articles. The quick screen separates proposed other-story copies under **Other stories in this test**; this tests retrieval and implies no connection between SAP, SpaceX or other subjects. Proposed family labels are not proof of relevance. The frozen scope remains unchanged, and missing-answer checks still require inspecting every selected copy. See the [recorded user feedback and product workflow](research-workflow.md).

For bulk actions or technical editing, open `batch-review.html` from the same directory. It groups all cases by proposed story family, shows expected facts and issue notes together, and provides original/proposed question, fact and exact-evidence comparisons. Full saved copies are included once and linked from each case. Filter by issue priority, proposed revision, source check or pending decision; select visible cases or a family after checking them. Enter your reviewer name and record the selected cases together. Nothing is selected or approved on initial load. The detailed screen reads the simple screen's downloaded progress through **Load saved review**; it does not share its automatic browser save.

The suggestions file contains `schema_version=1`, `authoring_kind=ai_assisted`, a canonical `proposal_sha256`, and one `judgments` row per original case. Each row retains `case_id`, canonical `case_sha256`, a complete proposed `case`, `suggested_action` (`keep`, `revise`, `check`), `priority` (`normal`, `high`) and explanatory `notes`. Hashes, exact source spans, case scope/split/labels and eligibility are validated before creating output. `keep` cannot change a case; `revise` must change it. Proposed absence labels must retain `check`; AI suggestions cannot silently exclude cases or declare human labels. See the original fictional examples in [the batch tests](../tests/test_research_batch_review.py).

Recording suggestions chooses `accept` for unchanged cases and `revise` for changed cases. Flagged/missing-information cases also require explicit confirmation that the selected full scopes and capture suitability were checked. Exclusions need a reason; cases can be left pending together. Source-family attestation remains separate and is never checked automatically. Edit proposals without approving them, download partial review JSON, and reload it to preserve pending edits and decisions. The detailed page has no autosave; neither screen uses a remote service.

The download uses the same gold-review contract as the single-case page; pass it to `apply-gold-review` with the original proposal after all cases/grouping are checked. The original corpus and source files remain unchanged, and output goes to a new destination. Bulk UI actions do not establish that labels are correct, reviewers independent or extraction complete. All human decisions still need actual user judgment. The private 60-case batch has 37 proposed revisions, 22 source-check flags (including 20 proposed unanswerable cases) and one proposed keep. It originally started with zero decisions. On 2026-11-09 the user's private downloaded progress records six revised approvals and 54 pending cases, with family grouping unconfirmed. The partial review has not been applied to a new approved corpus; it remains private and does not establish model quality.

## Measures and limits

| Measure | Definition |
| --- | --- |
| Recall@5/@10 | Best fraction of gold evidence units recovered in an acceptable sufficient set. A unit is covered only when every non-whitespace source character is present across retrieved spans. |
| Sufficient evidence@k | Whether at least one entire acceptable evidence set is recovered; partial multi-source evidence is not a complete answer. |
| MRR@10 | Reciprocal rank of the first passage overlapping non-whitespace gold evidence. A relevant first hit alone does not establish sufficient evidence. |
| Correct abstention | Fraction of unanswerable cases returning `supported=false` and no claims, conditional on the supplied gold labels. Pipeline failures do not count as correct refusals. |
| Answerable response rate | Whether claims were returned for an answerable question. This is **not** useful/correct answer coverage. |
| Claim/citation support | Human judgments on atomic factual units and their cited frozen passages; never inferred from valid citation IDs or an LLM grading itself. |
| Useful answer coverage | Separate human case judgment against required facts, complete atomic review and cited support. |
| Timing | Pipeline, retrieval, generation and embedding timing recorded separately. Memory/GPU utilization is not measured. |

Retrieval-only runs call the current semantic search with a top-10 result limit. Answer runs call `answer_question` unchanged, including its six-passage context; @10 metrics are **not measured** in answer mode. Passage alignment maps whitespace-normalized chunks back to original offsets and fails if non-whitespace content cannot be matched exactly. Saved run inspection/comparison checks frozen spans directly, so it does not depend on a later chunker's output.

Reports include per-case observations, source/tag/label strata, explicit exclusions and failures. Failed eligible runs keep zero credit in applicable retrieval/response denominators. Successful-only latency summaries disclose their observation count. For macro diagnostics, repetitions are averaged within case, then cases within story; stories receive equal weight. Confidence intervals resample entire story families with a fixed seed. Human atomic-support rates retain their actual unit denominators with story-clustered ratio intervals.

Intervals are descriptive conditional on these stories. Few clusters, homogeneous outcomes, review selection and correlated/syndicated data limit inference; a degenerate bootstrap interval is not certainty. Every report leaves the **quality gate not established**. This first harness does not certify the proposed 95% claim-support or 90% abstention targets.

## Human answer review

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py prepare-review --run output/evaluations/my-qwen-answers --output output/evaluations/my-qwen-answers/review-a.json
.\.venv\Scripts\python.exe scripts/evaluate_research.py review-summary --run output/evaluations/my-qwen-answers --review output/evaluations/my-qwen-answers/review-a.json --output output/evaluations/my-qwen-answers/review-a-summary.json
```

Preparation writes a pending JSON checklist plus `review-a.packet.json`, with model names omitted from the packet. It creates **zero human labels**. This is practical blinding; reviewers can still inspect the run directory. JSON avoids spreadsheet-formula interpretation of source/model-controlled text.

The reviewer sets `review_kind=human`, their name and an ISO timestamp with timezone, then:

1. Read the question, required facts, gold provenance and frozen cited passages. Missing or questionable gold should be corrected in a new corpus version, not silently edited inside an old run.
2. Split each compound generated claim into atomic units, retaining its parent claim index/hash and consecutive unit IDs. Keep every factual assertion. Unit text can be a concise decomposition; completeness needs human judgment.
3. Grade support as `supported`, `partial`, `unsupported`, `contradicted`, `unverifiable` or `non_factual`. Judge what the cited saved passages support, not independent world truth. Grade citation support separately as `supported`, `partial`, `unsupported` or `missing`; non-factual units use `not_applicable`.
4. Record the required fact IDs covered and the case decision. Answerable decisions are `complete`, `partial`, `incorrect` or `uncertain`. Unanswerable decisions are `correct_abstention`, `incorrect_answer` or `uncertain`. Failures retain `pipeline_error`.
5. Set `atomic_complete=true` only after checking that no assertions were omitted and all units are judged. A complete answer must return claims, cover all required facts and have no reviewed unsupported factual units. Leave unfinished work pending.

The summary reports reviewed/pending units, completed/pending cases and actual denominators. Full atomic support requires both support and citation verdicts to be `supported`. The tool cannot verify that a reviewer split claims honestly or that case annotations are correct. A model-provided or missing human provenance declaration is rejected.

For independent double review, create a second pending packet, have another person review at least 20% of cases, and pass `--second-review PATH` to `review-summary`. Both files retain all cases, with unreviewed ones pending. Distinct declared reviewer names are required. Differences in decisions, fact coverage, atomic decomposition or judgments are reported for adjudication; the tool never resolves them automatically. Review files are capped at 64 MiB.

Corpus, run/config/source snapshots, claims and review fingerprints must agree. Reprocessing evidence or changing a run makes prior review labels stale. Fingerprints use canonical JSON and source bytes; they are integrity bindings, not cryptographic authentication of reviewers or an adversarially tamper-proof audit log.

## Compare a candidate with baseline

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py compare --baseline output/evaluations/my-retrieval --candidate output/evaluations/my-candidate-retrieval --output output/evaluations/my-comparison
```

Both runs must use the same frozen corpus, selected cases, mode, repeats, cache regime and retrieval budget. The comparison recomputes retrieval measurements from validated frozen evidence and reports paired deltas, failures, configuration/model identities and story-clustered intervals. Latency deltas use successful pairs only. This initial comparison covers retrieval/latency diagnostics; human claim-support comparison requires separate review of each run.

Do not tune on held-out failures or promote a change on synthetic scores alone. Persistent passages/indexing, hybrid lexical-semantic ranking and rerankers remain subsequent work after the reviewed baseline exists. Explicit saved research and portable evidence are already delivered; their presence does not establish answer quality.

## Verification

Offline tests exercise metric denominators, alternative/cross-chunk evidence, Unicode alignment, exclusions, failure accounting, shared-cache reuse, source/storage isolation, schema/JSON validation, stale/invalid labels, independent reviewer declarations, snapshot integrity, interrupted journals and paired compatibility. CI uses the fixture engine without Ollama, publisher access, secrets or a GPU. Evaluation tools/fixtures are included in the Docker **test** target, not the application runtime image.

Historical three-case Qwen smokes are now supplemented by the [2026-11-11 full synthetic live diagnostic](validation.md#full-synthetic-live-model-diagnostic--2026-11-11): 24 retrieval and 24 answer cases, zero runtime failures, stable inventories and 8K answer contexts. One declared-unanswerable question produced timetable claims instead of abstaining about missing actual passenger counts. The 24-case claim review starts fully pending, with 46 generated claims seeded as review units. A separate two-source live result survived storage reopen and isolated backup/restore unchanged. These checks establish execution/evidence persistence, not real-world recall, support or abstention targets. The private real-source gold review remains separate and unfinished.

To reproduce the diagnostic in new directories with the default models already installed and Ollama running:

```powershell
.\.venv\Scripts\python.exe scripts/evaluate_research.py freeze --corpus tests/fixtures/research/synthetic-v1.json --output output/evaluations/my-live/corpus
.\.venv\Scripts\python.exe scripts/evaluate_research.py run --corpus output/evaluations/my-live/corpus/corpus.json --output output/evaluations/my-live/retrieval --engine ollama --mode retrieval --cache shared --timeout 180
.\.venv\Scripts\python.exe scripts/evaluate_research.py run --corpus output/evaluations/my-live/corpus/corpus.json --output output/evaluations/my-live/answers --engine ollama --mode answers --cache shared --timeout 180
.\.venv\Scripts\python.exe scripts/evaluate_research.py prepare-review --run output/evaluations/my-live/answers --output output/evaluations/my-live/answer-review.json
```

Every review decision remains pending until a person supplies the required judgments. Check [milestones](../milestones.md) and [validation](validation.md) for platform evidence and limitations.
