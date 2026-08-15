import pymupdf
import pathlib

def pdf_extractor(doc_path: str) -> list[dict] :

    """Returns [{'page': page_num, 'text': text}, ...], 1-indexed pages."""

    path = pathlib.Path(doc_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    doc = pymupdf.open(doc_path)
    pages = [{"page": i, "text": page.get_text()} for i, page in enumerate(doc, start=1)]
    doc.close()
    return pages

