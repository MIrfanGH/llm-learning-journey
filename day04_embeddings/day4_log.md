# Day 4 Log — Embeddings: Semantic Search Without a Database

*Goal*
    Turn sentences into vectors using OpenAI's embedding API, then find semantically similar sentences using cosine similarity.
    No vector DB yet — just raw numpy math. 
    This is the foundation of the RETRIEVE step in the pipeline.



## Setup

- Model: `text-embedding-3-small` (1536 dimensions, cheapest OpenAI option)
- Corpus: 50 sentences across 6 categories (Python, Django, FastAPI, Cricket, Cooking, Space)
- Categories chosen deliberately — so I can visually verify that embeddings cluster by topic.
- All sentences embedded in one batch API call (not a loop — same instinct as Django's `bulk_create`).



## Code Structure

day04_embeddings.py
├── load_sentences()       — reads sentences.txt, strips blanks
├── get_embedding(query)   — embeds a single user query
├── embedding_docs()       — batch-embeds all 50 sentences (one API call)
├── cosine_similarity()    — np.dot / (norm * norm)
├── search(query, top_k=5) — embed query → compare all → sort → return top_k
└── main()                 — embed once, then search loop


## Query Results & Analysis


***************************Query 1************************************

```
Query: "what are generators?"

1. Score: 0.6028  —  Generators allow lazy evaluation and efficient memory usage.
2. Score: 0.2263  —  Stars are massive spheres of hot glowing gas.
3. Score: 0.2112  —  Spinners use turn and flight to deceive the batter.
4. Score: 0.1941  —  Decorators modify the behavior of functions without changing their code.
5. Score: 0.1794  —  FastAPI automatically generates OpenAPI documentation.
```

# What I noticed:

# 1. The score gap is the signal, not the absolute number.
    Result #1 is at 0.60, result #2 drops to 0.22. That 0.38 gap means the model is confident only one sentence is truly relevant. The rest is noise.
    For Project 1: I'll need a minimum similarity threshold (maybe 0.35) to filter out garbage results instead of always returning top_k blindly.

# 2. Result #2 is garbage but harmless.
    "Stars are massive spheres of hot glowing gas" has nothing to do with Python generators. Score of 0.22 confirms it's noise. The ranking is correct — irrelevant results exist but they're scored low enough to filter out.

# 3. Result #4 makes partial sense.
    "Decorators modify the behavior of functions" — decorators and generators are both Python concepts. The embedding caught the topic proximity even though they're different features. This is semantic similarity working as intended.



***************************Query 2************************************


Query: "explain what is python?"

1. Score: 0.5471  —  Python is a versatile programming language used for web development and automation.
2. Score: 0.4532  —  Python supports object-oriented programming with classes and inheritance.
3. Score: 0.4277  —  Django is a high-level Python web framework.
4. Score: 0.3591  —  Python functions help organize reusable blocks of code.
5. Score: 0.3562  —  The Django ORM allows database queries using Python code.


# What I noticed:

# 1. All 5 results are genuinely relevant.
    Every result mentions Python or is Python-related (Django IS Python). No cricket or cooking sentences leaked in. The embedding model correctly clusters by domain.

# 2. Score spread is tighter than Query 1.
    Range is 0.54 to 0.35 (gap of ~0.19) vs Query 1's 0.60 to 0.17 (gap of ~0.43). This makes sense — "what is python" is a broad query that legitimately relates to multiple sentences. "what are generators" is narrow and specific.
    Takeaway: broad queries return more relevant results with tighter scores. Narrow queries return fewer with bigger gaps.

# 3. Django appearing in Python results is correct behavior.
    The model understands Django is a Python framework — it didn't just keyword-match "Python," it understood the semantic relationship. This is exactly why embeddings beat keyword search.



## Key Takeaways for production

# 1. Similarity threshold > blind top_k.
    Returning top 5 always means returning noise when only 1 result is relevant. In Production, I'll add: 
    if score < threshold: skip. 
    This prevents feeding irrelevant context to the LLM (which causes hallucination).

# 2. Cosine similarity can't catch semantic opposites.
    "The server is running" and "The server is not running" would score high because embedding models capture topic, not negation. This is why reranking and validation exist — embeddings find candidates, downstream steps verify quality.

# 3. You can't mix embedding models.
    If I embed docs with model A and query with model B, vectors are incompatible (different dimensions, different vector spaces). Pick one model and stick with it across the entire pipeline. Switching means re-embedding everything.

# 4. pgvector is neede to automate it.
    Today's `search()` function loops through all 50 vectors and compares one by one. That's O(n) — fine for 50, unusable for 50,000.
    pgvector does the same similarity math, but uses special indexes to make searching fast even with huge datasets.


Day 3 gave me the output side (validate + retry). Day 4 gives me the input side (find relevant context). Day 7 wires them together: search() → context → call_llm_with_retry() → validated answer.