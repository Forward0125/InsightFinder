"""Text -> chunks.

Two-pass design:

1. *Pre-split* every paragraph so none individually exceeds
   ``target_tokens``. Big paragraphs are first split on sentence
   boundaries; if even a single sentence is still too large
   (a giant data table, for instance), it's chopped into raw
   token windows.

2. *Greedy pack* paragraphs sequentially until adding the next would
   exceed ``target_tokens``. Save chunk, start the next chunk by
   re-including the last few paragraphs (``overlap_tokens`` worth) so
   information at chunk boundaries isn't lost from retrieval.

Tokens are counted with ``cl100k_base`` (OpenAI's tokenizer for
text-embedding-3-small / GPT-3.5 / GPT-4).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import tiktoken


_encoder = tiktoken.get_encoding("cl100k_base")

# Sentence boundary -- ., !, ? followed by whitespace, but NOT after a
# common abbreviation. Conservative regex that's good enough for filings.
_SENT_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z(\"'\[])")


@dataclass
class Chunk:
    text: str
    token_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


# ─── Helpers ─────────────────────────────────────────────────────


def _count_tokens(text: str) -> int:
    return len(_encoder.encode(text))


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_oversized(paragraph: str, max_tokens: int) -> list[str]:
    """Break a paragraph into pieces no larger than max_tokens.

    Try sentence-level first; fall back to token windowing for
    pathological cases (e.g. a comma-separated wall of numbers).
    """
    if _count_tokens(paragraph) <= max_tokens:
        return [paragraph]

    # Sentence-level packing.
    sentences = _SENT_BOUNDARY.split(paragraph)
    if len(sentences) > 1:
        out: list[str] = []
        buf: list[str] = []
        buf_tokens = 0
        for sent in sentences:
            s_tok = _count_tokens(sent)
            if s_tok > max_tokens:
                # Flush whatever we have so we don't merge giant sentences.
                if buf:
                    out.append(" ".join(buf))
                    buf, buf_tokens = [], 0
                # Recurse via token windowing for this single huge "sentence".
                out.extend(_split_by_tokens(sent, max_tokens))
                continue
            if buf_tokens + s_tok > max_tokens and buf:
                out.append(" ".join(buf))
                buf, buf_tokens = [], 0
            buf.append(sent)
            buf_tokens += s_tok
        if buf:
            out.append(" ".join(buf))
        return out

    # Single very long "sentence" -- chop by token windows.
    return _split_by_tokens(paragraph, max_tokens)


def _split_by_tokens(text: str, max_tokens: int) -> list[str]:
    """Cut text into max_tokens-sized pieces by raw token slicing."""
    ids = _encoder.encode(text)
    if len(ids) <= max_tokens:
        return [text]
    return [
        _encoder.decode(ids[i:i + max_tokens])
        for i in range(0, len(ids), max_tokens)
    ]


# ─── Public API ──────────────────────────────────────────────────


def chunk_text(
    text: str,
    *,
    target_tokens: int = 500,
    overlap_tokens: int = 50,
) -> list[Chunk]:
    """Return chunks of approximately ``target_tokens`` each."""
    raw_paragraphs = _split_paragraphs(text)
    if not raw_paragraphs:
        return []

    # Pass 1: ensure no paragraph is bigger than the target.
    paragraphs: list[str] = []
    for p in raw_paragraphs:
        paragraphs.extend(_split_oversized(p, target_tokens))

    para_tokens = [_count_tokens(p) for p in paragraphs]

    # Pass 2: greedy pack with trailing-paragraph overlap.
    chunks: list[Chunk] = []
    i = 0
    n = len(paragraphs)

    while i < n:
        j = i
        chunk_tokens = 0
        while j < n and (chunk_tokens + para_tokens[j] <= target_tokens or j == i):
            chunk_tokens += para_tokens[j]
            j += 1

        chunks.append(Chunk(
            text="\n\n".join(paragraphs[i:j]),
            token_count=chunk_tokens,
        ))

        if j >= n:
            break

        # Overlap: walk back from j to find the smallest start index
        # whose tail tokens fit in overlap_tokens.
        next_i = j
        overlap = 0
        for k in range(j - 1, i, -1):
            if overlap + para_tokens[k] > overlap_tokens:
                break
            overlap += para_tokens[k]
            next_i = k

        # Always advance by at least one paragraph.
        i = max(next_i, i + 1)

    return chunks
