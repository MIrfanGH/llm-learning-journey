import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))

from RAG_full_pipeline.doc_extractor import pdf_extractor
from day06_chunking.recursive_chunker import recursive_chunker
from day05_vector_db.database import sessionLocal
from day05_vector_db.vector_store import VectorStore

SEPARATORS = ["\n\n", "\n", ". ", " ", ""]


def doc_ingestion():

    doc_path = pathlib.Path(__file__).parent.parent / "data" / "sample_pdf.pdf"
    pages = pdf_extractor(str(doc_path)) # a list of dictionaries, where each dict representing one page

    all_chunks = [] # will hold every chunk from every page, flattened into one list.
    runnign_index = 0
    
    for page in pages:
        if not page["text"].strip():
            continue # skip blank/image-only pages

        # Calling recursive chunker once per page 
        page_chunks = recursive_chunker(
            text=page["text"],
            source=str(doc_path),
            separator=SEPARATORS,
            chunk_size=50,
            overlap=10,
        )


        for c in page_chunks:
            # Overwrites the chunker's local (per-page) chunk_index with the running global counter, 
            # so every chunk in the whole document has a unique index — no collisions across pages. 
            # Also stamps which page this chunk came from — new metadata
            c["chunk_index"] = runnign_index
            c["page"] = page["page"]
            runnign_index += 1 # 

        all_chunks.extend(page_chunks)

    # Row mapping : chunker's "text" -> DB's "content"
    # "page" now rides inside metadata (JSONB) alongside "strategy"
    rows = [
        {
        "content": c["text"],
        "source": c["source"],
        "chunk_index": c["chunk_index"],
        "metadata": {"strategy": c["strategy"], "page": c["page"]},
        }
        for c in all_chunks
    ]


    session = sessionLocal()
    vs = VectorStore(session)

    result  = vs.upsert(rows)
    print("upserted : ", result)

doc_ingestion()