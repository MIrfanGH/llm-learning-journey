
# Day 5 builds the storage + retrieval layer


# CORE FLOW

Document
   ↓
Generate embedding
   ↓
Store in PostgreSQL (pgvector)
   ↓
User asks question
   ↓
Generate query embedding
   ↓
Similarity search
   ↓
Return top matching chunks


# High-Level Code Flow
1. Generate embeddings (Day 4)
2. Connect to PostgreSQL
3. Create documents table with vector column
4. Insert text + embedding + metadata
5. Embed user query
6. Search nearest vectors
7. Return top-k chunks


# Combined Flow  (This is the core of vector search/RAG retrieval)
User Question
   ↓
Create Query Embedding
   ↓
Apply Metadata Filters
   ↓
Cosine distance against all document embeddings
   ↓
Find Top-K Nearest Neighbors (Sort by nearest)
   ↓
Return Best Chunks(top K documents)


# My Python to DB flow
Your Python code
    ↓
SQLAlchemy (ORM) + pgvector python package (adds Vector type)
    ↓
psycopg2 (driver - sends SQL over the wire)
    ↓
PostgreSQL (database) + pgvector extension (adds vector operations)


## Day 5 — Decision Log: 


*upsert strategy*

**What I did first:** Loop over chunks, SELECT-by-id to check existence, then
insert-or-update each one individually. 

```python
         for chunk, embedding in zip(chunks, doc_embeddings):
         existing = self.session.query(Document).filter(Document.id == chunk.get("id")).first()  
```

**Why it was wrong:** 
The N+1 Vector Bottleneck: Created an unnecessary N+1 query loop forcing 1 network round-trip per chunk. Invisible with a few test sentences, but scales linearly to 2,000+ blocking database queries for a single standard PDF ingestion.
Financial Waste: Unchecked loops risk re-embedding unchanged text chunks, leaking unnecessary OpenAI API costs.
Concurrency Vulnerability: Lacked atomicity, leaving the ingestion pipeline open to data-corrupting race conditions if multiple async workers targeted the same document simultaneously.

**What I changed to:** 
Switched to a native PostgreSQL batch approach using SQLAlchemy's INSERT ... ON CONFLICT DO UPDATE. 
This compresses the entire payload evaluation down to a single atomic database statement, 
wiping out network latency and ensuring race-condition safety.

**Open question (Day 6):** caller-supplied integer IDs won't survive re-ingestion.
Need deterministic IDs (hash of source+chunk_index).


## Local DB (Docker)
docker start pgvector-db
Connect: postgresql+psycopg2://llm_user:***@localhost:5433/llm_journey
Shell:   docker exec -it pgvector-db psql -U llm_user -d llm_journey

Rebuild from zero:
docker rm -f pgvector-db && docker volume rm pgvector_data
docker run -d --name pgvector-db -e POSTGRES_USER=llm_user \
  -e POSTGRES_PASSWORD=... -e POSTGRES_DB=llm_journey \
  -p 5433:5432 -v pgvector_data:/var/lib/postgresql/data \
  pgvector/pgvector:pg17


  # Why UPSERT ?
  With plain INSERT, run #2 gives you 50 more rows — now retrieval returns the same chunk three times and your context window fills with duplicates. With DELETE ALL + INSERT, you have a window where the table is empty and you're re-paying OpenAI for every embedding.
Upsert = "make the DB match this input, whatever state it's currently in." Run it once or ten times, same result. That's idempotency