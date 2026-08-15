import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from day05_vector_db.embeddings import get_embeddings
from day05_vector_db.vector_store import VectorStore
from day05_vector_db.database import sessionLocal
from day06_chunking.recursive_chunker import recursive_chunker 



DATA_PATH = pathlib.Path(__file__).parent.parent / "data" / "sample.txt"  # Path to the sentences file

with open(DATA_PATH, "r") as f:
    texts = f.read() # contains the sample data as it is without splitting them in sentences


SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

chunks = recursive_chunker(
    text = texts,
    source = str(DATA_PATH),
    separator = SEPARATORS,
    chunk_size=50,
    overlap=10,
    ) 

# since upsert() expects 'content' but chunker outputs text so mapping to avoid KeyError
rows = [
    {
    "content": c["text"], 
    "source": c["source"], 
    "chunk_index": c["chunk_index"], 
    "metadata": {
        "strategy": c["strategy"]}}
    for c in chunks
]


session = sessionLocal()
store = VectorStore(session)
result = store.upsert(rows)
print("chunks upserted , successfully! ") 