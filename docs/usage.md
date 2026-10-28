# Article Intelligence operating guide

This is the detailed operating guide. Start with the [README](../README.md) for installation and the offline synthetic demo. A fresh checkout has no saved articles. References below to `data/` and `output/` describe local runtime artifacts and historical developer validation; those files and the 100-source collection are not distributed in the repository. Run all commands from the project root, not from `docs/`.

A local, Python-based MVP with **individual article PDFs** and **a separate analytics dashboard**. A batch ZIP download contains each PDF separately; it does not combine articles into one PDF.

The next release targets a dependable personal research tool. See [milestones](../milestones.md),
[architecture](../architecture.md), and [product requirements](../requirements.md) for scope, acceptance
criteria, and current limitations. Benchmark targets in those documents are not achieved results.

## Stack and why

- **Streamlit**: fastest dashboard/UI iteration, without a separate frontend.
- **Trafilatura + BeautifulSoup**: article-body extraction, metadata, references, and links.
- **Requests**: HTML fetching with timeouts, redirect checks, robots policy, and response size limit.
- **Playwright**: bounded headless rendering when a public article needs JavaScript; normal HTML extraction remains the first attempt.
- **SQLite**: local persistent articles, no database server.
- **ReportLab**: precise page layout, one PDF per article, clickable source link.
- **Streamlit components v2 + local SVG/CSS/JavaScript**: linked research analytics, with SQLite aggregates and matching light/dark themes.
- **Ollama + Qwen**: local summaries, key takeaways, topic labels, semantic search, and cited answers.

## Windows / VS Code quickstart

The current development environment is Windows with Python 3.13. Other Python/OS combinations
need clean-install validation before they are declared supported. Open this project folder in
VS Code, then open a PowerShell terminal:

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app/dashboard.py
```

If PowerShell activation is restricted, run `.\.venv\Scripts\python.exe -m streamlit run app/dashboard.py` instead.

Linux/macOS: `python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && streamlit run app/dashboard.py`.

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
date, title, or reading length. **More filters** adds analysis status, publication windows/custom dates,
missing publication dates, reading length, coverage theme, company mentions, saved-analysis topics, and personal tags.
It also sets the page size (25, 50, or 100). Active selections appear below the toolbar; **Clear filters**
resets them together while retaining sort and page size. Filters combine; multiple publishers/topics match
any selected value. Date ranges exclude undated articles. Coverage themes/company mentions work without AI summaries.
Previous/Next and the Page field navigate results. Search uses indexed literal word prefixes across title,
author, publisher, and text; multiple words must all match. Search/filter changes reset pagination to page one.
Returning from another workspace view retains the library page and filter values, including custom dates.
**Export library** prepares metadata CSV for every matching article (up to 25 MB), or a PDF ZIP
for the current page (up to 100 PDFs / 50 MB of input files). Full text stays in the reading copies.
Search and reading work without Ollama.
The interface uses local system fonts and does not depend on external design assets.

In the reading room, open **Notes & highlights** to save your own notes, edit comma-separated tags,
choose collections, or create a collection for a project. Save applies notes, tags and memberships
together. Personal tags appear on article rows and in **More filters → Personal tags**; selecting
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

Version 1 limits: 10,000 articles, 128 MB of JSON metadata, 20 MB per PDF, 250 MB compressed ZIP,
512 MB expanded data, plus bounded record counts for annotations and caches. Restore uses exclusive
file creation on a local filesystem supporting hard links. Caught failures roll back new records and
files; crash-proof coordination across multiple app/CLI processes remains future operational work.

Open **Analytics** for the **Research observatory**. The developer's local AI bubble collection contains 100 public
reading sources across 64 website hosts, alongside the five original demonstration articles.
Select a spending/valuation/returns/financing/power/history lens, a company, a publisher, or a
publication month: the counts, charts, passage cards, and 12-row source notebook filter together.
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

Open **Research** in the sidebar. Choose an installed local chat model under **Research settings**,
and select **AI bubble** under **Research collection** to work with that collection alone,
then open **Saved insights** and click **Analyze this page**
to generate summaries, key takeaways, and topic labels for the saved articles. You can also
analyze one article at a time, filter saved insights by topic, and download insights as JSON.
Previously generated insights remain viewable when Ollama is offline. Research source search and
pagination show 25 articles at a time. Analysis batches operate on that page rather than the entire library.

For **Ask library**, choose an installed embedding model under **Research settings** and enter a question.
The **Search passages** mode finds related text by meaning. **Answer with citations** generates an
answer from those retrieved passages and displays the original text for checking. You can
limit research to selected articles. Questions search the shown page by default; **Choose sources**
can narrow it or include every match when the filtered selection contains at most 100 articles.
The scope count is shown before submission. This is **not whole-library semantic search** for
collections above 100 articles: a persistent passage/vector index and background indexing remain planned.
If the model finds insufficient evidence, the app
shows that it cannot answer from the retrieved articles.

This computer already has `qwen3:8b`, `qwen3.5:9b`, and `qwen3-embedding:0.6b` installed.
For a new machine, install suitable models first, for example:

```powershell
ollama pull qwen3:8b
ollama pull qwen3-embedding:0.6b
```

The app does not download models automatically. Requests go to `http://127.0.0.1:11434`
by default; set `OLLAMA_BASE_URL` to use another Ollama server. Keep the default local
address to process article text on your computer. No API key is needed.

