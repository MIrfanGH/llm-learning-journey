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