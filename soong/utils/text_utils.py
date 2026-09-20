"""Lyrics cleaning and normalisation, plus YouTube metadata tidying.

These helpers pull in no heavy dependency, which keeps them testable in
isolation and cheap to import.
"""

from __future__ import annotations

import re
import unicodedata

_SECTION_RE = re.compile(r"^\s*[\[(].*?[\])]\s*$")
_GENIUS_HEADER_RE = re.compile(
    r".*?(Lyrics|Paroles de la chanson)\s*", re.IGNORECASE | re.DOTALL
)
_MULTISPACE_RE = re.compile(r"[ \t]+")


def strip_genius_artifacts(text: str) -> str:
    """Remove the usual clutter of a Genius lyrics page.

    Drops the "N ContributorsXxx Lyrics" banner, the trailing "Embed" counter
    and the bracketed section lines, which are not sung and would otherwise
    throw the forced alignment off.
    """
    if not text:
        return ""

    header = _GENIUS_HEADER_RE.match(text)
    if header and header.end() < len(text):
        text = text[header.end() :]

    text = re.sub(r"\d*Embed\s*$", "", text)
    text = re.sub(r"You might also like", "", text)

    lines = [line for line in text.splitlines() if not _SECTION_RE.match(line)]
    return "\n".join(lines).strip()


def normalize_lines(text: str) -> list[str]:
    """Split a text into non empty lines with normalised spacing.

    This is the canonical representation consumed by the forced aligner and the
    subtitle builder: one line is one verse.
    """
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        cleaned = _MULTISPACE_RE.sub(" ", raw).strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def flatten_for_alignment(text: str) -> str:
    """Flatten a text into a single space separated line for the aligner.

    The CTC aligner works on a stream of words. The line structure is kept
    elsewhere, through `normalize_lines`, to rebuild the verses afterwards.
    """
    return " ".join(normalize_lines(text))


def tokenize_words(text: str) -> list[str]:
    """Split a string into words, the unit of alignment."""
    return [word for word in re.split(r"\s+", text.strip()) if word]


def strip_accents(text: str) -> str:
    """Lowercase, accent free version of a string, for lenient comparisons."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def slugify(text: str, *, max_len: int = 80) -> str:
    """Turn a track name into a filesystem safe identifier."""
    slug = re.sub(r"[^a-z0-9]+", "-", strip_accents(text)).strip("-")
    return (slug[:max_len] or "track").strip("-")


def normalized_tokens(text: str) -> list[str]:
    """Lowercase tokens without accents or punctuation, for fuzzy matching."""
    cleaned = re.sub(r"[^a-z0-9]+", " ", strip_accents(text))
    return [token for token in cleaned.split() if token]


_YT_NOISE_TERMS = (
    r"clips?\s*officiels?",
    r"clips?\s*officielles?",
    r"official\s*music\s*video",
    r"official\s*video",
    r"official\s*audio",
    r"official\s*lyrics?\s*video",
    r"official\s*visuali[sz]er",
    r"official\s*music",
    r"lyrics?\s*video",
    r"music\s*video",
    r"clip\s*vid[eé]o",
    r"vid[eé]o\s*oficial",
    r"video\s*officiel",
    r"videoclip",
    r"visuali[sz]er",
    r"lyrics?",
    r"paroles?",
    r"audio",
    r"video",
    r"m/?v",
    r"hd",
    r"hq",
    r"full\s*hd",
    r"4k",
    r"8k",
    r"remaster(?:ed)?",
    r"explicit",
    r"prod\.?\s*by[^)\]|]*",
)
_YT_NOISE_RE = re.compile(
    r"(?<![\w])(?:" + "|".join(_YT_NOISE_TERMS) + r")(?![\w])", re.IGNORECASE
)
_DASHES = "\u2013\u2014"
_BULLETS = "\u2022\u00b7"
_TRAILING_NOISE_RE = re.compile(
    rf"[\s\-|{_DASHES}{_BULLETS}]*(?:" + "|".join(_YT_NOISE_TERMS) + r")\s*$",
    re.IGNORECASE,
)
_SEGMENT_SEPARATORS = rf"\s*[|{_BULLETS}]\s*"
_EDGE_CHARACTERS = " -|" + _DASHES + _BULLETS


def _is_noise_segment(segment: str) -> bool:
    """True when a segment carries promotional terms and nothing else."""
    inner = strip_accents(segment).strip()
    if not inner:
        return True
    residue = _YT_NOISE_RE.sub("", inner)
    return re.sub(r"[^a-z0-9]+", "", residue) == ""


def clean_youtube_title(title: str) -> str:
    """Strip the promotional noise out of a YouTube title.

    For instance "Le Keur - Vital (Clip Officiel) | HD" becomes
    "Le Keur - Vital", before the artist and title are separated. Parenthesised
    or bracketed groups made only of promotional terms are removed, as are the
    promotional segments after a pipe and any bare promotional suffix.
    """
    if not title:
        return ""

    def replace_if_noise(match: "re.Match[str]") -> str:
        return "" if _is_noise_segment(match.group(1)) else match.group(0)

    cleaned = re.sub(r"\(([^()]*)\)", replace_if_noise, title)
    cleaned = re.sub(r"\[([^\[\]]*)\]", replace_if_noise, cleaned)

    head, *tail = re.split(_SEGMENT_SEPARATORS, cleaned)
    cleaned = " ".join([head, *[s for s in tail if not _is_noise_segment(s)]])

    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = _TRAILING_NOISE_RE.sub("", cleaned).strip()

    return _MULTISPACE_RE.sub(" ", cleaned).strip(_EDGE_CHARACTERS)


def clean_artist_name(artist: str) -> str:
    """Clean an artist name taken from a YouTube channel or title."""
    if not artist:
        return ""
    cleaned = re.sub(r"\s*vevo\s*$", "", artist, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*topic\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bofficial\b", "", cleaned, flags=re.IGNORECASE)
    return _MULTISPACE_RE.sub(" ", cleaned).strip(_EDGE_CHARACTERS)
