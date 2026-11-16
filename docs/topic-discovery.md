# Topic discovery: implementation and research

Research checked **11 November 2026**. Artint now has an optional experimental corpus-level discovery workspace, separate from per-article AI labels and the question-answer retriever. The user's request to improve discovery authorizes this independent experiment before the pending real-source answer review; it does not close that review or change retrieval/prompt behavior.

## Use it

In your native Python environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-topics.txt
.\.venv\Scripts\python.exe -m streamlit run app/dashboard.py
```

Open **Analytics → Topic discovery (experimental)**. Choose a collection with 4–200 saved articles, an installed Ollama embedding model and a minimum theme size. Choose **Discover topics**. Opening the workspace, selecting map points, reading, changing the publication window or downloading an existing result starts no inference. A chat model is unnecessary.

The map supports hover, zoom and point selection; selecting a point expands its theme. Inspect representative articles, all source copies, unassigned articles and the exact sampled passages. Download the complete JSON to retain a result beyond the browser session. Library/scope changes label the retained result as old; a failed new run preserves it. Reading a source that changed since discovery shows a notice before opening its current copy.

Themes can now contain **finer subtopics**. Open a parent theme and use **Browse sources in this theme** to inspect a child, all parent sources or parent articles without a subtopic. Both levels use the chosen minimum number of distinct bodies. A parent needs at least twice that minimum for an attempted split; fewer than two discovered children leaves the parent unsplit. Unassigned parent articles stay separately inspectable and can also open in the reader. Browsing does not run inference.

Version 2 keeps the original full-space EOM parent fit, then performs one separate [HDBSCAN leaf-selection fit](https://scikit-learn.org/stable/modules/generated/sklearn.cluster.HDBSCAN.html) within each eligible parent, using the same normalized article vectors. This is a local refit, not a recovered or longitudinally aligned hierarchy. Parent membership, parent publication-share denominators and outliers remain independent of the child fit. Child membership and explicit parent remainders partition all parent source copies; duplicate bodies stay together. No split, forced assignment or human coherence is guaranteed.

Keyword generation additionally excludes `said`, `says`, `news`, `article`, `articles`, `reported` and `reportedly`. Source-derived terms may still include publishers and generic domain language; they are not reviewed topic names. A single fitted class can retain keywords rather than losing its entire vocabulary to the cross-class frequency filter. The export records these settings. Its version changes to `density-topics-v2`, while sampled text, article-vector construction and the original `density-topics-v1` embedding recipe/cache namespace remain unchanged. Existing vectors can be reused without model POSTs when the endpoint, selected manifest and sampled input still match. Older version-1 results remain readable.

Development dependencies include the backend. Base native/runtime dependencies remain unchanged. Docker can opt in with `ARTINT_TOPICS=1 docker compose build` (PowerShell: set `$env:ARTINT_TOPICS='1'`, then build); restart/recreate only when intentionally updating your local stack. The build argument is `INSTALL_TOPICS=1`. The default image omits the optional backend and still serves coverage analytics, saved results and the other workflows. The topic-enabled Linux runtime and its live UI/cache-recreation workflow are now [validated locally](validation.md#topic-enabled-docker-checkpoint--2026-11-12). A separate real-model smoke reached host Ollama from the image on the checked Windows Docker Desktop setup. See [installation](installation.md) for explicit connectivity and opt-in update commands; networking on other hosts remains deployment-specific.

## What other tools do

| Reference | Observed approach | Consequence for Artint |
| --- | --- | --- |
| [BERTopic](https://maartengr.github.io/BERTopic/) | Embedding/clustering plus class-based TF-IDF, representative documents, hierarchy and temporal analysis | Use corpus embeddings, density groups, inspectable representatives and terms; keep outliers visible |
| [Feedly](https://developers.feedly.com/reference/articlejson) | Separate concept classification, same-event clusters and trending clusters; [deduplication](https://docs.feedly.com/article/218-how-does-deduplication-work) uses content overlap | Keep topic similarity, event matching and duplicate handling distinct; avoid counting repeated content as independent theme growth |
| [Bunka](https://charlesdedampierre.github.io/BunkaTopics/bunka-api/topic_modeling/topic_model_builder.html) | Explorable document maps, clustering and term-based names | Offer a linked map and source inspection, while declaring projection limits |
| [Top2Vec](https://github.com/ddangelov/Top2Vec) | Joint topic/document representations and semantic navigation; its contextual variant supports within-document topic spans | Plan multi-topic coverage of long documents as a separate evaluated extension |

These are documented capabilities, not independently measured rankings. Artint does not claim parity with these systems or implement their entire pipelines. Feedly's near-duplicate handling is broader than this first implementation's exact normalized-body grouping.

## Developments worth tracking

- **BERTopic 1.0 beta:** its [official development changelog](https://maartengr.github.io/BERTopic/dev/changelog.html#version-100b1) records `1.0.0b1` on 1 November 2026, including multimodal support and rewritten LLM representations with an Ollama integration. The same page identifies `0.17.4` as the default stable release. A prerelease and new embedding defaults need a separate compatibility/quality comparison; they are not installed or substituted into Artint by this change.
- **Contextual Top2Vec:** the [maintainer's documentation](https://github.com/ddangelov/Top2Vec#contextual-top2vec-overview) describes multiple topics and topic spans within documents, with specific token-embedding models and a beta warning. This is useful for long articles, but it is not a drop-in consumer of Artint's existing Ollama passage vectors. The linked underlying work is from 2024; this is an available direction, not a newly invented 2026 technique.
- **FASTopic and LLM refinement:** [FASTopic](https://github.com/bobxwu/FASTopic), published in 2024, provides a different document/topic modeling approach; the [2026 LX Topic paper](https://arxiv.org/abs/2603.03623) studies LLM refinement around that family. These are candidates for later comparisons, not evidence that a particular method will improve this collection.
- **Semantic Signal Separation:** [Turftopic's documentation](https://x-tabdeveloping.github.io/turftopic/s3/) models semantic axes rather than document groups. It could help overlapping themes, but answers a different question from the first grouping workflow.
- **Human-guided topic descriptions:** [TopicGPT](https://aclanthology.org/2024.naacl-long.164/) investigates natural-language topic descriptions and control. For Artint, a later optional local-labeling experiment should preserve memberships and source terms and measure labeling usefulness; it should not silently rewrite a cluster because a model invents a plausible description.

My implementation choice is a bounded local baseline: existing Ollama embeddings, native scikit-learn density clustering and source-derived class TF-IDF terms. This avoids introducing another embedding model or chat-model labeling step. The newer approaches remain comparison candidates until they demonstrate useful gains on the same reviewed corpus, with measured runtime/memory and label provenance.

## Pipeline and limits

1. Validate the entire explicit collection before inference: 4–200 source copies, at least four distinct bodies, at most 8 MiB total saved text, 256,000 characters per body and valid source URLs. Oversized scopes fail instead of silently taking the first page.
2. Collapse whitespace/case/Unicode-normalized identical bodies for modeling, retaining every publisher/source identity. This is neither general near-duplicate detection nor proof of independent reporting.
3. Select up to six passages spread from beginning to end of each distinct body. Long-article partial coverage is disclosed, with the actual sampled text retained. Normalize passage embeddings, average them into article vectors and normalize again. One primary group per body is the current contract; mixed-theme articles can lose detail in this average.
4. Fit scikit-learn **HDBSCAN** in the full normalized embedding space with Euclidean distances, `min_samples=2` and an explicit minimum cluster size. Parent themes use EOM selection; eligible parents receive a single finer leaf refit as described above. No chosen number of topics or forced assignment is required. All-noise output is valid. Native HDBSCAN and the third-party package have parameter-convention differences; do not equate their settings without checking documentation.
5. Derive class TF-IDF keywords from sampled text, using English stop words and unigrams/bigrams, excluding terms present in more than 90% of fitted classes. These are descriptive terms, not evaluated natural-language labels. Unicode text is accepted; multilingual topic quality is unmeasured.
6. Choose up to three representative distinct bodies by similarity to the group centroid, then expose all original source copies. A 2D PCA projection supports navigation only, with retained variance disclosed; it does not determine groups or certify pairwise distances.
7. Compute adjacent 7/30/90-day publication shares using distinct bodies, their earliest usable saved publication dates and all dated bodies—including outliers—as denominators. Missing/future dates and empty comparison windows stay explicit. A share change describes this saved corpus, not worldwide topic growth, causation or importance. Refitting after corpus changes can change groups/IDs; longitudinal topic alignment is not implemented.

Discovery uses a separate cache namespace derived from algorithm version, endpoint, model name and observed manifest digest. It never reads legacy question-search vectors or saved topic labels. New vectors are committed only after the complete run observes a stable selected digest; failures and detected drift do not leave partially attributed new vectors. Each request batch holds at most 16 passages and vectors are limited to 4,096 dimensions. Inventory observations cannot authenticate resident inference weights or detect every change-and-reversal race. Existing question-retrieval cache policy remains unchanged.

## Validation and next steps

`tests/test_topic_discovery.py` covers corpus grouping, copy counts, representatives, noise-only output, changed source/model identities, namespace isolation, invalid vectors/URLs/metadata, long-article sampling, atomic failed-batch behavior and publication denominators. The view tests cover explicit execution, bounded whole-scope reads, missing dependencies, retained results and stale source/scope notices. Full and browser checkpoints are recorded in [validation](validation.md).

For repeatable Docker validation without a host model service:

```powershell
.\.venv\Scripts\python.exe scripts/validate_container.py --topics --report output/my-container-topics/report.json
```

The validator uses its own randomly named project, original fictional sources and a loopback scripted embedding endpoint. It checks discovery/export/map selection, warm cache reuse after app recreation, the existing installation evidence and preservation of pre-existing containers/volumes. This scripted test is separate from real-model inference and from the pending real-source coherence benchmark. [Container validation](../docker/README.md#validate-optional-topic-discovery) describes its isolation and lifecycle.

An original fictional fixture can be run against installed Ollama models in a new ignored directory:

```powershell
.\.venv\Scripts\python.exe scripts/demo_topic_discovery.py --output output/my-topic-demo
```

It creates its own synthetic library, records real embedding/clustering output, checks shuffled-input membership stability and zero-new-embedding cache reuse, and reports agreement with the authored fixture categories. These measurements test a simple diagnostic corpus; they establish no real-world topic coherence, multilingual quality or competitor advantage. Next comparisons should use a frozen permitted real corpus, human judgments of representative articles/labels, outlier coverage, stability under additions and latency/memory. BERTopic/FASTopic comparisons, human renaming, multi-topic spans, semantic near-duplicates and evaluated event grouping remain follow-ups.
