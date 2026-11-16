# Article Intelligence operating guide

This is the detailed operating guide. Start with the [README](../README.md) for installation and the offline synthetic demo. A fresh checkout has no saved articles. References below to `data/` and `output/` describe local runtime artifacts and historical developer validation; those files and the 100-source collection are not distributed in the repository. Run all commands from the project root, not from `docs/`.

A local, Python-based MVP with **individual article PDFs** and **a separate analytics dashboard**. A batch ZIP download contains each PDF separately; it does not combine articles into one PDF.

The next release targets a dependable personal research tool. See [milestones](../milestones.md),
[architecture](../architecture.md), and [product requirements](../requirements.md) for scope, acceptance
criteria, and current limitations. Benchmark targets in those documents are not achieved results.

## Stack and why

Optional **Analytics → Topic discovery (experimental)** discovers corpus themes with article embeddings rather than saved per-article labels. Install `requirements-topics.txt` in the native environment or opt into the container build with `ARTINT_TOPICS=1`. Choose a collection and select **Discover topics**; no model starts on navigation. Inspect the interactive map, representative/source copies, unassigned articles and actual sampled text, then download JSON. Results remain available after failed requests and show when their original source/scope is stale. [Topic discovery](topic-discovery.md) explains setup, source limits, publication-share calculations and the competitor/research comparison. This optional path changes no question-answer ranking or existing labels.

- **Streamlit**: fastest dashboard/UI iteration, without a separate frontend.
- **Trafilatura + BeautifulSoup**: article-body extraction, metadata, references, and links.
- **Requests**: HTML fetching with timeouts, redirect checks, robots policy, and response size limit.
- **Playwright**: bounded headless rendering when a public article needs JavaScript; normal HTML extraction remains the first attempt.
- **SQLite**: local persistent articles, no database server.
- **ReportLab**: precise page layout, one PDF per article, clickable source link.
- **Streamlit components v2 + local SVG/CSS/JavaScript**: linked research analytics, with SQLite aggregates and matching light/dark themes.
- **Ollama + Qwen**: local summaries, key takeaways, topic labels, semantic search, and cited answers.

## Windows / VS Code quickstart

The checked native environments are Windows and Ubuntu/WSL2 x86_64 with Python 3.13. Docker packaging is also checked. See [installation](installation.md) and [validation](validation.md) for exact support boundaries and pending hosted CI checks. Open this project folder in VS Code, then open a PowerShell terminal:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app/dashboard.py
```

If PowerShell activation is restricted, run `.\.venv\Scripts\python.exe -m streamlit run app/dashboard.py` instead.

Linux/Bash, with Python 3.13 installed separately from the operating system Python:

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install --with-deps chromium
.venv/bin/python scripts/check_install.py --browser
.venv/bin/python -m streamlit run app/dashboard.py
```

Docker Compose: `docker compose up --build -d --wait`, then open http://127.0.0.1:8501. It uses separate persistent library/PDF volumes and publishes only on host loopback. Native files are migrated only by an explicit portable-backup restore. See [installation and recovery](installation.md) for volume ownership, removal without erasing data, optional host Ollama, sandbox requirements, spare ports and the container demo. Native macOS and ARM64 remain unvalidated.

`python scripts/check_install.py` is read-only; add `--browser` to test sandboxed Chromium. `python scripts/smoke_install.py` uses temporary synthetic storage to check search, PDF export and portable restore. Use the Python executable from your environment. The UI remains useful without Ollama.

Open the local Streamlit URL (usually `http://localhost:8501`). Paste public article URLs, one per line. Each successful extraction creates `output/pdfs/<article_id>.pdf` and persists metadata/content to `data/articles.db`.

**Article capture** defaults to **Auto** in Import articles and the selected search-results toolbar.
Auto first reads the normal HTML. If the body is missing/short and the page appears to need JavaScript,
it opens a fresh headless browser and extracts the rendered reading text. **HTML only** skips that step.
Search itself still uses the free RSS provider. The reader's **Source details** records HTML extraction
or browser rendering for each saved article. Existing saved URLs are reused without another capture.

New captures also record **capture checks**. Import results and background activity flag copies needing
review; the reading room explains missing metadata, possible missing/extra page content and decoding
problems. Automated checks are signals to inspect the original, not a guarantee of complete or correct
content. Earlier saved copies show that no checks were recorded, and are not silently reprocessed.
Short excerpts under 80 estimated reading units are rejected. Unicode words and CJK characters are
counted so unspaced articles are not rejected solely for lacking spaces. Explicit publisher publication
metadata takes precedence over inferred dates; comments are excluded from new reading copies.

