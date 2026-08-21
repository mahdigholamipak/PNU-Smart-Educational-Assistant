import logging
from pathlib import Path

import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_pages_from_pdf(file_path: str | Path) -> list[dict]:
    """Extract per-page text from a PDF file using PyMuPDF (fitz).

    PyMuPDF handles RTL (Persian/Arabic) text, complex layouts, and Unicode
    shaping natively, so the extracted text reads correctly without any manual
    reshaper/bidi post-processing. Returns a list of ``{"page": int, "text": str}``
    dicts for pages that contain extractable text. Page numbers are 1-based.
    """
    file_path_str = str(file_path)
    pages: list[dict] = []

    try:
        doc = fitz.open(file_path_str)
    except Exception as exc:
        logger.warning("Failed to open PDF %s: %s", file_path_str, exc)
        return pages

    try:
        for idx, page in enumerate(doc.pages(), start=1):
            text = page.get_text("text") or ""
            if text.strip():
                pages.append({"page": idx, "text": text})
    finally:
        doc.close()

    return pages


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Split text into overlapping chunks by character count at word boundaries."""
    if not text.strip():
        return []

    words = text.split()
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for word in words:
        word_len = len(word) + 1  # +1 for space
        if current_len + word_len > chunk_size and current:
            chunks.append(" ".join(current))
            # Keep overlap words from the tail of the current chunk
            overlap_words: list[str] = []
            overlap_len = 0
            for w in reversed(current):
                if overlap_len + len(w) + 1 > overlap:
                    break
                overlap_words.insert(0, w)
                overlap_len += len(w) + 1
            current = overlap_words
            current_len = overlap_len

        current.append(word)
        current_len += word_len

    if current:
        chunks.append(" ".join(current))

    return chunks


def process_pdf(file_path: str | Path) -> list[dict]:
    """Extract and chunk a PDF file into RAG-ready document chunks.

    Returns a list of ``{"content": str, "page": int}`` dicts. Chunking is
    performed within each page so every chunk records the page it came from,
    enabling accurate page-level citations in the UI.
    """
    pages = extract_pages_from_pdf(file_path)
    chunks: list[dict] = []
    for page in pages:
        for piece in chunk_text(page["text"]):
            chunks.append({"content": piece, "page": page["page"]})
    return chunks