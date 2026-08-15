# Day 2 — End-to-End RAG (LEAN)

Wired the first end-to-end RAG `/ask` flow: retrieval → context construction → generation → validation → response. Reused Day 5's `VectorStore.search()` and Day 3's retry wrapper unchanged — only two new pieces this session, `build_context()` and the FastAPI route.

## Pipeline verified end-to-end

`POST /ask` confirmed working on real queries against the pgvector store — retrieval → `build_context()` → generation → Pydantic validation → response, no manual glue in between. Tested with "explain what is FastAPI?" and "tell me about cricket": both returned `grounded: true`, and the answers only contained facts traceable to the retrieved chunks, no outside-knowledge leakage. This verifies the RAG slice of the pipeline; classification/router and tool/general-chat branches are not yet part of `/ask` and are scheduled for the later project-core stage.

Generation prompt used:
```
Answer the user's question using ONLY the context below.
If the context is insufficient, say so — do not use outside knowledge.

For "sources_used", copy the exact text after "[Source:" for each context
block you relied on — do not paraphrase or invent source names.

Respond with this exact JSON, nothing else:
{"answer": "...", "grounded": true/false, "sources_used": ["..."]}

Context:
{context}
```
Question goes in the user message, separate from the system prompt — same separation used for the Day 2 classifier.

## Generalizing `call_llm_with_retry`

Day 3's `validation_and_retry()` was hardcoded to the classifier's prompt and schema — couldn't be reused for RAG answering without duplicating the whole retry loop. Refactored the retry/validate logic into `call_llm_with_retry(system_prompt, user_message, schema, max_retries)`, with `schema` typed as `type[BaseModel]` so any Pydantic model can be validated against. Kept the old function name as a thin wrapper pre-filled with the classifier's prompt + schema, so Day 3's own CLI didn't need to change. Classifier and RAG generation are now two callers of one function instead of two copies of the same loop.

New schema for this call site, parallel to the classifier's `QueryValidation`:
```
RAGAnswerValidation: answer, grounded (bool), sources_used (list[str])
```
`grounded` is the model self-reporting whether its own answer is actually supported by the context — a free first-pass signal for later refusal logic, not ground truth (that's LLM-as-judge, later).

## The `sources_used` bug — mislabeled, not missing

First real responses came back with `sources_used` populated with either the chunking `strategy` tag (`"merged"`) or model-paraphrased sentence fragments — not document sources. Root cause: `build_context()`'s label was built from `chunk['metadata'].get('strategy')`, which is chunk-merge metadata, not document provenance. The actual document path was already sitting in every chunk dict as a top-level `source` key — promoted to a real typed column back when idempotent ingestion was fixed — just never read.

Two-part fix:
- Label switched to `chunk['source']` instead of the strategy field.
- Prompt tightened to explicitly instruct copying the source string verbatim into `sources_used`, not paraphrasing it — without this, the model filled the gap by inventing citations from its own answer text.

Confirmed fixed on both a grounded (FastAPI) and a multi-chunk (cricket) query — real file paths came back correctly in both.

## Important grounding limitation

`grounded: true` is currently an LLM self-report, not an independently verified grounding guarantee. Pydantic validates the response structure and types, but it does not prove that every claim in the answer is supported by retrieved context. The current FastAPI and cricket answers were manually checked and were traceable to retrieved chunks, but this should be treated as an observation, not a system-level guarantee. Formal grounding/faithfulness evaluation is deferred to the eval stage.

## Known limitation, not a bug

`sources_used` currently returns the same path 2–3 times when multiple retrieved chunks share one source file — accurate (different chunks, same file) but redundant-looking on a single-document test corpus. Will resolve naturally once ingestion covers a real multi-file corpus; not worth deduping until then, since a single-file test can't actually validate that dedupe logic does the right thing.

## Current test findings

The FastAPI query retrieved directly relevant chunks and produced a concise answer. The cricket query required multiple chunks from the same source and produced an answer whose claims were manually traceable to those chunks. These two tests are useful smoke tests, but they are not enough to establish RAG quality.


## ========================= PDF ingestion findings ========================= 

Ingested a real PDF (multi-section technical doc) to stress-test chunking/retrieval
against page-boundary text. Re-ran `doc_ingestion.py` a second time and confirmed
idempotency holds on this new path too: `upsert()` returned the same rowcount (27)
both times — same `(source, chunk_index)` conflict target correctly matched and
updated existing rows instead of duplicating.


**Overlap carry-back confirmed working, but resets at page boundaries.** Verified by
inspecting consecutive chunk content directly — a chunk's start correctly repeats the
prior chunk's last ~10 tokens *within* a page. But since `doc_ingestion.py` calls
`recursive_chunker()` once per page (a loop), overlap does not carry across page
breaks — unlike `.txt` ingestion, which chunks the whole document as one continuous
string. PDF-specific limitation, not present in the `.txt` flow. Not fixed — logged
as a known gap.

**Retrieval ranking can favor keyword overlap over topical relevance.** Query "how
does Redis caching consistency work?" returned a `grounded: true` answer that was
accurate but incomplete — missing the locking/single-flight sentence from the same
source section. Root-caused by dumping raw `search()` results (score + content)
before assuming an LLM or context-budget issue: the chunk containing that sentence
never made top-k. A different chunk sharing surface keywords ("Redis," "cache,"
"unavailable") from an unrelated section scored higher than the correct chunk.
Confirms the Day 6 tradeoff concretely — small chunk_size (50 tokens) improves
individual chunk retrieval scores but fragments one coherent explanation across
multiple chunks, and pure cosine similarity doesn't guarantee all fragments of one
concept retrieve together. This is the class of problem reranking/hybrid search
(already on the post-deploy roadmap) is meant to address — not fixed today.

**PDF text bleed at chunk boundaries is the same overlap artifact from Day 6, not
cross-file contamination.** Initially suspected the `.txt` file was bleeding into
PDF chunks; checking the `source` field on the actual row ruled that out — it was
a PDF flow-diagram line getting severed mid-arrow by a chunk boundary. Same known
artifact, different content shape.


## Still open

Dedupe `sources_used` (order-preserving, not `set()`) once corpus has multiple files. Similarity threshold/refusal, reranking, hybrid search, and LLM-as-judge remain deferred according to the 12-day roadmap; implement them only when the eval results justify them.