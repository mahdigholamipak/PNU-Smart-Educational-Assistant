from pathlib import Path

from pypdf import PdfReader


def extract_text_from_pdf(file_path: str | Path) -> str:
    """Extract raw text from a PDF file."""
    reader = PdfReader(str(file_path))
    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)
    return "\n\n".join(pages)


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


def process_pdf(file_path: str | Path) -> list[str]:
    """Extract and chunk a PDF file into RAG-ready document chunks."""
    text = extract_text_from_pdf(file_path)
    return chunk_text(text)