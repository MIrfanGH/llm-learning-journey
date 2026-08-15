import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent / "day05_vector_db"))


from fixed_chunker import fixed_size_chunker
from recursive_chunker import recursive_chunker, ENCODING

from vector_store import VectorStore
from database import sessionLocal





session = sessionLocal()  # create a database session for the vector store to use

with open("day06_chunking/sample.txt", 'r', encoding="utf-8") as f:
    text = f.read()


def to_upsert_row(chunk, doc_id):  # In production this adaptor lives inside ingest.py. 
                                   # What dies is the test file around it, not the function.
    """ 
    since chunker's output keys and upsert's expected keys don't match
    this adapter maps the chunker's output to the upsert's expected keys here 
    """
    
    return {
        "id": doc_id,
        "content": chunk['text'],
        "metadata":{
            "source": chunk['source'],
            "chunk_index": chunk['chunk_index'],
            "strategy": chunk['strategy'],
        }
    }


# get the chunks using different strategies
fixed_100 = fixed_size_chunker(text, source="sample.txt", chunk_size=100, overlap=10)
rec_100 = recursive_chunker(text, source="sample.txt", separator=["\n\n", "\n", ". ", " ", ""], chunk_size=100, overlap=10)
rec_50 = recursive_chunker(text, source="sample.txt", separator=["\n\n", "\n", ". ", " ", ""], chunk_size=50, overlap=10)

# add a strategy key to each chunk dict to separate the strategies when storing in the vector store for comparison
for c in fixed_100: c['strategy'] = "fixed"
for c in rec_100: c['strategy'] = "recursive_100"
for c in rec_50: c['strategy'] = "recursive_50"


# combine all the chunks into a single list so we can assing global ids to each chunk while storing them in the vector store
combined_list = fixed_100 + rec_100 + rec_50
dict_rows = [to_upsert_row(chunk, doc_id) for doc_id, chunk in enumerate(combined_list, 1)]   
# we called the adapter here to map the chunker's output to the upsert's expected keys and assign a global id to each chunk 

vs = VectorStore(session)
vs.delete(filters={"source": "day4"})   # one-time cleanup of day4's embeddings
vs.delete(filters={"source": "sample.txt"})  # one-time cleanup of previous runs of this test file, so we can re-run the test without duplicates
print(vs.upsert(dict_rows))  # store all the chunks in the vector store for comparison, batch embedding


QUERIES = [
"How does Django keep the database schema in sync?",
"What is used for authentication in FastAPI?",
"What makes a cricket bowler effective?",
"Which Python feature helps with memory efficiency?",
"How do you improve the taste of chicken?",
]

for q in QUERIES:
    print(f"\n=== {q} ===")
    for strat in ["fixed", "recursive_100", "recursive_50"]:
        print(f"\n-- {strat} --")
        for r in vs.search(q, top_k=3, filters={"strategy": strat}):
            print(f"  {r['score']:.3f}  {r['content'][:250]}")