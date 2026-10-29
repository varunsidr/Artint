# Reviewed extraction evaluation

Milestone B tooling, 2026-10-29. This extends `scripts/evaluate_extraction.py`; it adds no second capture pipeline, model judge or library writes. The existing diagnostic cohort remains a convenience sample and has zero human-reviewed eligible cases. Its observed 78 captures and 22 failures do not establish extraction completeness or the 90% target.

## Freeze the method before capture

Start with [the protocol template](evaluation-protocol.example.json) and [candidate CSV format](extraction-candidates.example.csv). The example URLs are reserved fictional domains; replace them with permitted sources before a live benchmark. Source kinds are `article`, `analysis`, `opinion`, `abstract`, `transcript` or `other`.

Declare selection method, eligibility/exclusions, topic/language/date window and publisher/source-type coverage. Do not select only URLs that previously captured successfully. Candidate lists accept 1-500 unique URLs; small development fixtures do not satisfy the benchmark target. HTTP(S) parsing at freeze time makes no network requests; actual capture still applies the existing public-address, robots, redirect and resource policies.

```sh
python scripts/evaluate_extraction.py --freeze-candidates candidates.csv --protocol protocol.json --output output/evaluations/my-cohort
python scripts/evaluate_extraction.py --output output/evaluations/my-cohort --phase baseline
```

The first command creates a versioned manifest containing protocol and source-list fingerprints without fetching anything. It refuses an existing manifest or capture phase. The second command explicitly captures sources using the existing policy-compliant evaluator. It never creates article-library records or PDFs. Phase captures, diagnostics and locally permitted HTML/readings remain under that output directory. The 128 MB cache budget still applies; 500 candidates is a limit, not a promise that every reading copy fits.

Use `--offline --mode html` to replay available frozen responses without network/browser requests. Paired extraction changes must use the same manifest and cached responses; retain failures that have no response to replay. The legacy `--freeze --audit ...` command remains available for historical diagnostics and does not create a prospective cohort.

## Prepare an immutable-snapshot review

Finish the phase, then:

```sh
python scripts/evaluate_extraction.py --output output/evaluations/my-cohort --phase baseline --prepare-review
```

This creates `review-baseline-v2.csv` exclusively; it never overwrites a completed review or the legacy `review.csv`. Every row contains phase, manifest fingerprint and a fingerprint of capture outcome, source/body hashes, title/date/author and extractor/diagnostic configuration. Available local reading copies are checked against the captured title/URL/body hash; modified copies and symlinks are rejected. A missing reading copy cannot receive an acceptable-body judgement. A different phase or changed reading/metadata cannot silently reuse the same labels. To review an improved phase, create its separate `review-improved-v2.csv`.

Do not edit identity/fingerprint, URL, source-kind or capture-status columns. Keep every row, including failures and exclusions. `pending` means genuinely not reviewed, not a failed extraction or an exclusion. Source kinds describe the predeclared cohort; if an original is a different type, record the discrepancy and eligibility reason rather than rewriting the frozen identity.

## Human rubric

Compare the original source with the phase-specific reading text under `local-cache/`. Captures can be outdated or access can change; record that uncertainty instead of asserting completeness without a reference. Set `review_kind=human`, identify the actual reviewer and enter an ISO timestamp with timezone in `reviewed_at`.

| Criterion | Required check |
| --- | --- |
| `body_complete` | Substantive article paragraphs and conclusions are retained; a teaser is not a full article. |
| `title_correct` | The saved title belongs to this article rather than a listing or surrounding page. |
| `metadata_correct` | Author and other available metadata are faithfully represented; missing values are not fabricated. |
| `date_correct` | Publication date is distinguished from updates/comments; missing dates are accurately represented, with timezone uncertainty noted. |
| `publisher_correct` | Final source/publisher attribution matches the original and redirect provenance. |
| `no_boilerplate` | Menus, comments, unrelated recommendations and access banners do not contaminate the body. |
| `no_missing_sections` | Relevant lists, tables, headings and substantial sections are present where supported by the declared source scope. |
| `not_duplicate` | This is a distinct eligible source under the predeclared duplicate/syndication rule. Retain duplicate candidates and record an exclusion or failure according to that rule. |

For a captured eligible source, fill every criterion with `pass` or `fail`; all must pass for an acceptable reading copy. An eligible source whose capture failed is counted as a failure even if someone fills its checks with `pass`. For `excluded`, supply an explicit reason, human identity and review timestamp. Do not exclude a source merely to remove a failed capture from the denominator.

## Summarize without recapturing

```sh
python scripts/evaluate_extraction.py --output output/evaluations/my-cohort --phase baseline --review-summary
```

This validates the complete frozen row set and snapshot bindings, then writes separate `review-baseline-summary.json` and `.md`. It does not modify captured phases, cached bodies or the library. Missing/duplicate cases, invalid eligibility, unreasoned exclusions, missing human identity and stale evidence are rejected. Unreviewed rates are null, not an invented 0% success rate.

Reports include candidate composition, reviewed eligible/pass/fail/excluded/pending denominators, host/source-kind strata and a descriptive Wilson 95% interval. That binomial interval assumes independent cases; it is not adjusted for publisher/story dependence. Do not call it cluster-aware or use it to establish a general-web success rate. Case mix, small publisher subgroups and convenience selection remain limitations even with a favourable overall number.

For a second reviewer, give them a separate copy of the same phase checklist, retain independent decisions, then:

```sh
python scripts/evaluate_extraction.py --output output/evaluations/my-cohort --phase baseline --review-summary --second-review-file second-review.csv
```

A different declared reviewer must label the overlapping cases. Reports retain disagreements, including eligibility disagreements; resolve them through a documented human adjudication process and preserve the original checklists. The tool does not authenticate identities or prove independence merely because names differ.

The declared-cohort gate requires a prospective protocol, no pending first-review cases, at least 100 reviewed eligible sources across at least 10 hosts, at least 90% acceptable readings, at least 20% double review and no unresolved disagreements. Hosts are not necessarily independent publisher organisations. This is a scoped engineering gate, not statistical evidence that the extractor succeeds on 90% of the web. Legacy unbound review counts cannot satisfy it.

## Existing diagnostic cohort

The local commands executed for the existing 100-source convenience sample were:

```sh
python scripts/evaluate_extraction.py --prepare-review --phase improved
python scripts/evaluate_extraction.py --review-summary --phase improved
```

Result: **100 pending; zero reviewed eligible; pass rate not established; gate false**. The phase captures and legacy review were preserved. Completing this diagnostic review can identify failures; a new prospectively declared eligible cohort is still needed for the release gate.

Keep publisher HTML, full reading text, reviewer notes and private metadata under ignored `output/`. Publish only original/licensed fixtures and approved aggregate reports/configuration. Do not claim a human-reviewed benchmark until those reviews actually exist.
