# LLM Learning Journey

Backend Engineer → AI Engineer transition. 19-day hands-on schedule.



## THE PIPELINE I'M FOLLOWING FOR LEARNING:


User asks a question
    ↓
[1] CLASSIFY — Is this a knowledge question, a tool action, or general chat?
                             ↓                      ↓                    ↓
[2]                 RETRIEVE from docs        [3] CALL a tool          Just answer
                    (embeddings, vectors,        (API call, calculator,
                    chunking, reranking)         web search)
    ↓                              ↓
[4] BUILD CONTEXT — Combine retrieved info + conversation history + instructions
    ↓
[5] GENERATE — Send to LLM, get structured response
    ↓
[6] VALIDATE — Does the output match the schema? Is it sane?
    ↓ (no)                    ↓ (yes)
[7] RETRY with error ──→  [8] RESPOND to user



##           ================== Day 1: LLM Fundamentals ==================

**What I built:** CLI chat app with conversation history and token tracking.

**Key concepts:**
- LLMs are stateless — "memory" is just resending the full message list
- Tokens = smallest unit of text LLM processes to understand and genrate response,  1 token ~ 3-5 char on average
    Prompt tokens grew per turn: 33 → 99 → 156 → 181 → 229 cause i gave the input + reponse appended list each time
- Temperature=0 for deterministic output, higher for creativity
- System/User/Assistant roles structure every API call

**Stack:** Python, OpenAI SDK, gpt-4o-mini

--------------------------------------------------------------------------------------------------------------------------


##                    ================== Day 2: Classifier =================

**What I built:**  A classifier that takes user query and labels it into one of : RAG | TOOL | GENERAL

**Key concepts:**
- Prompt Techniques...(zero-shot, few-shot,  Chain-of-Thought(CoT))
- System Prompt Design
- Structured Output generation

**Why this matters:** 
We need to label the query and route it based on intent, so the LLM knows exactly what to do next — call a tool, retrieve from docs, or just answer casually. 
We're not letting the model guess the next step; we're controlling its behaviour and the route.

**Today Result:**
 I ran 31 queries and got 96.7% accuracy, 
 Also i found some prompt-level issues (noted in day2_log.md)

**Stack:** Python, OpenAI SDK, gpt-4o-mini


--------------------------------------------------------------------------------------------------------------------------

##                    ================== Day 3: Validation + Retry =================

**What I built:** A retry wrapper around Day 2's classifier. 
                 Uses Pydantic to validate the LLM's response. If validation fails, 
                 the error is fed back to the LLM and it tries again(taking the error as context).

**Flow**

validation_and_retry(query, ResponseModel)
        ↓
    LLM → raw string
        ↓
    json.loads(raw) → dict
        ↓
    ResponseModel.model_validate(dict)
        ↓
    Valid → return object
    Invalid → format error → append to messages → retry
        ↓
    Still failing after N attempts → raise exception


**Why this matters:**
LLMs occasionally return malformed JSON, miss fields, or violate constraints. In production we can't crash on every bad response — we need a safety net(feeding the LLM previous response/error then retry ). 

**Key concepts:**
- model_validate() raises ValidationError, doesn't return True/False — must use try/except
- The error message itself is the teaching signal. Feeding it back to the LLM lets it self-correct.
- Schema validation catches structural bugs (wrong type, missing field, out of range), NOT semantic bugs(wrong answer with valid format). Evals handle that — coming on Day 8 and Day 15.

**Today Result:**
With normal constraints, retry never fired as — gpt-4o-mini rarely breaks JSON format at temperature=0.0 so, forced retry by tightening the schema (confidence must equal 0.95). 
Then watched the LLM read the error message and fix exactly that field on the next attempt. 
Confirmed the retry path isn't dead code, then reverted the schema. Full notes in day3_log.md.

**Stack:** Python, OpenAI SDK, Pydantic v2, gpt-4o-mini



--------------------------------------------------------------------------------------------------------------------------

##          ================== Day 4: Embeddings, Semantic Search, and Cosine Similarity   =================

**What I built:** A semantic search engine over 50 sentences using OpenAI embeddings and cosine similarity. 
                  No vector DB — used just raw numpy math

**Flow**
50 sentences → batch embed (one API call) → 50 vectors (1536 dims each)                                               ↓
user query → embed query → cosine similarity against all 50 → sort → top_k results

**Why this matters:**
Keyword search fails when users say "cancel my account" but the doc says "account termination." Embeddings capture meaning, not exact words — so semantically similar text clusters together regardless of phrasing. This is how the RETRIEVE step finds relevant context to feed the LLM.
Key concepts:

**Key concepts:**
Embeddings = fixed-length float arrays representing semantic meaning
Cosine similarity measures direction (topic match), not magnitude (doc length)
Batch the API call — embed 50 sentences in one call, not 50 calls for 1 sentence
The score gap between results matters more than absolute scores
Broad queries → tight score spread, many relevant results. Narrow queries → big gap, fewer relevant results.

