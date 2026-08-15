# Chunking Strategy Comparison

Fixed-size and recursive chunking implemented from scratch (no LangChain), then measured against real retrieval — all variants embedded into pgvector with a `strategy` tag, the same queries run against each in isolation.

**Two headline findings:**

1. Recursive chunking is **two phases**, and the split phase alone is not a chunking strategy. It enforces a ceiling on piece size and says nothing about a floor. Split finer than your target and let the merge pass do the packing.
2. **Token-level overlap is not a cosmetic problem.** It produced a false rank-1 in testing — a chunk that matched on a severed word fragment while containing no answer. Found by measurement, not inspection.

**Corpus:** ~570 tokens, 6 topic paragraphs (Python, Django, FastAPI, cricket, cooking, space), 8–9 short sentences each, one per line. Deliberately adversarial — unrelated topics packed tightly, so boundary errors surface immediately.

**Stack:** `tiktoken` / `cl100k_base` for counting, `text-embedding-3-small` for embeddings, pgvector with an HNSW index (`vector_cosine_ops`). All sizes in tokens, never characters.

---

## Part 1 — Chunk shape

| # | Strategy | size / overlap | Chunks | Range | Finding |
|---|---|---|---|---|---|
| A | Fixed-size | 100 / 10 | 6 | 78–100 | Perfect capacity use, structure-blind. Cuts mid-phrase at every boundary (`"...Model Template View architectural"` \| `"framework."`). A chunk can end before the clause that gives it meaning. |
| B | Recursive, split only | 100 / 10 | 6 | 77–99 | Best-looking output — one chunk per paragraph, hierarchy never fell past `\n\n`. Almost entirely a property of this corpus having paragraphs just under budget. Looks excellent, generalizes poorly. Reproduce by calling `text_splitter()` directly — `recursive_chunker()` always merges. |
| C | Recursive, split only | 50 / — | 50 | 6–15 | Every paragraph fell to sentences. ~75% of capacity wasted, each chunk a lone sentence with no context. *Worse* than the naive fixed chunker despite the more sophisticated algorithm. |
| D | Recursive, split + merge | 100 / 10 | 7 | 28–100 | Merge fixes C's starvation. Split budget of 90 left a mixed bag — three paragraphs intact, two fragmented — so one chunk stranded at 28 tokens when an intact 90-token paragraph arrived next. |
| E | Recursive, split + merge | 50 / 10 | 15 | 38–50 | Split budget of 40 forces every paragraph to sentences, giving uniform ~11-token pieces. Tightest, most consistent packing. New cost: topic bleed — some chunks straddle paragraph boundaries. |

### The design principle

> **The splitter's job is to enforce a ceiling on granularity. The merger's job is to produce the chunks.**

Every failure above traces back to that division being blurred. C is the splitter asked to produce chunks. D is the merger handed pieces too coarse to pack. E works because the splitter was aggressive enough to give the merger real freedom.

Two properties that only become obvious once you build it by hand:

**The merger can group pieces but can never split one.** A large atomic piece arriving after small ones always forces a short flush — that's D's 28-token chunk. Unfixable in the merge phase; fixed only by splitting finer upstream.

**Two phases can't independently enforce the same limit.** D initially produced 109- and 102-token chunks against a limit of 100. After a flush the buffer resets to `overlap` tokens *then* appends the piece, so the true bound is `overlap + max_piece_size`. Split at `chunk_size - overlap`, merge at `chunk_size`.

---

## Part 2 — Retrieval results

28 chunks (6 fixed + 7 recursive@100 + 15 recursive@50) embedded into one pgvector table, separated at query time by a metadata filter on `strategy`. Same five queries against each, `top_k=3`. Queries were chosen to hit known failure modes, not easy matches.

**Did rank 1 contain the answer?**

| Query | fixed | rec_100 | rec_50 |
|---|---|---|---|
| How does Django keep the database schema in sync? | ✅ 0.468 | ✅ 0.478 | ✅ **0.611** |
| What is used for authentication in FastAPI? | ❌ 0.498 | ✅ **0.679** | ✅ 0.664 |
| What makes a cricket bowler effective? | ✅ 0.461 | ✅ 0.460 | ✅ **0.483** |
| Which Python feature helps with memory efficiency? | ✅ 0.419 | ✅ 0.438 | ✅ **0.503** |
| How do you improve the taste of chicken? | ✅ 0.319 | ❌ 0.494 | ✅ **0.519** |

**recursive@50: 5/5 correct at rank 1, top score on 4 of 5.**

### Finding 1 — fixed chunking retrieved the wrong topic

