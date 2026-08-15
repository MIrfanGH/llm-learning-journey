from recursive_chunker import ENCODING, recursive_chunker
import pathlib

DATA_PATH = pathlib.Path(__file__).parent.parent / "data" / "sample.txt"  # Path to the sentences file

with open(DATA_PATH, 'r', encoding="utf-8") as f:
    text = f.read()

# dict_chunks = fixed_size_chunker(text, source="sample.txt")

# for i, chunk in enumerate(dict_chunks, 1):
#     print(f"------Chunk------") 
#     print(f"source: {chunk['source']}"),
#     print(f"strategty: {chunk['strategy']}")
#     print(f"chunk_index: {i}")
#     tokens = ENCODING.encode(chunk['text'])
#     print(f"token_count: {len(tokens)}")
#     print(f"text:\n{chunk['text']}\n")


SEPARATORS = ["\n\n", "\n", ". ", " ", ""]

text_chunks = recursive_chunker(text, source="sample.txt", separator=SEPARATORS, chunk_size=50, overlap=10) 
# will return a list of dicts with the text chunks, their source, strategy, and chunk_index

for i, chunk in enumerate(text_chunks, 1):
    print(f"------Chunk{i}------")
    print(f"source: {chunk['source']}")
    print(f"strategy: {chunk['strategy']}")
    print(f"chun_index: {i}")
    print(f"token_count: {len(ENCODING.encode(chunk['text']))}")
    print(f"text:\n {chunk['text']}\n")