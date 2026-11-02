# Validation record

Updated: 2026-11-02. These results distinguish runtime/harness checks from extraction completeness and human-reviewed AI quality. Milestone A's historical baseline source commit is `9067fad`; the research harness starts from `4ef742b`. The current harness changes have not been pushed or released by this implementation.

## Expanded coverage analytics checkpoint — 2026-11-02

- Windows/Python 3.13 full suite with `RUN_BROWSER_TESTS=1`: **404 passed, 1 opt-in live-server installation test skipped**. Analytics regression cases verify complete filtered scope across pages, duplicate/stale labels, bounded publisher columns with full topic reach, exact adjacent 30-day boundaries, future/undated records, calendar advancement, capture flags versus missing/stale/malformed checks and cell-filter/CSV membership.
- Existing native Ubuntu/WSL2 Python 3.13 environment: **18 targeted analytics tests passed**. Docker, hosted CI and a new full Linux UI/install pass were not run. No dependency or schema migration was needed.
- Separate Chrome checks used an isolated original 36-article synthetic demo with 12 synthetic capture-check records (four flagged). Four indicators, per-publisher details, the saved-label comparison and readiness panel rendered correctly. Keyboard cell selection applied both topic/publisher; the CSV matched that count. Missing-label/empty states, specialist switching, tooltip/Escape, both themes and 390px contained table scrolling passed without page errors/overflow. New text measured at least 12px. Private artifacts: `output/analytics-fields-20261102/`; its identified temporary app process was stopped.
- These are local saved-source aggregates and regression checks, not market-wide trend measurement, political-bias/factuality ratings or evaluated claim comparison. No actual model inference ran. Every real-library table/all 112 PDFs and the frozen core research source hashes remain unchanged. All 60 real human decisions remain pending. Documentation/whitespace checks pass.

## Publisher promotion cleanup checkpoint ? 2026-11-02

- Windows/Python 3.13 full suite with `RUN_BROWSER_TESTS=1`: **398 passed, 1 opt-in live-server installation test skipped**. Existing browser-rendering and offline batch-review fixtures ran; no live publisher request or model inference was needed. New coverage verifies the reported template before/within/after article text, paragraph/div/split wrappers, following headlines, quoted/mixed reporting, malformed links, clean PDF/RAG passages, minimum body length and missing-content warnings.
- Existing native Ubuntu/WSL2 Python 3.13 environment: **69 targeted capture/cleanup/extraction-evaluation tests passed, 1 opt-in real-browser test skipped**. Docker/hosted CI and a fresh Linux installation were not run. No dependency or schema migration was needed.
- New capture cleanup is explicitly versioned and counted in diagnostics. New extraction phase/review fingerprints include its source hash; incompatible same-phase resumes and frozen-helper replays are rejected. Historical phase/review files are preserved. This does not establish general boilerplate precision or the 90% reviewed extraction target.
- A read-only library query found one saved article containing the reported template. Existing saved text/PDFs were retained; URL reuse does not reprocess them. All real-library table/all 112 PDF hashes and frozen core research source hashes remain unchanged. Documentation/whitespace checks pass. All 60 real human review decisions remain pending; this capture fix does not silently revise those source snapshots.

## Research result recovery checkpoint ? 2026-11-02

- Windows/Python 3.13 full suite with `RUN_BROWSER_TESTS=1`: **377 passed, 1 opt-in live-server installation test skipped**. Added regression coverage for failed-request retention, offline/empty-filter access, explicit clearing, source revisions/fingerprints, passage-search model metadata, international links and near-full/near-zero mixed-memory rounding.
- Existing native Ubuntu/WSL2 Python 3.13 environment: **159 targeted intelligence/research/development/batch/diagnostic/export tests passed, 1 opt-in batch-browser test skipped**. This is not a new full Linux UI/browser or GPU pass. Docker and hosted CI were not run; no dependency or schema change was needed.
- The isolated original 36-article demo and loopback synthetic metadata/answer server exercised a successful answer followed by a failing request, offline inventory refresh and filters with no matches. The original question, completion time, source fingerprints, claims and retrieved passages stayed identical in each download. Explicit clearing removed exports while retaining all 36 demo articles. Metadata checks/downloads made no additional model POST. Light/dark screens and 390px layout passed without page errors/overflow. Fake near-full mixed residency rendered `>99.9%` alongside `CPU + GPU`. This tests workflow behavior, not actual inference, speed or model quality.
- Private artifacts: `output/research-recovery-20261102/`; both identified fixture processes were stopped. No actual Ollama service was started, model downloaded or hardware setting changed. Every real-library table/all 112 reading PDFs and frozen core inference/storage source hashes remain unchanged. The 60-case human review remains entirely pending. Documentation/whitespace checks pass. Session retention and portable exports do not implement durable research history or close Milestone B.

