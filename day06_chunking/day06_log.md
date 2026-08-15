# Day 1 — Chunking Strategies

Built two chunkers from scratch: fixed-size (token-based) and recursive (separator hierarchy + greedy merge). No LangChain. Both pure functions returning `{text, source, chunk_index, strategy}` dicts — no DB coupling, so the output feeds the ingest pipeline unchanged. Then embedded all variants into the Day 5 pgvector store and measured which one actually retrieves better.

## What actually took the time

Not the fixed chunker — that was 20 minutes. The recursive one, because "recursive chunking" is described everywhere as one thing when it's actually **two phases solving opposite problems**:

- **Split-down** walks a separator hierarchy (`\n\n` → `\n` → `. ` → ` ` → `""`), recursing into any piece still over budget. Guarantees a *ceiling*: no piece bigger than the budget.
- **Merge-up** greedily packs those pieces back into chunks up to `chunk_size`, carrying back `overlap` tokens on each flush. Guarantees a *floor*.

The splitter alone produces garbage. At `chunk_size=50` it returned 50 single-sentence pieces of 6–15 tokens — 75% of budget wasted, each chunk stripped of surrounding context. The merger isn't an optimization; it's the half that makes recursive chunking worth doing.

Corollary that only became obvious after tracing a bad run: **the merger can group pieces but can never split one.** A large atomic piece arriving after small ones forces a short flush — that's how one chunk came out at 28 tokens while its neighbours sat near 97. Greedy bin-packing behaving exactly as greedy bin-packing does. Not fixable in the merger; fixable only by splitting finer upstream.

## The ceiling bug

First working merge run produced chunks of 109 and 102 tokens against a `chunk_size` of 100. After a flush the buffer resets to the last `overlap` tokens, *then* the piece is appended — so the real bound is `overlap + max_piece_size`, and `max_piece_size` is `chunk_size`, because that's what the splitter was told to enforce.

Fix is one line: split at `chunk_size - overlap`, merge at `chunk_size`. Max piece 90, plus 10 carry-back = 100. Ceiling holds.

General shape worth remembering: **when two phases each enforce the same limit independently, the composition doesn't.** The budgets have to be derived from each other, not copied.

## Three bugs worth not repeating

- **Module-level `chunks = []` inside a recursive function.** The list was shared across every call; the recursive branch did `chunks.extend(recursive_call(...))` where the inner call had already appended to that same list and returned it — so it extended the list with itself. Compounds exponentially. Locals only in recursive functions.
- **Missing final flush.** Buffer-and-flush loops silently drop the tail. No error, just a missing last chunk.
- **Look-ahead merge (`chunks[i+1]`).** Wrong shape entirely — needed indexing, mutation-during-iteration, and an end special-case. Buffer-accumulate-and-flush needs none of that. When a loop wants to peek forward, it usually wants to accumulate instead.

## Wiring the retrieval test

Reused Day 5's `vector_store.py` untouched. The only glue needed was a small adapter mapping the chunker's output to what `upsert` expects — `text` → `content`, everything else into a `metadata` blob. That adapter is the one piece of test code that survives into production; it lives inside `ingest.py` there.

Two things worth carrying forward:

- All three variants go into **one table**, separated at query time by a metadata filter on `strategy`. IDs get assigned by enumerating over the *combined* list — per-variant numbering would collide on the integer PK and silently overwrite via `on_conflict_do_update`. Same pattern as multi-tenant filtering.
- `upsert` takes a list, not a string, so 28 chunks cost **one** embedding request and one transaction instead of 28 of each. Embedding calls are the latency and cost bottleneck; batching at the interface is the reason that matters.

## What the retrieval numbers actually said

recursive@50 got the right chunk at rank 1 on all five queries and the top score on four. Fixed and recursive@100 each failed one. But the failures are more interesting than the scoreboard.

**The overlap artifact isn't cosmetic — it caused a wrong answer.** rec_100's top hit for "how do you improve the taste of chicken" was a chunk starting with the fragment `" taste."`, left behind when the token-level carry-back sliced *"Marinating chicken improves tenderness and taste."* in half. Three occurrences of "taste", zero answer. The actual answer was in the previous chunk at rank 2.

That flips this from a style note to a real bug: the fragment worked as a keyword magnet with none of the meaning attached, and in production it hands the LLM context that can't answer the question. Piece-level carry-back is now a justified fix rather than a nice-to-have — and it turns out that's what LangChain and LlamaIndex do anyway.

**Small chunks score higher because big chunks dilute.** An embedding is one 1536-dim vector for the *whole* chunk, so a relevant sentence among eight irrelevant ones lands near the centroid of all nine rather than near itself. Same migrations sentence scored 0.611 in a 5-sentence chunk and 0.468 buried in a 9-sentence one. Nothing changed but the neighbours.

**Fixed chunking pulled the wrong topic entirely.** Asked about FastAPI auth, its rank 1 was the *Django* auth chunk — matched on a shared word while the OAuth2/JWT answer sat at rank 2. Fixed slicing had merged the tail of one paragraph with the head of the next, so the embedding straddled both topics.

## Note for the threshold work

The next day's task adds a similarity threshold so the agent refuses when retrieval is weak. These numbers make the case for thresholding on the **gap between rank 1 and rank 2**, not the absolute score: a 0.4 cutoff would have refused a correct answer at 0.319 while happily accepting an answerless chunk at 0.494. Absolute scores drift with chunk size; the gap is steadier.

## Still open

Piece-level carry-back (deferred, now justified). Chunk size needs re-tuning against the real corpus — 50/10 is tuned to a deliberately adversarial test document with six unrelated topics crammed into 570 tokens; real support docs are more coherent and will likely favour bigger chunks. Both of this run's failures were ranking problems rather than missing-data problems, which is exactly what reranking and hybrid search are for — post-deploy, measured against this same eval set.