# Research workflow and user feedback

User review, 2026-11-08: the analysis was reported as useful, but seeing SAP, SpaceX and unrelated stories together made its scope hard to trust. Research also put model settings and many filters ahead of explaining what a user could do with saved articles. This is qualitative feedback, not a measured answer-quality result.

The user's downloaded private progress file was inspected on 2026-11-09. It records six explicit revised approvals and 54 pending cases, with story grouping unconfirmed. Notes flag unrelated source copies for the glass/creativity questions and leave an uncertain long-term-outcome case pending. These decisions and notes are preserved as supplied; they are not silently expanded into other approvals. The private JSON stays on disk and is Git-ignored rather than included in public documentation. No completed approved corpus or quality score follows from this partial review.

## Use your saved articles

1. Open **Research**, choose a **Research collection**, and optionally search for a topic. For example, choose your SAP collection or search for SAP. Publisher/date/length controls are under **More source filters**; saved labels and tags are under **Topic filters**.
2. Choose a task:
   - **Article summaries**: choose one **Article** and select **Summarize this article** for a summary, takeaways and citations. A chat model is enough. To summarize several, select up to 25 under **Articles to use** and choose **Summarize selected articles**. Each gets its own analysis; this does not establish a relationship between stories.
   - **Ask a question**: select the relevant sources under **Articles to use**, inspect **Review selected articles**, and ask a specific question. For example, “What collaboration did these reports announce, and what amounts or dates do they give?” Article summaries are not a prerequisite. Questions need an embedding model; generated answers also need a chat model.
   - **Search passages**, inside Ask a question: find original excerpts without generating an answer. This still needs the embedding model.
3. Inspect the cited passages. Use **Save research** to keep a completed question/result, or download its brief. Reopen it through **Saved research**. Article summaries are stored separately with their articles.

Nothing is selected for questions or batch summaries by default. **Include every match** explicitly chooses the whole filtered scope, up to 100 articles, including other pages. The individual selector is disabled while it is enabled. Keyword/filter matches are not a semantic-relevance guarantee. Changing filters or source pages clears the question/batch selection and this checkbox. A single-article summary selector narrows to the explicitly selected sources when present; otherwise it offers the current page for browsing.

**Analytics** describes collection counts, publishers, publication activity and available saved labels. It runs no new AI analysis. **Research** generates or browses article summaries and answers questions from selected saved text. Importing articles does not automatically generate summaries.

Model setup remains under **Research settings**, after the main workspace. An offline notice explains that existing summaries and saved research remain readable. No model starts merely because a user opens a task or changes a filter.

## Why the evaluation reviewer includes unrelated articles

The development-test selection explicitly has target sources and `distractor_ids`. A SAP question may deliberately include a SpaceX story to check whether retrieval ignores irrelevant evidence. That is a test condition, not a claim that the stories are connected, and it is separate from the application's user-selected scope.

The quick reviewer now explains this and separates other-story copies under **Other stories in this test**. Proposed story groups remain unreviewed; the grouping is not proof of relevance. All scoped copies remain available and must be inspected before confirming a missing-answer label. No source IDs, questions, gold spans, fingerprints or human labels are changed by this presentation fix. Older review files stay intact; new packets can load compatible downloaded progress.

## Remaining relevance work

The production retriever still ranks available passages by embedding similarity and returns its bounded nearest matches. Selection narrows where it searches; it does not prove every returned passage answers the question. A source citation identifies a passage but does not by itself establish that the passage supports the claim. The model can abstain, but that behavior still needs human measurement.

Keep the reviewed baseline before changing ranking. Milestone C should evaluate same-story and distractor-heavy cases, hybrid lexical/vector retrieval and optional reranking, plus a tested insufficient-evidence policy. Do not add an arbitrary cosine cutoff or advertise relevance/faithfulness percentages without evaluation. Automatic story clustering and claim-level comparisons remain planned work.

Acceptance: a new user can find relevant articles, summarize one, ask about an explicit group, inspect citations and save/reopen the result without opening advanced settings unless setup is needed. SAP-only question/summary tests must never send SpaceX article text. Workflow checks and fictional browser fixtures establish behavior, not model quality.
