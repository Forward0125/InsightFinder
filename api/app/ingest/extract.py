"""HTML -> clean text.

SEC filings come as iXBRL HTML: lots of inline XBRL tags
(``<ix:nonNumeric>``, ``<ix:nonFraction>``), heavy inline styling, and
embedded scripts. We strip that noise and pull plain text with
block-level newline separation.

Hidden iXBRL data lives in two main places we need to drop:
  1. ``<ix:hidden>`` — the standard hidden-fact container
  2. ``<div style="display:none">`` near the top with raw data points

Anything else flagged as hidden (``[hidden]`` attr, CSS
``visibility:hidden``) is also dropped to avoid leaking metadata into
chunks.
"""

from __future__ import annotations

import re
from pathlib import Path

from selectolax.parser import HTMLParser


# Tags whose contents are noise -- decompose entirely.
NOISE_TAGS = ("script", "style", "noscript", "head", "meta", "link")

# iXBRL containers that hide their contents from rendering. Selectolax's
# CSS engine doesn't reliably match the namespaced selector, so we walk
# all nodes and check tag name directly.
IXBRL_HIDDEN_TAGS = {"ix:hidden", "ix:references", "ix:resources"}

# Inline-style substrings indicating the element should not render.
HIDDEN_STYLE_PATTERNS = (
    "display:none",
    "display: none",
    "visibility:hidden",
    "visibility: hidden",
)


def _strip_hidden(tree: HTMLParser) -> None:
    """Remove iXBRL hidden tags and elements with hidden inline styles."""
    # Drop iXBRL namespaced hidden containers.
    for node in tree.css("*"):
        if node.tag in IXBRL_HIDDEN_TAGS:
            node.decompose()

    # Drop CSS-hidden elements (style="display:none" etc.).
    for node in tree.css("[style]"):
        style = (node.attributes.get("style") or "").lower()
        if any(p in style for p in HIDDEN_STYLE_PATTERNS):
            node.decompose()

    # Drop elements with the bare HTML `hidden` attribute.
    for node in tree.css("[hidden]"):
        node.decompose()


def extract_text(html: str) -> str:
    """Return readable plain text from an SEC filing's HTML.

    Block-level boundaries become newlines so the chunker can split on
    paragraph breaks.
    """
    tree = HTMLParser(html)

    for sel in NOISE_TAGS:
        for node in tree.css(sel):
            node.decompose()

    _strip_hidden(tree)

    body = tree.body or tree.root
    raw = body.text(separator="\n", deep=True, strip=False) if body else ""

    # Normalize whitespace.
    raw = re.sub(r"[ \t\xa0]+", " ", raw)            # NBSPs included
    raw = re.sub(r" *\n *", "\n", raw)
    raw = re.sub(r"\n{3,}", "\n\n", raw)
    return raw.strip()


def extract_file(path: Path) -> str:
    """Read an .htm file and return its extracted text."""
    return extract_text(path.read_text(encoding="utf-8", errors="replace"))