New captures remove a recognized publisher-home/social/newsletter promotion template before saving text, PDFs or research evidence. Complete standalone blocks qualify; quotations, editorial discussion and mixed article paragraphs remain. Capture diagnostics record the cleanup version and removed-block count. This rule is intentionally narrow and does not remove every possible advertisement or related-story widget. Existing saved text/PDFs remain their original copies; pasting an already saved URL reuses that copy rather than reprocessing it.

The Python Playwright package is included in requirements. Auto tries installed Chrome, then Edge,
then Playwright Chromium. This Windows workspace has been checked with installed Chrome. If none is
available, install Chromium in your virtual environment:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

`ARTICLE_BROWSER_CHANNEL` can select `auto` (default), `chrome`, `msedge`, or `chromium`.
No personal browser profile is used. Recognized sign-in/paywall/challenge pages and network/HTTP/robots
failures do not trigger a browser retry. Browser resource requests have host, byte, request and time
limits; images, fonts, media, forms and service workers are blocked. Some pages will still fail.

The sidebar opens five focused views: **Library**, **Analytics**, **Research**, **Search articles**, and **Import articles**.
Library is the default view. Search saved text, filter your sources, sort articles, then choose **Read**
for the reading room with article text, saved analysis, original source, and PDF download.
The full-width toolbar provides search, collection, multiple publishers, and sorting by saved/publication
date, title, or reading length. **General filters** adds analysis status, publication windows/custom dates,
missing publication dates, reading length and page size (25, 50, or 100). **Topic filters** adds scoped
saved-analysis topics and personal tags, with an explicit **Show AI investment filters** option when matching coverage signals exist.
Active selections appear below the toolbar; **Clear filters**
resets them together while retaining sort and page size. Filters combine; multiple publishers/topics match
any selected value. Date ranges exclude undated articles. Coverage themes/company mentions work without AI summaries.
Previous/Next and the compact page menu navigate results; open the page menu to jump directly. Search uses indexed literal word prefixes across title,
author, publisher, and text; multiple words must all match. Search/filter changes reset pagination to page one.
Returning from another workspace view retains the library page and filter values, including custom dates.
**Export library** prepares metadata CSV for every matching article (up to 25 MB), or a PDF ZIP
for the current page (up to 100 PDFs / 50 MB of input files). Full text stays in the reading copies.
Search and reading work without Ollama.
The interface uses local system fonts and does not depend on external design assets.

Library has separate **General filters** (status, publication window, reading length and page size, alongside the main search/collection/publisher/sort toolbar) and **Topic filters**. Topic choices and tags come from the complete matching source scope, not only the visible page. Changing general context prunes incompatible selections. **Show AI investment filters** explicitly enables the existing coverage lenses/tracked companies and resets when the general context changes; these are not general-purpose topic classifications.

Research uses the same general/topic distinction. Its saved-topic list is scoped to the search, collection, publisher, date, status, reading length and selected analysis model/version. No saved labels means an explicit empty state; unrelated labels are never substituted. Topic/tag choices exclude their own selections when computing available alternatives, then combine with general predicates for source results.

In the reading room, open **Notes & highlights** to save your own notes, edit comma-separated tags,
choose collections, or create a collection for a project. Save applies notes, tags and memberships
together. Personal tags appear on article rows and in **Topic filters → Personal tags**; selecting
several matches any selected tag. Keyword search still searches the publisher text and metadata.
Your notes are separate from the source text and are not supplied as evidence to the AI.

Expand **Add a highlight**, paste an exact saved passage and optionally add a note. For repeated text,
choose its occurrence. Highlights retain the quote, source offsets and text revision; text changes mark
them as belonging to an earlier copy instead of silently moving them. Current highlights are marked
in the Article tab where their rendered text can be mapped. Highlight notes can be edited or removed.
Limits: 20,000 characters of article notes, 20 tags of 40 characters each, and 200 highlights per
article. A highlight quote is 3–5,000 characters; its note can contain up to 5,000 characters.
Annotations do not change reading PDFs or invalidate saved AI analysis.

To remove an article, open **Source details → Remove from library**, confirm the selection and choose
**Delete article**. This removes its text, analysis, annotations, memberships and search-index entry.
Only its exact managed PDF is removed; outside files and PDFs shared by another article are kept.
Reusable embedding caches are retained. A failed database operation restores the staged PDF;
interrupted deletions are recovered from a journal on later app visits. Finish or stop active imports
before deleting or restoring data.