**Today Result:**
"what are generators?" → top result scored 0.60, next dropped to 0.22 (clear signal, one relevant match).
"explain what is python?" → top 5 all Python-related, scores 0.54–0.35 (broad query, multiple valid matches).
No cross-domain bleeding — cricket didn't leak into Python queries. 
Full analysis in day4_log.md.

**Stack:** Python, OpenAI SDK, numpy, text-embedding-3-small

--------------------------------------------------------------------------------------------------------------------------

##          ================== Day 5: Vector Database — pgvector Storage & Retrieval  =================

**What I built:** `VectorStore` class (upsert / search / delete) — a PostgreSQL + pgvector storage and retrieval layer that replaces Day 4's raw-numpy similarity search with a persistent, indexed DB.

**Flow**
Document chunks
    ↓
Generate embeddings
    ↓
PostgreSQL + pgvector
    ↓
User query → query embedding
    ↓
Cosine similarity search
    ↓
Top-K matching chunks

**Why this matters:**
Turns Day 4's in-memory numpy search into a persistent retrieval layer the RAG pipeline can actually reuse — pgvector adds durable storage and an HNSW index for approximate-nearest-neighbor search, and lets me reuse SQLAlchemy/ORM skills already built from Django instead of learning a new vector-DB API from scratch.

**Key concepts:**
- `Vector` column type (pgvector-sqlalchemy) + HNSW index with `vector_cosine_ops` — must match the distance operator used at query time or it fails silently with plausible-looking wrong results
- Upsert via `INSERT ... ON CONFLICT DO UPDATE` — one atomic, race-condition-safe statement instead of per-row read-then-write
- Batch embedding calls, not one API call per row
- Idempotent re-ingestion keys off a composite `UniqueConstraint(source, chunk_index)` as the natural key — not a hashed ID; the row's own integer PK stays plain auto-increment

**Today Result:**
First upsert implementation looped per chunk, doing a `SELECT`-by-id existence check before every insert — an N+1 query bottleneck invisible at 5 test sentences but linear-scaling to 2,000+ blocking round-trips on a real PDF, plus wasted OpenAI spend re-embedding unchanged chunks. Replaced with a single batched `ON CONFLICT DO UPDATE` statement — one round-trip, atomic, idempotent by construction. Full decision log in `day05_vector_db/day05VecotrDB_log.md`.

**Stack:** Python, SQLAlchemy, psycopg2, PostgreSQL + pgvector (Docker), OpenAI embeddings

--------------------------------------------------------------------------------------------------------------------------

##          ================== Day 6: Chunking Strategies  =================

**What I built:** Two chunkers from scratch (no LangChain) — fixed-size (token-based) and recursive (separator hierarchy + greedy merge with overlap), both returning plain chunk dicts that feed the existing ingestion and vector-store layers unchanged. Embedded all variants into the Day 5 pgvector store and measured retrieval quality against 5 adversarial queries on a 6-topic test corpus.

**Flow**
Document text
    ↓
Split-down — walk separator hierarchy (`\n\n` → `\n` → `. ` → ` ` → `""`), recurse into any piece still over budget → enforces a **ceiling**
    ↓
Merge-up — greedily pack pieces back up to `chunk_size`, carry back `overlap` tokens on each flush → enforces a **floor**
    ↓
Embedding → pgvector → retrieval comparison

**Why this matters:**
Chunk quality is a retrieval-quality ceiling — poor boundaries fragment an answer or mix unrelated topics, and a perfect vector search can't fix a chunk that's missing the sentence that answers the question. This is the RETRIEVE step's input quality, upstream of everything else in the pipeline.

**Key concepts:**
- Recursive chunking is two phases solving opposite problems, not one algorithm — split alone produces sentence-starved chunks (75% of budget wasted); merge alone has nothing to pack
- Two phases can't independently enforce the same size limit — split at `chunk_size - overlap`, merge at `chunk_size`, or the composed ceiling silently breaks
- Token-level overlap carry-back can sever a sentence mid-word, creating a keyword-matching chunk with no actual answer in it — found by measurement, not inspection
- Smaller chunks score higher on retrieval due to embedding dilution — one relevant sentence among eight irrelevant ones drags the whole chunk's vector toward the centroid
- Threshold refusal (next sprint) should key off the score **gap** between rank 1/2, not an absolute cutoff — absolute scores drift with chunk size

**Today Result:**
recursive@50 (10-token overlap) got the correct chunk at rank 1 on 5/5 test queries, top score on 4/5. Fixed-size chunking pulled the wrong topic entirely on a FastAPI-auth query (matched "Django" auth on shared vocabulary). recursive@100's overlap artifact produced a false rank-1 — a chunk starting with the severed fragment `" taste."` outranked the chunk that actually contained the answer. Full writeup with score tables in `day06_chunking/chunking_comparison.md`, build/debug notes in `day06_chunking/day06_log.md`.

**Stack:** Python, tiktoken, OpenAI embeddings, pgvector (HNSW, `vector_cosine_ops`)

--------------------------------------------------------------------------------------------------------------------------

##          ================== Day 7: End-to-End RAG Pipeline (`/ask`)  =================