Query 2 asked about FastAPI authentication. Fixed chunking's rank 1 was a chunk about *Django's* auth system — it matched on the shared word "authentication" while the real answer (OAuth2/JWT) sat at rank 2.

Structure-blindness made concrete: fixed slicing puts the FastAPI paragraph's opening in the same chunk as the Django paragraph's ending, so that chunk's embedding straddles two topics and matches queries for both. The right chunk existed; a wrong-topic chunk with overlapping vocabulary outranked it.

### Finding 2 — the overlap artifact caused a false positive

This upgrades a limitation previously written off as cosmetic.

rec_100's rank 1 for query 5 was a chunk beginning with the fragment `" taste."` — the token-level carry-back had severed *"Marinating chicken improves tenderness and taste."* mid-sentence. That orphaned word, plus "taste" appearing twice more in the chunk, pulled a query about taste to rank 1.

**That chunk does not contain the answer.** The marinating sentence lives in the previous chunk, which ranked 2nd at 0.367.

The fragment acted as a keyword magnet with none of the meaning attached. In production this hands the LLM context that cannot answer the question — the direct path to a hallucinated answer or a wrong refusal. Ugly text is a style problem; a wrong rank 1 is a retrieval bug.

### Finding 3 — smaller chunks score higher, and that's dilution

An embedding is one fixed-size vector representing the *whole* chunk. One sentence and one hundred sentences compress into the same 1536 numbers, so every additional sentence averages the others away. A chunk with one relevant sentence and eight irrelevant ones produces a vector sitting near the centroid of all nine — near "general Django stuff," not near "migrations specifically."

Query 1 shows it cleanly. rec_50 returned a chunk opening with the migrations sentence among ~5 total → **0.611**. Fixed returned that same sentence buried among 9 others → **0.468**. Identical answer present in both; 0.14 of similarity lost purely to surrounding noise.

The counterweight: shrink chunks and similarity sharpens, but each chunk carries less context for the LLM to actually answer from. That tension *is* the chunk-size decision.

### Finding 4 — why smaller chunks avoid topic bleed

Counterintuitive at first: rec_50 has *more* chunks straddling paragraph boundaries, yet retrieves better.

Query 2 explains it. rec_100 had room after the JWT sentence to keep going into the cricket paragraph, producing a half-auth/half-cricket chunk that scored 0.379. rec_50 could only fit ~4 sentences, so it filled with FastAPI content and flushed *before* reaching cricket — a clean, all-FastAPI chunk at 0.664.

Smaller chunks flush more often, so each is less likely to spill across a topic boundary. It isn't that they contain more; it's that they contain less unrelated material.

---

## Recommendation

**recursive@50 with 10-token overlap**, for this corpus and this embedding model.

Fixed-size remains the correct baseline for genuinely unstructured input — transcripts, logs, OCR output — where there is no structure to exploit and predictability is worth more than boundary awareness.

The right size is corpus-dependent, not universal. Topically dense documents favour smaller chunks; documents where an answer routinely spans several sentences favour larger ones. The rule that transfers: **split finer than your target and let the merge pass do the packing.**

---

## Changes needed before production

**1. Piece-level carry-back instead of token-level.** Now justified by measurement rather than aesthetics — Finding 2 is a real retrieval failure. The fix tracks pieces alongside tokens in the merge buffer and carries back whole pieces until roughly `overlap` tokens are covered. Cost: carry-back size becomes approximate (a whole sentence may exceed the overlap budget), so the ceiling calculation needs a wider margin. This is what LangChain and LlamaIndex both do — arriving at it from a measured failure is the more useful route.

**2. Threshold on the score gap, not the absolute score.** The next sprint day adds a similarity threshold so the agent refuses when retrieval finds nothing relevant. These numbers show why an absolute cutoff is fragile: a threshold of 0.4 would have made fixed chunking refuse query 5 despite holding the answer at 0.319, while letting rec_100 confidently answer from an answerless chunk at 0.494. Absolute scores shift with chunk size; the gap between rank 1 and rank 2 is the more stable signal.

**3. Chunk size revisited per corpus.** The 50/10 result is tuned to a deliberately adversarial test document. Real support documentation is topically coherent, so larger chunks will likely hold up better. Re-run this harness against the actual corpus rather than carrying the number across.

**4. Reranking and hybrid search remain open.** Both failures above are retrieval-*ordering* problems — the correct chunk was present, just outranked. A cross-encoder reranker addresses exactly this, and BM25/tsvector hybrid retrieval addresses the keyword-match cases pure vector similarity handles poorly. Deferred to post-deploy, but this eval set is what they'll be measured against.