"""Text cleaning helpers for niche extraction."""

from __future__ import annotations

import html
import re
import unicodedata

from bs4 import BeautifulSoup

_MIN_TEXT_LENGTH = 20


def clean_text(text: str) -> str:
    """Strip markup and return normalized plain text."""
    if not text:
        return ""

    cleaned = unicodedata.normalize("NFKC", text)
    cleaned = re.sub(r"```.*?```", " ", cleaned, flags=re.S)
    cleaned = re.sub(r"`[^`]*`", " ", cleaned)
    cleaned = re.sub(r"https?://\S+|www\.\S+", " ", cleaned)
    cleaned = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = BeautifulSoup(cleaned, "html.parser").get_text(" ")
    cleaned = html.unescape(cleaned).lower()
    cleaned = re.sub(r"[*_#>~]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) >= _MIN_TEXT_LENGTH else ""
