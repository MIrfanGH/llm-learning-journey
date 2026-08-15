import tiktoken


ENCODING = tiktoken.get_encoding("cl100k_base")


def build_context(chunks: list[dict], max_token: int = 500) -> str:

    """
    Build and return the context that is to be passed to the LLM
    """

    pieces = []
    current_tokens = 0

    for chunk in chunks:
        label = f"[Source : {chunk['source']} | Page: {chunk['metadata'].get('page', '?')}]"
        labeled_piece = f"label : {label}\n{chunk['content']}"

        piece_length = len(ENCODING.encode(labeled_piece))
        if current_tokens + piece_length > max_token:
            break
        pieces.append(labeled_piece)
        current_tokens += piece_length


    return "\n\n--\n\n".join(pieces)
        