Choose **Export library → Backup & restore → Prepare full backup** for a portable ZIP of the whole
library, regardless of current filters. It includes article text, notes, tags, highlights, collections,
saved analyses, cached vectors and available managed PDFs. Missing/invalid/unmanaged PDFs are reported;
their article text remains included. Import jobs are not part of a portable backup.

To restore, choose the **Restore backup** tab, upload the ZIP, **Inspect backup**, review its counts,
then select **Restore missing data**. An empty library also has a direct restore button. Restore keeps
existing article text and nonempty notes. Tags, nonduplicate highlights and memberships are merged;
annotations for a different saved text revision are skipped. Existing PDFs are kept, missing managed
PDFs can be restored, and unrelated destination files are never overwritten. Repeating a restore
does not add duplicate articles or highlights. Restore does not contact publishers or a model service.

Version 2 limits: 10,000 articles, 1,000 saved research results, 128 MB of JSON metadata, 20 MB per PDF, 250 MB compressed ZIP,
512 MB expanded data, plus bounded record counts for annotations and caches. Restore uses exclusive
file creation on a local filesystem supporting hard links. Caught failures roll back new records and
files; crash-proof coordination across multiple app/CLI processes remains future operational work.

Open **Analytics** for the **Research observatory**. **General analytics · any topic** is the default. Select your collection or search saved coverage to explore publication activity, publisher distribution, current-analysis counts, saved topics and reading lengths. Date spans up to 45 days use daily counts; longer spans show up to 60 months, including empty intervals. Topic/status/date clicks filter the notebook and CSV together. Labels come only from current saved `qwen3:8b` analyses; unanalyzed articles still contribute metadata charts and explicitly show missing labels. No model runs automatically. Text and labels support Unicode; generated labels depend on your saved model output and are not translated automatically.

The coverage indicators and comparison panels add:

| Field | What it measures |
| --- | --- |
| Published · last 30 days | Saved articles published in the 30 calendar days ending on the displayed date, compared with the adjacent prior 30 days. Every active filter applies to both periods; date filters can restrict either period. A zero prior count has no percentage baseline. This is saved publication volume, not web-wide growth or new-import volume. |
| Largest publisher share | Leading publisher's article count divided by all articles in the selection, plus the share of the top three labels. Labels do not establish corporate ownership or editorial independence. |
| Analysis coverage | Percentage with a current saved default-model analysis, with the missing count. |
| Publication dates available | Percentage with a usable publication date; undated copies are listed separately. |
| Publisher details | Each displayed publisher's share, percentage analyzed and latest saved publication date. Up to eight publishers are shown; the selector retains all source choices. |
| Topic coverage by publisher | Up to six leading saved topic labels across five leading publishers. Each count uses distinct articles across the whole filtered selection. Select a nonzero count to filter by both topic and publisher; the notebook and CSV follow the same scope. Topic reach counts all publishers in the selection, including those outside the five columns. |
| Collection readiness | Articles with recorded authors, saved topic labels, current capture checks, capture flags and unavailable checks. Unknown/stale checks are not counted as passed. Capture flags are automated diagnostics, not truth or completeness ratings. |

Topic comparison appears in General analytics and uses current saved `qwen3:8b` labels. Missing labels are explicit; absence does not establish that a publisher omitted a subject, and matching labels do not establish agreement. Metadata fields work without a model. Calendar day is part of the analytics cache key so publication windows refresh on the next render after a date change. Light/dark themes, keyboard selection and contained horizontal table scrolling support narrow screens.