**What I built:** First fully wired RAG slice — `POST /ask` FastAPI endpoint: retrieve → build context → generate → validate → respond. Generalized Day 3's retry wrapper (`call_llm_with_retry`) to accept any Pydantic schema so the classifier and RAG generation share one retry/validate loop instead of duplicating it. Tested against both a single-topic `.txt` corpus and a real multi-section PDF.

**Flow**
User query
    ↓
Vector search (`VectorStore.search()`) → top-k chunks
    ↓
Build context (`build_context()`) → token-budgeted, source-labeled string
    ↓
LLM generation
    ↓
Pydantic validation + retry (`call_llm_with_retry`)
    ↓
Response (`answer`, `grounded`, `sources_used`)

**Why this matters:**
This connects every individually-tested retrieval component into one real request path — Steps [2]+[4]+[5]+[6]+[8] wired together for the first time into something that answers a real question end-to-end, not separate pieces tested in isolation.

**Key concepts:**
- `build_context()` labels each chunk with its real document `source` (not chunking-strategy metadata) and enforces a token budget via a running `tiktoken` count — stop adding chunks, don't skip ahead, since chunks arrive rank-ordered
- Context construction must preserve document provenance (source, page) — retrieved metadata should be carried through, never invented by the LLM
- `grounded` is the LLM self-reporting whether its own answer is supported by the context — a free first-pass signal for refusal logic, not a verified faithfulness guarantee
- Reusable retry function: `schema` as a parameter (`type[BaseModel]`), not hardcoded — classifier and RAG answering are now two callers of one loop
- PDF ingestion needs a global `chunk_index` reassigned after per-page chunking — the chunker's own index resets to 0 every call, which collides with the `(source, chunk_index)` unique constraint across page boundaries

**Today Result:**
`sources_used` initially came back as the chunking-strategy tag (`"merged"`) or model-paraphrased fragments instead of real document paths — root cause was `build_context()` reading the wrong metadata field; fixed by switching to the already-existing `source` column and tightening the prompt to copy it verbatim. On PDF ingestion, traced an incomplete-but-accurate answer to a Redis-caching question back to raw `search()` output before concluding anything: the correct supporting chunk simply wasn't in top-k, outranked by an off-topic chunk sharing surface keywords — confirms Day 6's chunk-size/dilution finding concretely, on a real document, and is a known limitation deferred to post-deploy reranking, not fixed today. Full findings in `RAG_full_pipeline/log.md`.

**Stack:** Python, FastAPI, PyMuPDF, tiktoken, OpenAI SDK, Pydantic v2, pgvector



##          ================== Day 8: Lightweight RAG Evaluation  =================

**What I built:** A 12-question eval harness (`eval_runner.py` + `eval_questions.json`) run against the live `/ask` endpoint — covering direct questions, multi-chunk synthesis, a near-miss keyword trap, two fabricated-link traps, out-of-scope questions, and one adversarial question outside the corpus entirely. Logs raw responses to `eval_response.jsonl` alongside expected grounding/source metadata for manual review.

**Flow**
Questions (`eval_questions.json`)
    ↓
POST /ask for each question
    ↓
Merge question metadata + actual response
    ↓
Append as one JSON line → `eval_response.jsonl`
    ↓
Manual review against expected grounding/source

**Why this matters:**
Pydantic validation (Day 3) only confirms the output is structurally well-formed — right types, right fields. It says nothing about whether the answer is actually correct or genuinely grounded in the retrieved context. Eval is what tests the pipeline's real behavior, especially on adversarial cases designed to induce hallucination — this closes the VALIDATE step at a system level, not just a schema level.

**Key concepts:**
- Fabricated-link traps (two unrelated concepts sharing retrieval keywords, e.g. "FastAPI + Redis") and adversarial questions (topics outside the corpus the model likely knows from training) specifically test for hallucination beyond simple correctness
- Literal example values inside a system prompt aren't inert — a placeholder like `"answer": "..."` gets treated by the model as content to reproduce under low-signal conditions, not as a schema to fill
- Full absolute file paths break JSON generation — backslash is JSON's escape character, so asking the model to reproduce a Windows path verbatim causes intermittent malformed output; label chunks with `Path(chunk['source']).name` instead
- A refusal (`grounded: false`) isn't automatically a retrieval bug — isolate stage by stage (raw retrieval output → raw context output → generation) before assuming where a failure actually lives
- Incremental, one-row-at-a-time writes need JSON Lines (`.jsonl`), not a single JSON array — a mid-run crash still leaves prior rows readable

**Today Result:**
12/12 correct grounding classifications, with two real bugs found and fixed along the way: a prompt placeholder leaking `"..."` into refusal answers, and Windows paths breaking JSON escaping in `sources_used`. One question (fast bowler vs. spinner) intermittently refused despite the answer being retrieved at rank 1 with an intact context — traced stage by stage to a generation-layer grounding-consistency issue on evaluative-framing questions, not a retrieval or code bug. Full findings in `RAG_eval/RAG_full_pipeline_eval.md`.

**Stack:** Python, FastAPI, requests, OpenAI SDK, Pydantic v2, pgvector