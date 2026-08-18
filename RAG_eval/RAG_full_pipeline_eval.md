
*We want to answer:*
> Given a query, does my RAG retrieve the right information and 
> Does the LLM produce an answer grounded in that information?


# RAG Evaluation & Debugging (VALIDATE)

Ran a 12-question eval set end-to-end through the pipeline — `Query → Vector Search →
Context Building → Generate → Validate → Respond` — covering direct single-chunk
questions, multi-chunk synthesis, a near-miss keyword trap, two fabricated-link traps,
out-of-scope questions, and one adversarial question (pgvector/HNSW) that never appears
in the corpus. Corpus: `sample.txt` (Python, Django, FastAPI, Cricket, Cooking,
Astronomy) and `sample_pdf.pdf` (production API architecture — caching, Celery, auth,
observability, failure scenarios). Context window set to 1000 tokens for this baseline.
The goal wasn't just to confirm the happy path — it was to find out *where* failures
actually trace to when they happen: retrieval, generation, or validation.

## The traps held

The two questions this eval existed to stress-test both passed. "How does FastAPI use
Redis for caching?" and "Does Django use Celery for background jobs?" each retrieve
chunks that share surface keywords but where the corpus never actually connects the two
concepts — both were correctly refused instead of the model stitching together a
plausible-sounding but fabricated relationship. The adversarial question, on pgvector's
HNSW index, was also refused cleanly, despite being a topic directly relevant to this
project and almost certainly present in the model's own training data — the clearest
evidence yet that "answer using ONLY the context" holds under real pressure, not just on
easy questions. The near-miss trap (FastAPI auth) correctly cited only `sample.txt`'s
OAuth2/JWT line, without pulling in the PDF's separate, unrelated JWT section — real
topical discrimination, not keyword matching.

## Bug 1 — placeholder text leaking into refusals

Refusal responses were inconsistently returning `"answer": "..."` instead of real text —
some refusals got a proper sentence, others just three dots, with no obvious pattern.
Traced it back to `main.py`'s system prompt, which included a literal JSON example
(`{"answer": "...", "grounded": true/false, ...}`) meant as a format template. At
`temperature=0.0`, when the model had nothing grounded to say, the lowest-friction
completion was to echo the ellipsis straight out of the example rather than generate an
actual refusal sentence. Fixed by replacing the placeholder with a descriptive
instruction instead of a literal value. Verified directly against `/ask` before and
after the fix — refusals now consistently return real reasoning, e.g. "The context is
insufficient to provide information on how FastAPI uses Redis for caching."

## Bug 2 — Windows paths breaking JSON escaping

A second issue showed up after the first fix: intermittent `\u0005` corruption inside
`sources_used`, moving to a different entry on each run rather than always the same one.
FastAPI's logs confirmed the mechanism — `Invalid JSON: Unterminated string`, triggering
the retry loop. Root cause: `context.py` labeled each chunk with the full Windows
absolute path, and the prompt then asked the model to copy that path verbatim. Backslash
is JSON's escape character, so reproducing a raw Windows path inside a JSON string is a
genuinely hard generation task — the model sometimes broke the JSON outright, and while
self-correcting on retry, sometimes produced a malformed unicode escape instead of a
clean one. Fixed by switching the label to `Path(chunk['source']).name`, so the model
only ever sees and copies a bare filename. Re-ran the full eval afterward — the artifact
did not recur across any of the 12 questions, and as a side benefit, local machine paths
no longer leak into user-facing citations.

## Open — `sources_used` format is inconsistent

Citations still come back in three different shapes across responses — bare filename,
`"filename | Page: N"`, and the full bracketed label. Not breaking validation, but not
clean enough to trust for a real citation UI yet. Needs either a tighter prompt
instruction or deterministic post-processing before it's product-quality. Not a Day 3
blocker.

## Q5 — root-caused, not just retested

"What makes a good fast bowler vs a spinner in cricket?" passed cleanly twice, then
came back as a refusal on a later run with no code change that should have affected it.
Rather than treating that as noise, isolated it stage by stage:

- **Retrieval** — dumped raw `vs.search()` output directly. The correct chunk (containing
  both the fast-bowler and spinner sentences) ranked #1 with a clear score gap over
  everything else (0.566 vs 0.375 next-best).
- **Context construction** — dumped `build_context()`'s actual output. The full sentence
  pair was present, intact, and well under the token budget — not truncated, not
  mangled.

Both stages checked out clean, so the failure isolates to generation itself. Two
contributing factors: OpenAI's `temperature=0.0` doesn't guarantee full run-to-run
determinism, and — more usefully — the question asks what makes a bowler *good*, while
the retrieved context only describes *technique* (pace/swing, turn/flight) without
explicitly framing it as a quality marker. Answering requires a small inferential leap
the model made inconsistently across runs — sometimes willing to infer "technique
described = answer," sometimes treating the literal absence of the word "good" as
insufficient grounding. This is a generation-layer grounding-consistency issue specific
to evaluative-framing questions — Q1-Q4's purely descriptive questions never showed it.
No pipeline fix belongs here: retrieval is proven correct, so reaching for reranking or
hybrid search would be solving a problem that doesn't exist. If this pattern recurs on
other evaluative questions during Day 7's larger eval pass, the right lever is
tightening the prompt's definition of "grounded," not the architecture.

## Status

Both bugs fixed and confirmed not to recur across a full re-run. Q5 was fully
root-caused rather than just retested away, isolating the issue to generation rather
than retrieval. That's a documented finding, not an open bug. **Day 3 closed.**

## Key lesson

Q5 looked like a retrieval problem on the surface — wrong answer, no sources cited —
and the instinct might have been to reach straight for reranking or hybrid search.
Checking each pipeline stage independently first, before touching generation logic,
proved it wasn't retrieval at all. A RAG system can fail in a way that points at the
wrong fix if you don't isolate which stage actually broke first.