## Research diagnostics and export checkpoint — 2026-11-02

- Final Windows/Python 3.13 full suite with browser extraction enabled: **367 passed, 1 opt-in live-server installation test skipped**. New checks cover valid/malformed/missing GPU metadata, installed versus unloaded models, old/unknown runtimes, bounded/no-redirect metadata reads, explicit CLI behavior, stale UI snapshots, safe theme-aware HTML, citation-preserving exports, literal markup, unsafe links and offline workflows.
- Existing native Ubuntu/WSL2 Python 3.13 environment: **153 targeted intelligence/research/development/batch/diagnostic/export tests passed, 1 opt-in batch-browser test skipped**. This does not establish a new full Linux application/UI pass or native Linux GPU support. Docker and hosted CI were not run; runtime/test copies already include the new app modules/tests, without new dependencies or database migrations.
- A separate Windows browser session used the original 36-article fictional demo, its own SQLite/PDF overrides and a loopback synthetic Ollama metadata/answer fixture. Light/dark snapshots and 390px layout passed without page errors/overflow. A semantic HTML status table was used to match the app's dark theme; model names are escaped and narrow tables scroll inside the panel. This is simulated residency/answer metadata, not an actual GPU-performance or model-quality check.
- Instrumentation confirmed that explicit compute checks made only GET metadata requests and that Markdown/JSON downloads caused no additional model POST or research rerun. The downloaded brief retained citation links, original URLs and quoted saved evidence; the versioned JSON retained all retrieved evidence/context metadata. Unloaded-state reporting was also exercised. Private artifacts are under `output/workspace-usability-20261102/` and both temporary fixture processes were stopped afterward.
- The actual native Ollama endpoint was offline during the explicit CLI check; it returned a structured unavailable result without starting a service or changing hardware settings. A live loopback metadata fixture also passed the CLI with installed-but-unloaded models, without inference. Default installation checks still contact no model service. API references and compatibility limits are in [diagnostic usage](installation.md#model-readiness-and-residency-checks).
- Frozen production inference/storage hashes still match the earlier candidate, the 60-case review packet is entirely pending, and every real-library table/all 112 reading PDFs remain hash-identical. Documentation and whitespace checks pass. This improves usability/diagnosis/export, not reviewed retrieval or answer quality, durable research history or the Milestone B gold gate.

## Consolidated batch-review checkpoint — 2026-11-02

- Final Windows/Python 3.13 full suite with real browser extraction enabled: **323 passed, 1 opt-in live-server installation test skipped**. Fifteen new batch tests cover stale/duplicate hashes, altered scopes/labels, invalid spans, hidden exclusions, absent-label flags, output preservation and a real browser export/resume workflow on original fictional data. One concurrent Windows/WSL run hit the existing three-second Analytics AppTest timeout; a serial full rerun passed without production changes or timeout increases.
- Existing native Ubuntu/WSL2 Python 3.13 environment: **114 targeted intelligence/research/development/batch tests passed, 1 opt-in batch-browser test skipped**. This is not a fresh install or full Linux application/browser validation. Docker and hosted CI were not run; the existing allowlist/test-target copies include the new Python module and original tests, with private outputs excluded.
- Prepared a hash-bound AI-suggestions packet covering all 60 real-source development cases: 37 suggested revisions, 22 source-check flags and one proposed keep, grouped into 19 proposed story families. All 20 proposed absence cases remain flagged. The two other source flags concern extraction/image-caption suitability. Structural spans/scopes/hashes validate; semantic correctness and absence remain for human judgment. No original corpus, source text or human label was overwritten.
- Actual offline page checks covered all 60 rows/23 full source copies, revision/source-check filtering, light/dark, 390px layout, zero remote requests/page errors and zero initial selections/decisions. Interactive bulk selection, reviewer-name checks, flagged-scope confirmation, exclusions, partial/complete JSON export, resume, pending edits, invalid-scope imports, family attestation and literal unsafe markup were tested only on original fictional fixtures. The real 60-case packet has **zero human decisions**.
- A completed fictional browser export validated and applied through the existing gold-review contract to a new fictional fixture corpus; missing family attestation was rejected. This interoperability test creates no real human gold. Private artifacts are under `output/development-eval-20261102/batch-review-ready/`; exported progress can be resumed in that same page.
- Production RAG/storage source hashes still match the earlier engine candidate, and every real-library table and all 112 reading PDFs remain hash-identical. New review-tool code will be fingerprinted separately in later runs; the old candidate is preserved. No model inference, model/context/cache change, schema migration or dependency addition was required. Human review and the measured baseline remain pending.

## Baseline engine candidate — 2026-11-02

- Rechecked the saved 60-case/23-source proposal and partial-review contract: zero human decisions and all labels still unreviewed. No downloaded review export was found in the targeted review locations. A human-reviewed gold corpus and measured baseline remain pending.
- Copied the pipeline/evaluation source, GPU launcher and dependency/lock files into a new private engine candidate, verified all 18 file hashes, and recorded expected model/cache/context settings. This is code/config preservation, not a gold-corpus freeze or model-quality run. Candidate engine fingerprint: `abb2508edbb8d93532a8e84835adb716178dbbceb5496c53f3ea22b4f5b09249`.
- The local Ollama service was unavailable for read-only model/runtime identity observation. No service startup, model inference, publisher fetch or application/database change was performed. Actual model identity, cache type and placement must be checked when executing the eventual baseline. The real-library/PDF preservation and documentation checks passed; the prior regression results below were not rerun for this artifact-only step.

## Gold-review readiness checkpoint — 2026-10-31

- Revalidated the existing real-source development proposal: 60 cases, 23 source copies, exact source hashes/gold spans and a valid partial-review contract. All 60 decisions remain pending with zero human approvals; no approved corpus or quality baseline was created.
- Prepared a private first-three-case review guide and offline session under `output/development-eval-20261031/review-session-01/`. Machine notes identify ambiguous cooling-temperature wording, potentially over-required evidence, attribution and the need to check full source scope before accepting absence labels. The Q1 suggested JSON is separate; original corpus/case scope/text and proposal files are preserved, with the same proposal SHA-256 `415de8a7d994be6c9a0e46e483dd644fbe5fb31177a5a577cd53fd8a8c336762`.
- Headless Chrome verified the actual session in light/dark and at 390px: notes visible, all three scoped source copies present, no overflow, zero remote requests/page errors and zero decisions recorded. The library/PDF guard remained unchanged. Only private review artifacts and documentation were added for this checkpoint; no application change or repeated full regression run was needed. Human judgments and source-family review remain pending.

## Opt-in KV-cache experiment — 2026-10-31

- Added `-KvCacheType f16|q8_0` to the native Windows GPU launcher; `f16` remains the default and the app model default remains `qwen3:8b`. Requested settings are captured in a local UTF-8 JSON manifest. Actual runner logs confirmed Flash Attention and the selected K/V types. Parent/persistent environment settings are unchanged; invalid cache values and occupied ports were rejected without stopping a server.
- Compared three native RTX 5050 profiles on the same six original synthetic cases (`alder-1`, `alder-3`, `harbor-2`, `orbit-2`, `sora-3`, `larch-1`), two shared-cache repeats each: **36 successful case observations, zero runtime failures**, all at 8K. These cases cover numeric/multi-source distinctions, conflicting reports, absent facts, Unicode/source instructions and late evidence in a long document. Corpus/model/runtime/config identities and pending human-review packets are preserved per run. The private instrumented diagnostic and results are under ignored `output/kv-cache-20261031/`; no publisher text or real-library writes were involved.

| Model / server KV cache | Reported GPU memory residency | Median generation time, second repeat |
| --- | --- | --- |
| Qwen3 8B / f16 | 100% | 2.05s |
| Qwen3.5 9B / f16 | 85.4% | 4.64s |
| Qwen3.5 9B / q8_0 | 87.4% | 3.73s |

- These are six-case sequential diagnostic timings, not a controlled general-speed benchmark or quality ranking. Output lengths differ; model-specific defaults, OS/model caches, thermals and desktop GPU load were not normalized. Second repeats reused stored embeddings; per-request load/evaluation timing and placement were recorded separately. Decode-rate medians were about 49.85, 25.15 and 31.08 tokens/s respectively.
- For the installed 9B model at 8K, the logged attention KV allocation decreased from **256 MiB f16 to 136 MiB q8_0**. Its weights/runtime still did not fit entirely on the GPU. No 4K application fallback, model replacement or persistent quantization was applied.
- Both f16 profiles retrieved the same passage IDs/order on all 12 observations. Quantizing the server also quantized embedding inference: only 6/12 retrieved ID sets and 2/12 orders matched the f16 runs. Synthetic gold-span recall/sufficiency at 5/6 had zero measured paired delta on this tiny subset; that does not establish unchanged retrieval quality elsewhere.
- Both 9B profiles emitted `supported=true` for `sora-3` in each repeat, phrasing the response as missing audited expenditure, whereas the fixture expects explicit abstention. The 8B profile returned `supported=false` on both missing-information cases in both repeats. This is a measured synthetic output-contract difference, not a human claim-faithfulness score; all human review packets remain pending and the quality gate remains unestablished.
- The Ollama tray helper had to be temporarily closed because it restarted its server during profile changes. The experiment server was stopped, the normal default `f16` launcher restored, and an actual 8K Qwen3 8B request again returned valid JSON with **100% GPU / 37 of 37 layers offloaded**. No startup or persistent environment setting was changed. The existing full-suite checkpoint below remains 308 Windows passes/1 skipped and 100 targeted Linux passes; this launcher-only checkpoint did not rerun the Python suite, Linux/Docker or hosted CI. Library/PDF hash and documentation checks passed.

## Adaptive context checkpoint — 2026-10-31

- Final Windows/Python 3.13 full suite with browser extraction enabled: **308 passed, 1 opt-in live-server installation test skipped**. Existing native Ubuntu/WSL2 Python 3.13 environment: **100 targeted intelligence/research/development tests passed**, using a separate Linux bytecode cache. This is not a fresh Linux install or a new full Linux/Docker validation; hosted CI and Docker were not run.
- Native Windows Ollama 0.40.11 rejected a declared 2,065-token synthetic request at a 256-token context with HTTP 400 when `truncate=false` and `shift=false`. This checked runtime is the generation compatibility floor; unknown/older runtime versions are rejected before new chat generation.
- Five live application probes passed: initial 8K selection, initial 16K selection, complete 8K-to-16K retry after input overflow, retry after actual input counts showed insufficient reserved output space, and rejection above 16K. The budget uses an explicit UTF-8 estimate, not an exact tokenizer; the server controls and actual returned counts provide the fit checks. Original synthetic text only; artifacts are ignored under `output/context-adaptive-20261031/`.
- Three declared original synthetic research cases (`alder-1`, `orbit-2`, `sora-3`) completed through the actual Qwen retrieval/answer pipeline with no failed runs. Their evaluator rows record 8K context, actual input token counts, reserves and non-truncation request flags. Human claim-support labels remain pending; these are operational smokes, not quality percentages. Prior fixed-16K snapshots remain separate and unchanged.
- Actual RTX 5050 placement: `qwen3:8b` at 8K reported equal total/VRAM allocation (about 5.77 GiB), confirming full GPU model residency under the observed desktop load. At 16K it retained mixed CPU/GPU residency, consistent with the earlier 31/37-layer check. GPU residency can change as other applications consume VRAM.
- Installed `qwen3.5:9b` was also checked at 8K, one cold and one warm synthetic request with the same schema and prompt. Both models returned schema-valid budget/citation responses. The 9B model reported mixed memory residency (about 5.08 GiB GPU out of 5.95 GiB total), versus all-GPU residency for 8B; the single warm requests took about 2.52s and 1.03s respectively. Output lengths differed (57 vs 49 tokens); this tiny sequential probe is not a controlled speed benchmark or a human quality comparison. The default remains `qwen3:8b`.
- UI regression checks covered context captions and session reuse; missing/invalid optional context metadata in older/imported analyses is handled without crashing. New generation metadata needs no schema migration or dependency change. Read-only hash checks preserved every real-library table and all 112 reading PDFs; documentation link and whitespace checks passed.

## Native Windows NVIDIA checkpoint — 2026-10-30

- Actual hardware: NVIDIA GeForce RTX 5050 Laptop GPU, 8,151 MiB VRAM, compute capability 12.0, driver 592.82; Windows native Ollama 0.40.11 using its CUDA 13 backend. This establishes one workstation configuration, not Linux/container/macOS GPU support.
- A synthetic 16-passage embedding request returned 16 valid 1,024-dimensional vectors. Ollama reported all 29 embedding-model layers offloaded and identical total/VRAM allocation (about 1.14 GiB). The embedding model was already running entirely on the GPU before the configuration change.
- `qwen3:8b` with the existing 16,384-token context returned the expected synthetic budget and valid source ID. Ollama reported 31/37 layers on CUDA and mixed CPU/GPU residency (about 5.86 GiB VRAM), both before and after enabling Flash Attention. The 8 GB GPU did not fit the full answer model/context under the observed desktop memory load.
- The checked profile selects the NVIDIA UUID, disables Vulkan, enables Flash Attention and retains `f16` KV-cache precision and the existing generation budgets. The small embedding probe returned byte-identical serialized vectors and the same cited synthetic answer across profiles; this is not a general quality or speed benchmark. No KV quantization, context reduction or model replacement was applied.
- The Windows launcher was checked for PowerShell syntax, invalid-device and occupied-port refusal, hidden server startup, readiness and preservation of the calling process environment. It changes no persistent settings. See [installation commands](installation.md#optional-native-windows-nvidia-inference).
- Repeating both synthetic inference probes through the checked launcher confirmed the same placements and responses. The existing intelligence tests passed **24/24**; documentation links and whitespace checks passed, and every real-library table and all 112 reading PDFs remained hash-identical. Production application code was unchanged; no new Linux/Docker/full-suite run was needed for this Windows-only launcher.
- Private local probe artifacts are under ignored `output/gpu-rtx5050/`; no publisher text is used in them. Human-reviewed retrieval and claim-support gates remain pending.

## Development gold-authoring checkpoint — 2026-10-30

- Windows/Python 3.13: **286 passed, 1 opt-in installation test skipped**; dependency checks pass. One run concurrent with local Qwen drafting hit the existing three-second Analytics AppTest timeout; the full rerun after generation completed passed without application changes.
- Existing Ubuntu/WSL2 Python 3.13 environment: **55 targeted research/development tests passed**. This is not a fresh install or a full new Linux application validation.
- Chrome: synthetic interactive checks covered edits, partial review download/import, unsafe markup rendered literally and evidence-selection offsets after an emoji. The actual 60-case review page passed light/dark/mobile checks with no remote requests or browser errors and zero human decisions created.
- The private 60-case development candidate is structurally valid and source-hash bound, but all expected answers/absence labels and family grouping remain unreviewed. The 23 selected sources and remaining 89 unassigned records establish no held-out independence or extraction-quality target.
- Read-only hash checks preserved every real-library table and 112 reading PDFs. Production application code was unchanged. Docker/hosted CI were not run for this checkpoint.

## Research harness checkpoint — 2026-10-30

- Windows/Python 3.13.14: **268 passed, 1 opt-in live-server installation test skipped**, with real browser extraction enabled; dependency checks pass. The unchanged baseline was 231 passed/1 skipped.
- Existing native Ubuntu/WSL2 x86_64 Python 3.13.14 environment: **37 targeted harness tests passed**, plus a 24-case offline fixture answer run. A separate Linux bytecode-cache prefix avoided Windows cache contamination. This does not establish a fresh install or a full post-change Linux application pass.
- Local Ollama: three declared synthetic cases passed actual embedding retrieval; three declared synthetic cases passed Qwen answer generation. Model digests, available runtime version and actual generation settings are recorded in ignored run artifacts. Human support labels remain pending; these are operational smokes, not established quality percentages.
- The configured personal library is not used for evaluation caches. Existing real-library table hashes and 112 PDF hashes remained identical.
- Windows/Ubuntu CI definitions now run fixture evaluation/review scaffolding without models. Evaluation scripts/fixtures are wired into the Docker test target only. The Docker daemon is stopped, so the new test image was **not built or run**; hosted CI is also **not run** for these changes.

See [research evaluation](research-evaluation.md) for reproducible commands, exact metrics, reviewer declarations, corpus/label integrity and current limits. The broader platform checks below are historical; they are not a claim that the new research code passed every environment.

Later Windows checkpoint (general analytics/research usability): **231 passed, 1 opt-in live-server installation test skipped**. Separate synthetic browser checks verified general/specialist modes, topics/status/day scopes, CSV membership, both themes, 390px layout, page-jump navigation and article-to-Research handoff. The 112-article/PDF personal library remained hash-identical. This later checkpoint has not been repeated on Linux/Docker; the Milestone A matrix below is historical evidence for that milestone, not a claim that subsequent changes have been validated everywhere. See [milestones](../milestones.md) for the bounded cache/analytics performance measurements and pending human evaluation.

## Historical Milestone A verification matrix

| Check | Result | Actual environment/evidence |
| --- | --- | --- |
| Unchanged Windows baseline | PASS | Python 3.13.14, pip check, 196 tests with installed Chrome |
| Updated Windows regression suite | PASS | Python 3.13.14; 203 passed, 1 live-server test skipped in the ordinary full suite |
| Windows live UI | PASS | Separate disposable server/library: search, reading dialog, notes, downloaded PDF bytes and parsed PDF text |
| Fresh native Linux install | PASS | Ubuntu 26.04 WSL2 x86_64, separately installed CPython 3.13.14; fresh source/venv, runtime/dev install, pip check |
| Native Linux regression/browser | PASS | 203 passed, 1 live-server test skipped in the ordinary full suite; actual Chromium 156.0.8078.4 namespace/PID/network/seccomp status verified |
| Native Linux live UI | PASS | Separate disposable server/library: same search, notes and PDF checks, without Ollama |
| Original synthetic demo | PASS | 36 articles, isolated destination; no publisher/model calls |
| Offline PDF/export/portable restore | PASS | Windows, native Ubuntu and container; notes/PDF hash preserved; repeat restore idempotent; hard-link creation exercised |
| Docker build/runtime | PASS | Docker Desktop Linux engine 29.7.2, Compose 5.3.1; Python 3.13.14 on Debian 12, local x86_64 image |
| Container full suite and live UI | PASS | 204 tests, including browser-policy fixture and real UI/PDF download |
| Container sandbox/security settings | PASS | Non-root UID, read-only rootfs, all host capabilities dropped, no-new-privileges, default-deny seccomp plus documented namespace/chroot rules; Chromium's own status checked |
| Container recreation persistence | PASS | New Compose project and isolated named volumes; synthetic article, note, highlight and PDF hash survived force-recreation |
| Actual Docker build context audit | PASS | 69 allowlisted files at audit time; no private/generated paths, PDFs, databases, backups, env files or caches |
| Existing personal library preservation | PASS | Read-only hash baseline for all real tables and 105 PDFs; final check matches 105 saved articles |
| New hosted CI matrix | NOT RUN | Windows/Python 3.13, Ubuntu 24.04/Python 3.13 and Docker jobs configured; needs an explicitly requested push to execute |
| Native macOS / ARM64 / GPUs | NOT RUN | Not declared supported by this milestone |
| Host Ollama connectivity/model quality | NOT RUN | Optional; model service intentionally unavailable in installation smoke checks |
| AppArmor policy loading on Ubuntu 24.04 | NOT RUN | Scoped profile generation/syntax exercised; WSL kernel lacks the full AppArmor interface. Hosted CI uses the scoped profile if namespace restrictions are active |

## Commands and observations

Windows, from the repository root:

```powershell
$env:RUN_BROWSER_TESTS = '1'
$env:ARTICLE_BROWSER_CHANNEL = 'chrome'
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q tests
.\.venv\Scripts\python.exe scripts/check_install.py --browser
.\.venv\Scripts\python.exe scripts/smoke_install.py
.\.venv\Scripts\python.exe scripts/validate_native.py
```

Native Linux used a fresh source copy without Windows caches or user data. A checksum-verified temporary uv bootstrap provided CPython 3.13.14 without replacing the OS Python. The clean copy then ran the normal `python3.13 -m venv .venv`, `.venv/bin/python -m pip install -r requirements.txt`, pip check and development install with Linux runtime constraints. Ubuntu browser system packages were installed with administrator privileges using Playwright's `install-deps chromium`.

```bash
export ARTICLE_BROWSER_CHANNEL=chromium
export RUN_BROWSER_TESTS=1
export PLAYWRIGHT_BROWSERS_PATH=/path/to/validated-matching-browser-cache
.venv/bin/python -m pytest -q tests
.venv/bin/python scripts/check_install.py --browser
.venv/bin/python scripts/smoke_install.py
.venv/bin/python scripts/seed_demo.py
.venv/bin/python scripts/validate_native.py
```

The ordinary suite skips the live-server test because no server URL is supplied. `validate_native.py` supplies an isolated server and runs that additional test. The Docker validator supplies its isolated running app when executing the complete test image, so all 204 tests run together there.

```sh
docker compose config --quiet
docker build --target runtime -t artint:milestone-a .
python scripts/validate_container.py --report output/container-validation.json
```

The container validator uses a random Compose project and a dynamic host-loopback port, an empty env file, fresh named volumes and an intentionally unreachable model URL. It checks health, actual sandbox status, search/export/restore, persistence after recreation and live UI behaviour. It cleans only that project's containers/volumes. The separate test image includes dev dependencies and extraction-evaluator fixtures; these do not enter the runtime target.

Local evidence is under ignored `output/milestone-a/`: `container-validation.json`, `native-browser.log`, `native-ui.log`, `fresh-native.log`, `context-audit.json` and the real-library hash baseline. Those are local validation artifacts, not publisher fixtures to distribute.

## Issues found and resolved

- Windows `.pyc` files reused from a shared WSL checkout caused two source-inspection test failures. A separate Linux cache and a fresh source checkout removed this environment contamination; application behaviour was not rewritten to mask it.
- `/tmp` was cleared when WSL restarted. The isolated validation interpreter was moved to persistent temporary storage for the duration of checks.
- The browser CDN repeatedly timed out from Linux/container networking. The Dockerfile now obtains matching Chromium/FFmpeg from the digest-pinned official Playwright image. Native validation reused those same binaries. No certificate check or publisher restriction was disabled.
- Dropping all host capabilities exposed the upstream seccomp profile's capability-gated `chroot` rule. A marked syscall allowance lets Chromium chroot inside its own user namespace without granting outer `SYS_CHROOT` or `SYS_ADMIN` capabilities. Namespace/PID/network/seccomp checks and the real capture fixture then passed.
- Chromium's current sandbox page labels its first layer `Namespace`; diagnostics verify the actual current page rather than accepting launch success alone.

## Milestone A release checks

- [x] Preserve the existing library and retain schema version 6.
- [x] Validate Windows, native Ubuntu/WSL and local Docker without Ollama.
- [x] Keep private data outside Git and the actual Docker context/runtime.
- [x] Verify sandboxed browser policy, safe exports, restore and persistent volumes.
- [x] Document explicit migration, backup, loopback binding and removal behaviour.
- [ ] Run the new hosted CI jobs after an authorized push; investigate any runner-specific differences.
- [ ] Review the scoped AppArmor loading path on an AppArmor-enabled native host/runner.
- [ ] Tag a release or publish an image only after an explicit request and the selected release gates pass.

Milestone A's local verification is complete for the environments above. Hosted-runner/AppArmor checks remain explicit release follow-ups. Milestone B now has extraction-review tooling, but its human-reviewed quality gate remains open. Later analytics/research changes have their separate Windows checkpoint above and still need Linux/Docker revalidation; these historical checks establish no accuracy percentage.
