import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from fastapi import FastAPI
from pydantic import BaseModel, Field

from day05_vector_db.database import sessionLocal
from day05_vector_db.vector_store import VectorStore
from RAG_full_pipeline.context import build_context
from day03_validation_with_retry.day3_validation import call_llm_with_retry
from dotenv import load_dotenv


load_dotenv()

app = FastAPI()

session = sessionLocal()
vs = VectorStore(session)


class RAGAnswerValidation(BaseModel):
     answer: str = Field(min_length=1, max_length=1000)
     grounded : bool = Field(description="True only if the context actually supports the answer")
     sources_used : list[str] = Field(default_factory=list)


class AskRequest(BaseModel):
     query : str


SYSTEM_PROMPT = """Answer the user's question using ONLY the context below.
                        If the context is insufficient, say so — do not use outside knowledge.

                        For "sources_used" copy the exact text after "[Source: " for each context block you relied on - 
                        do not paraphrase or invent source names. 

                        Respond with this exact JSON, nothing else:
                        {{"answer": "...", "grounded": true/false, "sources_used": ["..."]}}

                        Context:
                        {context}
                        """
 

@app.post("/ask")
async def ask_query(user_query: AskRequest):
    
    top_k = vs.search(user_query.query)
    context = build_context(top_k)

    system_prompt = SYSTEM_PROMPT.format(context=context)

    result = call_llm_with_retry(
         system_prompt = system_prompt,
         user_message = user_query.query,
         schema= RAGAnswerValidation,
    )

    return result

