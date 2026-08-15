import tiktoken


ENCODING = tiktoken.get_encoding("cl100k_base")

def fixed_size_chunker(text, source, chunk_size=100, overlap=10):
    """
    Splits the input text into fixed-size chunks with optional overlap.

    Args:
        text (str): The input text to be chunked.
        chunk_size (int): The size of each chunk in tokens.
        overlap (int): The number of tokens to overlap between chunks. Default is 0.

    Returns:
        list: A list of token chunks.
    """

    # Safety check: overlap must be smaller than chunk_size
    assert overlap < chunk_size, "Overlap must be smaller than chunk_size"

    tokens = ENCODING.encode(text)
    chunks = []
    start = 0

    while start < len(tokens):
        end = start + chunk_size
        chunk_token = tokens[start:end]
        chunk_text = ENCODING.decode(chunk_token)

        chunks.append({
            "text": chunk_text,
            "strategy": "fixed",
            "source":source,
            "chunk_index": len(chunks) # using chunks instead of chunk_token cause we want the index of the chunk, not the token
        })

        # Move start
        start += chunk_size - overlap 

    return chunks