This prioritizes article/source-volume patterns described by [Feedly trend analysis](https://docs.feedly.com/article/748-trend-analysis) and cross-source inspection described by [Ground News](https://ground.news/frequently-asked-questions). Artint's saved-source counts do not supply those services' bias, ownership or factuality classifications.

Choose **AI investment coverage · specialist** to use the six English keyword lenses, tracked companies and concern/countercase passages. General mode hides these specialized categories and its source rows show saved topic labels instead. Analytics previews remove Markdown/image destinations; the stored source copy is unchanged.

The developer's local AI bubble collection contains 100 public
reading sources across 64 website hosts, alongside the five original demonstration articles.
Select a spending/valuation/returns/financing/power/history lens, a company, a publisher, or a
publication date in the specialist view: the counts, charts, passage cards, and 12-row source notebook filter together.
Search the coverage, change the publication window, reset filters, or export the exact selection.
Chart transitions and counters use short animations; reduced-motion preferences disable them.
Coverage themes have consistent blue, purple, teal, amber, clay, and slate accents across bars,
matrix columns, and source tags. Raised panels separate charts from the workspace background.
Hover a chart mark or focus it with the keyboard for a themed card with its exact count and context;
Escape dismisses the card. Timeline selection uses the dot itself, with a small ring for keyboard focus.

**Collection notes** explains the sample and failures. The collection audit (`output/ai-bubble-collection.json`, local artifact)
records every attempted URL, saved source, exclusion, and failure. This is a diverse shuffled sample,
with at most five sources per website host, not a representative survey. Six entries are public research
abstracts; other sources include news, commentary, institutional analysis, and interview/transcript pages.
Publication dates come from source metadata and may be approximate. The cutoff for this collection
is 27 October 2026. These counts describe text mentions and co-mentions, not author stance, verified
financial relationships, or a conclusion that a bubble exists. New sources have coverage signals;
generating their AI summaries is a separate action in Research.

Use **Dark mode** in the sidebar to switch between the matching light and dark appearances.
The choice follows you across views and is retained in the page URL on refresh. A direct
`http://localhost:8501/?theme=dark` link opens the dark workspace. Charts, menus, model settings,
and the reading room use the same selected palette; PDF exports keep their paper-friendly design.

Alternatively, edit `example_urls.txt` and run:

```sh
python cli.py example_urls.txt
# Optional: disable browser fallback
python cli.py example_urls.txt --fetch-mode html
```

For development, install `python -m pip install -r requirements-dev.txt`, then run
`python -m pytest -q`. PDF tests inspect selectable text and link annotations; the dashboard
startup test uses an isolated database and mocked offline model discovery.
The real-browser fixture is opt-in: set `$env:RUN_BROWSER_TESTS='1'` before running
`python -m pytest -q tests/test_browser_extraction.py`. It renders deterministic JavaScript through
installed Chrome/Edge/Chromium without fetching a live publisher. It is not a publisher-coverage benchmark.

`requirements.txt` pins application dependencies; `requirements-dev.txt` adds test tools.
`requirements-lock.txt` is the full tested development-environment snapshot. To reproduce
that snapshot in a fresh virtual environment, use `python -m pip install -r requirements-lock.txt`.
It includes development dependencies and is not a cross-platform compatibility guarantee.

## Discover articles by topic

Open **Search articles** to search beyond the saved library. Enter one to five comma-separated topics,
add optional highlighted keywords, and request 5, 10, 25, 50, 100, or a custom count from 1–100.
Keywords can highlight previews or require any/all matching phrases in the title or preview.
Choose publishers (including The Guardian and The Hindu), optional extra domains, a requested language,
reported date window/custom bounds, and relevance or newest-first ordering.

The first provider is free **Bing News RSS**, used as a personal, non-commercial news aggregator.
No API key is required. This source mainly covers recent news; it is not a comprehensive historical
archive or a commercial search backend. The result count is a target, not a guarantee. Publisher-domain
and reported-date filters are checked locally; language is requested from the provider and is not
independently verified. Dates and snippets may differ from the publisher's actual article. Source/provider
limitations and partial results are shown instead of filling gaps with unrelated or invented entries.
The query is sent to Bing; this discovery feature requires network access.

Search does not save previews as articles. Select individual results, the current ten-result page, or
all results, name the collection, then choose **Import selected**. Up to 100 selected URLs are queued
for background extraction and individual PDFs. You can keep browsing while **Import activity** polls
progress. Existing exact URLs are reused without refetching; later batches with the same collection name
and topic query extend that collection. Failures remain visible. **Stop after current article** cancels
the remaining queued items. After an application interruption, unfinished work resumes when its
five-minute worker lease expires. No automatic network retries run on ordinary access failures.

Imported articles appear in Library and its collection selector, and can be selected in Analytics and
Research. Importing does not generate AI summaries. Reading text supports Unicode, but exported PDFs
still have limited font coverage for non-Latin scripts; the page discloses this for relevant languages.

## Local AI research

Start Ollama, then launch the dashboard from this project folder:

```powershell
ollama serve
```

In a separate terminal:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/dashboard.py
```

Open **Research**, choose a **Research collection** or search a topic, then choose a task. **Article summaries** opens first: choose one **Article** and click **Summarize this article** for a summary, takeaways and topic labels with cited passages. For several summaries, select up to 25 under **Articles to use** and click **Summarize selected articles**. Selected sources also narrow the single-article selector. Previously saved summaries remain readable offline. The source list is paginated at 25 articles; nothing is implicitly selected for a question or batch job. **More source filters** and **Topic filters** are collapsed by default. Model configuration is under **Research settings**, below the main workspace. See the [short workflow guide and user feedback](research-workflow.md).

From a reading room with no saved analysis, choose **Analyze in Research** to open that exact article. **Generate analysis** processes only that source and needs a chat model, not an embedding model. No analysis starts just by navigating. Your existing Library and Research filters are preserved; return to Library or the research source list when finished. Offline and deleted-source states explain the next action.

For **Ask a question**, explicitly select articles under **Articles to use** and enter a question. You do not need to summarize them first. Choose an installed embedding model under **Research settings** if one is not connected.
The **Search passages** mode finds related text by meaning. **Answer with citations** generates an
answer from those retrieved passages and displays the original text for checking. You can
inspect the selected titles under **Review selected articles**. An empty selector means no question sources; submission is disabled. **Include every match** explicitly uses all filtered articles, across pages, when there are at most 100. It disables individual selection while enabled. Changing filters or source pages clears the selection and include-all choice. The exact scope count is shown before submission; filter membership alone is not a guarantee that stories are related. This is **not whole-library semantic search** for
collections above 100 articles: a persistent passage/vector index and background indexing remain planned.
If the model finds insufficient evidence, the app
shows that it cannot answer from the retrieved articles.

Answer cards include expandable cited passages, with original-source links and saved text. Retrieval details show passages searched, embeddings reused/created and the original elapsed time. Submitting the same question, mode, source revision, models, endpoint and context-policy version reuses the last result in this session; select **Generate a fresh result** to run again. Reuse applies to the current browser session; **Save research** creates a separate durable snapshot. Cache reads are batched and the embedding model remains loaded between input batches, then unloads after the final batch before answering. Model choice, output budget and retrieval ranking are unchanged. Hardware/model latency and independently reviewed answer quality remain separate measurements.

A failed new question keeps your last completed answer and its downloads. If the current source/model selection differs, the result is labelled as the previous completed result and shows its original scope/models. It also remains available when Ollama is offline or filters match no articles. **Clear research result** clears only this session answer and error; saved articles and analyses remain. Starting a new browser session or restarting the app can lose an unsaved result; choose **Save research** or download it to keep a copy.

Use **Download research brief** for a Markdown answer with numbered citation links, original URLs and the exact cited saved passages. **Download full result** saves a versioned JSON snapshot with all retrieved passages and available model/context/retrieval metadata. New results also record the original UTC completion time, selected/searched article IDs, fingerprints of the loaded source copies, library revision, research mode and embedding model. Export time is separate from completion time. Markdown links normalize international domain names and encode Unicode paths; JSON preserves original URLs. Passage-search exports contain evidence without a generated answer; abstention exports explain the limited evidence. Exporting uses the current result without another model call or storage write, and the download does not rerun research. Claim/source markup is literal and unsafe links or missing citations prevent an incomplete export. These downloads are portable files; **Save research** also keeps the result in this library. Neither saving nor exporting establishes claim faithfulness.

### Save and reopen research

New Ollama-generated summaries and answers also retain [request fingerprints](research-evaluation.md#request-fingerprints) in their JSON metadata: messages/schema hashes, requested settings for each context attempt, requested/reported model names and the runtime observed by the client. Full-result downloads, saved research and backups preserve these fields. Older results remain readable without them. Weight digests and reused embedding provenance are not verified, and matching fingerprints do not guarantee the same answer or establish claim support.

New workspace questions and passage searches also take [model inventory observations](research-evaluation.md#model-inventory-observations-in-research) before and after the run, retaining the selected manifest digests and available quantization details. A version-change warning or incomplete-observation notice stays with the result and its brief; full details stay in JSON, saved research and backups. Metadata failure does not discard a completed answer. Reading, saving, exporting and reusing that result do not recheck models. **Generate a fresh result** takes new observations but does not rebuild cached search vectors; matching installed manifests do not prove the provenance of those vectors or the model's answer quality.

Choose **Save research** below a completed cited answer, abstention or passage search. The button stores the exact question, answer, retrieved passages, original completion time, source selection/revisions and available model/context/retrieval metadata. Saving the same snapshot twice keeps one record. Saving does not call the model, and saved evidence is never added to later retrieval automatically.

Open **Research → Saved research** to search saved questions and reopen them offline, including after restarting the app or restoring a backup. Lists show 20 questions per page. Original passages remain unchanged when source articles are updated; a changed-source notice identifies comparable revisions. Restored/remapped identifiers or absent fingerprints remain explicitly unverified. Available model tags/settings are retained; exact model weight digests and prompt identities are not newly inferred for older results.

**Clear research result** clears the current browser result. **Remove saved research** deletes a persisted result and its quoted evidence after confirmation. Deleting an article also removes every saved research result linked to that article's original selection, and the reading room shows the affected count. Earlier downloaded exports/backups keep their copies. Article IDs remapped by restore are linked to the new local record without rewriting original passage/citation IDs.

Limits are 1,000 results, 256 KB per result and 64 MB of result JSON per library. Export/delete older results to free capacity. Saved research is included in full library backup version 2; version-1 library backups remain restorable. Changes to research history invalidate prepared backups without changing the source-library revision used for question reuse.

Under **Research settings**, **Check model status** explicitly reads the selected endpoint's installed models, runtime and loaded memory placement. The table follows light/dark appearance and scrolls within its panel on narrow screens. Installed, not loaded and unavailable are distinct states. GPU percentages are model-memory residency, not GPU utilization; a model that has unloaded is not thereby a CPU model. The report is a timestamped snapshot; repeat the check to update it. No inference is performed. See [startup/compute diagnostics](installation.md#model-readiness-and-residency-checks) for the CLI and compatibility limits.

New generation automatically chooses **8K or 16K context**, using an estimate that includes the system instructions, complete prompt and appended JSON schema, plus 1,600 output tokens and a 512-token margin. This is a UTF-8-based estimate, not exact model tokenization. The checked Ollama controls reject oversized input and disable context shifting. An 8K context failure, or reported input token count leaving too little answer space, retries the identical request at 16K; if 16K cannot fit, narrow the selection rather than accepting a shortened answer. Window changes can reload the model and add latency. New answers/analyses display their selected context and reported input token count; saved older analyses are retained. Generation requires **Ollama 0.40.11 or newer**, the oldest checked runtime; passage search and saved insights remain available separately. The 8K profile fit the checked RTX 5050 entirely, but other GPU memory use can change placement. No model, cache-precision or answer-quality improvement is assumed from this change.

The repository does not include model weights. Install suitable models on your machine first, for example:

```powershell
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b
```

The app does not download models automatically. Requests go to `http://127.0.0.1:11434`
by default; set `OLLAMA_BASE_URL` to use another Ollama server. Keep the default local
address to process article text on your computer. No API key is needed.

The embedding and answer models have different jobs: `qwen3-embedding:0.6b` creates search vectors; `qwen3:8b` writes cited answers. The [embedding model card](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) describes a multilingual 1,024-dimensional model. We retain it as an efficient baseline for an 8 GB laptop; suitability for this collection still needs human-reviewed retrieval evaluation. A larger embedding model is a candidate to compare after that baseline, rather than an established quality improvement. Native Windows NVIDIA users can use the [CUDA launcher and placement checks](installation.md#optional-native-windows-nvidia-inference). CPU activity during research can include retrieval, storage and partially offloaded answer inference even when embedding inference runs entirely on the GPU.

Insights and embeddings are cached in `data/articles.db`. Changed article content gets
new embeddings and invalidates its saved summary; analysis models have separate caches.
Long articles are analyzed up to 18,000 characters of complete passages and labeled
**Partial analysis** when text is omitted. Search indexes the full saved text in bounded
passages. Citations are validated against the passages sent to the model, but this does
not prove that each claim is true or fully supported; review the displayed source text.
Generated answers are research aids, not independent fact checks.

For developer evaluation, use the separate [research harness](research-evaluation.md). It freezes source hashes/gold spans, calls the same retrieval/answer functions in an isolated cache, and creates reports plus pending human-review packets. Its 24 original fictional cases are machinery diagnostics, not established quality evidence. It does not change this UI or save product research sessions.

The implementation uses Ollama's [structured chat outputs](https://docs.ollama.com/capabilities/structured-outputs)
and [embedding API](https://docs.ollama.com/api/embed). The first model load and index build
can take longer, especially on a CPU.

## Key features

1. Ingest up to 10 public article URLs at a time.
2. Capture title, publisher, author, publication date, text, extracted word count, article links and image URL references (when present).
3. Create **one selectable-text PDF per article**. Includes original publisher URL as clickable citation [1], retrieval timestamp and page numbers. Markdown web links become clean clickable labels; basic headings, emphasis, lists, quotes, code, and tables are rendered when present in the saved text. Raw HTML stays literal text. Generation atomically replaces the previous file only after rendering succeeds.
4. Browse PDFs individually or download the current page's PDFs as a ZIP; export metadata for all matching articles as CSV.
5. **Analytics view**: general collection/query/date/publisher/topic/status filters; daily or monthly activity, saved topic labels, analysis coverage, reading profiles, publisher mix, 12-row notebook and matching CSV. The optional AI investment view adds six lenses, company co-mentions and concern/countercase excerpts. The publisher selector includes every publisher in the collection.
6. **Research view**: Article summaries and Ask a question are separate tasks. Questions and batch summaries use explicit sources; saved summaries/research remain accessible offline. Model controls follow the main workspace under Research settings.

## What this MVP deliberately does not do

- No website-wide recursive crawl or scheduling yet; URL batches are enough for a reliable MVP.
- No browser-based search/discovery, automatic OCR, or sentiment scoring yet.
- No screenshot-based faithful article archiving. Images are preserved only as URL references in JSON/SQLite, **not embedded in PDFs**. The individual PDF is a clean text reading copy.
- No guarantee of 100% article extraction. Paywalled, inaccessible, blocked, and JS-only pages can fail and are reported.
- General analytics describes saved metadata and current saved model topic labels; it does not run a fresh analysis or establish article stance. The optional investment view uses versioned English keyword/alias rules, not a sentiment model.
- PDFs cite the original URL at article level. AI summaries and answers also cite saved text passages, which can be inspected in the workspace.

## Privacy, rights and deployment caution

Use only sources you are authorized to access/reproduce. Respect `robots.txt`, site terms, copyright, and rate limits; never bypass authentication or paywalls. The included fetcher tries to reject private/internal IP addresses, but public multi-user deployments require stronger DNS-rebinding and network egress protections. Run locally initially. The `RobotFileParser` logic makes a best-effort robots check; verify publisher requirements before large-volume jobs.

## Extraction evaluation

Milestone B adds [phase-bound human review](extraction-evaluation.md) and a [prospective protocol template](evaluation-protocol.example.json). Legacy `review.csv` counts remain available but cannot establish the release gate. New review commands do not fetch, modify existing phase results, create library articles or produce PDFs. Human labels and an eligible prospective cohort are still required.

The first frozen diagnostic cohort contains 100 previously saved AI-bubble sources across 64 hosts.
The live run captured 78, found 19 access/subscription gates, and encountered three network failures.
This is a convenience sample containing abstracts and other page types, not 100 independently reviewed
eligible articles. The M2 90% completeness target has not been established.

Open the paired report (`output/evaluations/ai-bubble-20261028/comparison.md`, local artifact) for changes and remaining
flags. Four author fields were recovered, five publication dates switched to explicit published-date
metadata, and one article's extraneous outside text was removed while retaining detected source-block
coverage. Five captures remain flagged. Publication dates still need review, including time-zone boundaries.

The evaluator never writes to SQLite or generates library PDFs. Reports contain diagnostics, hashes
and metadata; publisher HTML and phase-specific reading text stay in the ignored `local-cache/`
directory. Do not redistribute these caches without permission. The runtime/development tests use
synthetic fixtures instead.

To create another cohort from an audit with 100 saved URLs and at least 10 hosts:

```powershell
python scripts/evaluate_extraction.py --freeze --output output/evaluations/my-cohort --phase baseline
# After an extractor change, compare the same cached pages without network traffic:
python scripts/evaluate_extraction.py --output output/evaluations/my-cohort --phase improved --offline
```

Keep the baseline source version when collecting a new cohort if you plan to replay the old engine.
The recorded development cohort includes a local baseline snapshot whose checksum matches the initial
report; `--engine frozen --phase baseline --offline` can replay that snapshot. `--resume` continues a
phase only when its source/cohort/diagnostic checksums and mode still match. Offline replay requires HTML
mode; Auto may fetch JavaScript resources and is rejected with `--offline`.

The original `review.csv` is a legacy, unbound checklist and cannot certify the reviewed quality gate.
Use the current phase/hash-bound `--prepare-review` and `--review-summary` workflow in the
[extraction review guide](extraction-evaluation.md). Inspect the original and local reading copy,
declare eligibility and review criteria, and record the human reviewer and timestamp. Pending labels,
failed captures and exclusions remain visible; no labels means no reviewed pass rate.

## Large-library storage and verification

Library browsing uses SQLite FTS5, indexed sorting/filtering, and bounded result pages. Full article
text is fetched for reading or a scoped research operation. Dashboard totals and analysis counts are
computed in SQL; saved-insight lookup does not open a connection per article.

The first connection upgrades an existing database to schema version 7 in one transaction and makes
a pre-upgrade SQLite backup under `data/backups/`. It backfills content fingerprints and publisher keys,
builds the full-text index, and installs mutation triggers. Version 2 adds research collections and
content-versioned coverage signals; a version-1 upgrade preserves the existing full-text index and caches.
A failure rolls back schema changes.
Version 3 adds persistent discovery import batches and per-URL states without rebuilding the existing
FTS index or changing article/insight/embedding records. `ARTICLE_PDF_DIR` optionally selects an isolated
PDF output directory for browser QA; it defaults to `output/pdfs`. Version 4 adds article capture methods
and persisted batch capture modes; legacy articles default to HTML extraction, and existing queued
imports default to Auto. Article content, fingerprints, saved analyses, and embeddings are preserved.
Version 5 adds versioned capture diagnostics and per-item import failure codes. Legacy diagnostics
default to an unassessed state, without rewriting saved article text or invalidating AI caches.
Version 6 adds personal notes/tags/highlights, indexes and mutation tracking, plus the deletion journal.
Existing source text, cached analyses, vectors and collection memberships are preserved. Portable
backups store relative PDF entries and restore paths under the current configured PDF directory.
Keep the backup until you have verified your library. SQLite must include FTS5, as the tested Python
3.13 / SQLite 3.50.4 environment does. `ARTICLE_LIBRARY_DB` optionally selects a separate library file;
the default remains `data/articles.db`.

Run the isolated synthetic benchmark from the project directory:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_library.py --counts 1000 10000
```

It uses disposable databases, never your library. The report at `output/library-benchmark.json`
records the dataset, hardware/runtime, warm-query p95 timings, bounded payload size, and AppTest script
timings. These measurements exclude browser paint, publisher fetching, PDF generation, live inference,
and semantic index construction. They do not establish production concurrency or extraction/AI quality.

The observatory queries have a separate dense synthetic benchmark covering general and specialist modes,
with three hand-authored saved topic labels per article. Use a new output filename to retain earlier runs:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_observatory.py --output output/benchmarks/observatory-current.json
```

Omitting `--output` writes `output/observatory-benchmark.json`. These are warm SQL/serialization timings,
excluding browser paint, fetching, PDFs, inference and concurrency; synthetic labels do not evaluate model quality.
The earlier library report measures the previous analytics aggregate function and does not establish
the observatory's performance.

The developer's public-source collection can be resumed locally using its saved discovery manifest (not distributed in Git):

```powershell
.\.venv\Scripts\python.exe scripts/collect_ai_bubble.py --target 100 --as-of 2026-10-27
```

The collector respects robots, validates redirects, limits responses and request rates, skips access
blocks, detects duplicate text/regional titles, and writes an incremental audit. It is a research
collection script, not the planned durable ingestion/job system or an extraction-success benchmark.

## Suggested future architecture

Keep Streamlit and SQLite through the local beta. Next steps are extraction completeness evaluation,
library organization, evaluated AI retrieval,
and durable local jobs. Introduce an API, external workers, or a server database when measured
workloads or hosted requirements justify them. See [architecture.md](../architecture.md) for the
current data flow, trust boundaries, and staged evolution.

## Files

- `app/extract.py` — network fetching and extraction
- `app/reports.py` — PDF rendering
- `app/pdf_content.py` — safe Markdown-to-PDF content rendering
- `app/storage.py` — SQLite persistence
- `app/exports.py` — bounded, on-demand metadata CSV and page PDF exports
- `app/dashboard.py` — workspace entry point and view routing
- `app/ui.py`, `app/assets/dashboard.css` — shared presentation and responsive styles
- `app/library_view.py`, `app/analytics_view.py`, `app/ingest_view.py` — library, analytics, and import screens
- `app/observatory_view.py`, `app/observatory_data.py`, `app/facets.py` — linked analytics, bounded SQL, inspectable coverage rules
- `app/assets/observatory.*` — trusted local component markup, styling, and animation/interaction code
- `app/intelligence.py` — Ollama integration, cited summaries, semantic retrieval, and answers
- `app/ai_dashboard.py` — research UI and saved-evidence presentation
- `app/discovery.py`, `app/discovery_view.py` — bounded free news discovery, filters, safe highlights, previews, and selection
- `app/discovery_imports.py` — persisted selected-URL import batches, leases, progress, stop requests, and collection membership
- `cli.py` — batch command-line mode
- `tests/` — offline smoke tests
- `milestones.md`, `architecture.md`, `requirements.md` — delivery plan and acceptance criteria
- `requirements-dev.txt`, `requirements-lock.txt` — test dependencies and tested environment
- `scripts/benchmark_library.py` — isolated synthetic load benchmark
- `scripts/collect_ai_bubble.py` — resumable, audited public-source collection
- `scripts/benchmark_observatory.py` — isolated analytics query benchmark
