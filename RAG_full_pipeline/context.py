import tiktoken
from pathlib import Path


ENCODING = tiktoken.get_encoding("cl100k_base")


def build_context(chunks: list[dict], max_token: int = 1000) -> str:

    """
    Build and return the context that is to be passed to the LLM
    """

    pieces = []
    current_tokens = 0

    for chunk in chunks:
        label = f"[Source: {Path(chunk['source']).name} | Page: {chunk['metadata'].get('page', '?')}]"
        # Path(...).name strips the full path down to just the filename (e.g. "sample.txt"
        # instead of "c:\Users\801MI\Desktop\LLM-Journey\data\sample.txt"). 
        # Two reasons:
        # 1) backslashes in the full Windows path are JSON's escape character — asking the
        #    model to reproduce them exactly caused inconsistent, malformed JSON output
        # 2) local machine paths shouldn't leak into a user-facing "sources_used" citation anyway.

        labeled_piece = f"label : {label}\n{chunk['content']}"

        piece_length = len(ENCODING.encode(labeled_piece))
        if current_tokens + piece_length > max_token:
            break
        pieces.append(labeled_piece)
        current_tokens += piece_length


    return "\n\n--\n\n".join(pieces)
        
