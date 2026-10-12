"""Document chunker splitting extracted text with overlap and metadata tracking."""

import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    """Represents a discrete text chunk with indexing metadata."""

    chunk_index: int
    content: str
    token_count: int
    vector_id: str


class DocumentChunker:
    """Splits document text into overlapping segments respecting paragraph and sentence boundaries."""

    def __init__(
        self,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_text(
        self,
        text: str,
        document_id: int,
        user_id: int,
    ) -> list[TextChunk]:
        """Split text into structured chunks with consistent vector IDs."""
        cleaned_text = self._clean_text(text)
        if not cleaned_text:
            return []

        # If text is small, return as single chunk
        if len(cleaned_text) <= self.chunk_size:
            tokens = len(cleaned_text.split())
            vector_id = f"user_{user_id}_doc_{document_id}_chunk_0"
            return [
                TextChunk(
                    chunk_index=0,
                    content=cleaned_text,
                    token_count=tokens,
                    vector_id=vector_id,
                )
            ]

        # Split along paragraph or sentence boundaries
        chunks: list[TextChunk] = []
        start = 0
        chunk_index = 0
        text_len = len(cleaned_text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)

            # If not at the end of text, attempt to find a natural sentence/newline break
            if end < text_len:
                # Look for paragraph break (\n\n) or sentence period (. ) within last 100 chars of window
                window = cleaned_text[start:end]
                last_para = window.rfind("\n\n")
                last_period = window.rfind(". ")
                last_newline = window.rfind("\n")

                if last_para != -1 and last_para > len(window) - 150:
                    end = start + last_para + 2
                elif last_period != -1 and last_period > len(window) - 150:
                    end = start + last_period + 2
                elif last_newline != -1 and last_newline > len(window) - 100:
                    end = start + last_newline + 1

            chunk_content = cleaned_text[start:end].strip()
            if chunk_content:
                tokens = len(chunk_content.split())
                vector_id = f"user_{user_id}_doc_{document_id}_chunk_{chunk_index}"
                chunks.append(
                    TextChunk(
                        chunk_index=chunk_index,
                        content=chunk_content,
                        token_count=tokens,
                        vector_id=vector_id,
                    )
                )
                chunk_index += 1

            # Advance by step size (chunk_size - overlap)
            step = max(1, self.chunk_size - self.chunk_overlap)
            start += step

        return chunks

    def _clean_text(self, text: str) -> str:
        """Normalize line breaks and collapse excessive whitespace."""
        if not text:
            return ""
        # Normalize carriage returns
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse excessive whitespace within lines
        text = re.sub(r"[ \t]+", " ", text)
        # Collapse more than two consecutive newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()
