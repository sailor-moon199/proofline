"""Read text from source documents while preserving source positions."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass(frozen=True)
class SourceChunk:
    """A text slice with source identity and a stable location range."""

    document: str
    chunk_index: int
    heading: str | None
    start_line: int
    end_line: int
    start_char: int
    end_char: int
    text: str


def read_document_text(path: str | Path) -> tuple[str, list[str]]:
    """Read plain text from supported source formats.

    The returned text is the normalized source text, and the second value is a list of
    lines so downstream code can report citations by line number.
    """
    path_obj = Path(path)
    suffix = path_obj.suffix.lower()
    if suffix == ".txt":
        text = path_obj.read_text(encoding="utf-8", errors="replace")
        return text, text.splitlines()

    if suffix == ".docx":
        try:
            from docx import Document
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional dependency
            raise RuntimeError("python-docx is required to read .docx files.") from exc
        document = Document(str(path_obj))
        paragraphs = [paragraph.text for paragraph in document.paragraphs]
        text = "\n".join(paragraphs)
        return text, text.splitlines()

    if suffix == ".pdf":
        try:
            import pdfplumber
        except ModuleNotFoundError as exc:  # pragma: no cover - depends on optional dependency
            raise RuntimeError("pdfplumber is required to read .pdf files.") from exc
        pages: list[str] = []
        with pdfplumber.open(str(path_obj)) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text() or ""
                pages.append(extracted)
        text = "\n".join(pages)
        return text, text.splitlines()

    raise ValueError(f"Unsupported document type for {path_obj!s}: {suffix!r}")


def chunk_text_by_heading(
    text: str,
    *,
    document: str,
    max_chars: int = 1800,
) -> list[SourceChunk]:
    """Split text into chunks that preserve line and character offsets.

    Headings are detected using Markdown-like headings (#, ##, ###) when present.
    Otherwise the function falls back to character-based chunking.
    """
    lines = text.splitlines()
    if not lines:
        return []

    heading_ranges: list[tuple[int, int, str | None]] = []
    current_start = 0
    current_heading: str | None = None
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("#") and stripped.replace("#", "").strip():
            if current_start != index:
                heading_ranges.append((current_start, index, current_heading))
            current_heading = stripped
            current_start = index
        elif not stripped:
            continue
    heading_ranges.append((current_start, len(lines), current_heading))

    if len(heading_ranges) > 1:
        chunks: list[SourceChunk] = []
        for chunk_index, (start_idx, end_idx, heading) in enumerate(heading_ranges):
            if start_idx >= end_idx:
                continue
            chunk_lines = lines[start_idx:end_idx]
            chunk_text = "\n".join(chunk_lines).strip()
            if not chunk_text:
                continue
            offset_start = sum(len(line) + 1 for line in lines[:start_idx])
            offset_end = offset_start + len(chunk_text)
            chunks.append(
                SourceChunk(
                    document=document,
                    chunk_index=chunk_index,
                    heading=heading,
                    start_line=start_idx + 1,
                    end_line=end_idx,
                    start_char=offset_start,
                    end_char=offset_end,
                    text=chunk_text,
                )
            )
        if chunks:
            return chunks

    chunks: list[SourceChunk] = []
    current_lines: list[str] = []
    current_start_line = 1
    char_offset = 0
    index = 0
    for line_no, line in enumerate(lines, start=1):
        if not line.strip() and not current_lines:
            char_offset += len(line) + 1
            continue
        current_lines.append(line)
        char_offset += len(line) + 1
        if sum(len(part) + 1 for part in current_lines) > max_chars:
            chunk_text = "\n".join(current_lines[:-1]).strip()
            if chunk_text:
                chunks.append(
                    SourceChunk(
                        document=document,
                        chunk_index=index,
                        heading=None,
                        start_line=current_start_line,
                        end_line=line_no - 1,
                        start_char=max(0, char_offset - sum(len(part) + 1 for part in current_lines)),
                        end_char=max(0, char_offset - len(current_lines[-1]) - 1),
                        text=chunk_text,
                    )
                )
                index += 1
            current_lines = [line]
            current_start_line = line_no
    if current_lines:
        chunk_text = "\n".join(current_lines).strip()
        if chunk_text:
            chunks.append(
                SourceChunk(
                    document=document,
                    chunk_index=index,
                    heading=None,
                    start_line=current_start_line,
                    end_line=len(lines),
                    start_char=0,
                    end_char=len(text),
                    text=chunk_text,
                )
            )
    return chunks or [
        SourceChunk(
            document=document,
            chunk_index=0,
            heading=None,
            start_line=1,
            end_line=len(lines),
            start_char=0,
            end_char=len(text),
            text=text.strip(),
        )
    ]


def ingest_document(path: str | Path, *, max_chars: int = 1800) -> list[SourceChunk]:
    """Read and chunk a document while preserving the source text and locations."""
    document_text, _ = read_document_text(path)
    return chunk_text_by_heading(document_text, document=str(Path(path).name), max_chars=max_chars)