Insights and embeddings are cached in `data/articles.db`. Changed article content gets
new embeddings and invalidates its saved summary; analysis models have separate caches.
Long articles are analyzed up to 18,000 characters of complete passages and labeled
**Partial analysis** when text is omitted. Search indexes the full saved text in bounded
passages. Citations are validated against the passages sent to the model, but this does
not prove that each claim is true or fully supported; review the displayed source text.
Generated answers are research aids, not independent fact checks.

The implementation uses Ollama's [structured chat outputs](https://docs.ollama.com/capabilities/structured-outputs)
and [embedding API](https://docs.ollama.com/api/embed). The first model load and index build
can take longer, especially on a CPU.

## Key features

1. Ingest up to 10 public article URLs at a time.
2. Capture title, publisher, author, publication date, text, extracted word count, article links and image URL references (when present).
3. Create **one selectable-text PDF per article**. Includes original publisher URL as clickable citation [1], retrieval timestamp and page numbers. Markdown web links become clean clickable labels; basic headings, emphasis, lists, quotes, code, and tables are rendered when present in the saved text. Raw HTML stays literal text. Generation atomically replaces the previous file only after rendering succeeds.
4. Browse PDFs individually or download the current page's PDFs as a ZIP; export metadata for all matching articles as CSV.
5. **Analytics view**: linked collections, keyword/date/publisher/lens/company/month filters; up to 60 calendar months including zero-coverage months; six inspectable coverage lenses; company/lens co-mentions; top-eight publisher mix; matched concern/countercase passages; 12-row source pagination and filtered CSV export. The publisher selector includes every publisher in the collection.
6. **Research view**: local summaries, takeaways, topic filters, semantic search, and source-grounded questions. Saved insights remain accessible offline; model controls are grouped in Research settings.

## What this MVP deliberately does not do

- No website-wide recursive crawl or scheduling yet; URL batches are enough for a reliable MVP.
- No browser-based search/discovery, automatic OCR, or sentiment scoring yet.
- No screenshot-based faithful article archiving. Images are preserved only as URL references in JSON/SQLite, **not embedded in PDFs**. The individual PDF is a clean text reading copy.
- No guarantee of 100% article extraction. Paywalled, inaccessible, blocked, and JS-only pages can fail and are reported.
- Analytics uses versioned English keyword/alias rules, not a sentiment model. AI-generated summaries and topic labels appear separately in Research and Library.
- PDFs cite the original URL at article level. AI summaries and answers also cite saved text passages, which can be inspected in the workspace.

## Privacy, rights and deployment caution

Use only sources you are authorized to access/reproduce. Respect `robots.txt`, site terms, copyright, and rate limits; never bypass authentication or paywalls. The included fetcher tries to reject private/internal IP addresses, but public multi-user deployments require stronger DNS-rebinding and network egress protections. Run locally initially. The `RobotFileParser` logic makes a best-effort robots check; verify publisher requirements before large-volume jobs.

## Extraction evaluation

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

The review checklist is `review.csv` beside the reports. Inspect the original and local reading copy,
declare eligibility, mark body completeness/title/metadata/boilerplate pass or fail, and name the reviewer.
An incomplete checklist cannot produce a reviewed pass rate. Exclusions never disappear from the cohort.

## Large-library storage and verification

Library browsing uses SQLite FTS5, indexed sorting/filtering, and bounded result pages. Full article
text is fetched for reading or a scoped research operation. Dashboard totals and analysis counts are
computed in SQL; saved-insight lookup does not open a connection per article.

The first connection upgrades an existing database to schema version 6 in one transaction and makes
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

The new observatory queries have a separate dense synthetic benchmark:
`python scripts/benchmark_observatory.py`, reported in `output/observatory-benchmark.json`.
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
