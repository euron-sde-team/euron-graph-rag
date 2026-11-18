"""Entity name normalization: the one definition of "the same name" for the whole system.

`entity_key` is what makes extraction from many documents converge on one row per entity,
what duplicate resolution compares and what local search matches against a question.
"""

from __future__ import annotations

import re
import unicodedata

# Words that never distinguish one entity from another.
TITLES = frozenset({"dr", "prof", "professor", "mr", "ms", "mrs", "sir", "mx"})
CORPORATE_SUFFIXES = frozenset(
    {
        "inc",
        "incorporated",
        "corp",
        "corporation",
        "ltd",
        "limited",
        "llc",
        "plc",
        "gmbh",
        "co",
        "company",
        "ag",
        "sa",
    }
)
_POSSESSIVE = re.compile(r"['\N{RIGHT SINGLE QUOTATION MARK}]s\b")
_PUNCT = re.compile(r"[^a-z0-9&\s-]")
_SPACE = re.compile(r"\s+")


def fold(text: str) -> str:
    """Lowercase ASCII with accents removed."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()


def name_tokens(name: str) -> list[str]:
    """The distinguishing tokens of a name, in order."""
    text = _POSSESSIVE.sub("", fold(name)).replace(".", " ")
    text = _SPACE.sub(" ", _PUNCT.sub(" ", text)).strip()
    tokens = [t for t in text.split(" ") if t]
    while tokens and tokens[0] in TITLES:
        tokens = tokens[1:]
    while tokens and tokens[-1] in CORPORATE_SUFFIXES and len(tokens) > 1:
        tokens = tokens[:-1]
    if tokens and tokens[0] == "the" and len(tokens) > 1:
        tokens = tokens[1:]
    return tokens


def entity_key(name: str) -> str:
    """The identity of an entity within a project."""
    return " ".join(name_tokens(name))[:300]


def display_name(name: str) -> str:
    """A name as shown: titles and possessives dropped, spacing fixed."""
    text = _POSSESSIVE.sub("", name.strip())
    parts = text.split()
    while parts and fold(parts[0]).rstrip(".") in TITLES and len(parts) > 1:
        parts = parts[1:]
    while len(parts) > 1 and fold(parts[-1]).rstrip(".") in CORPORATE_SUFFIXES:
        parts = parts[:-1]
    return _SPACE.sub(" ", " ".join(parts)).strip(" ,;:")[:300]


def acronym(name: str) -> str:
    """Initials of a multi-word name ("helios robotics institute" -> "hri")."""
    tokens = [t for t in name_tokens(name) if t not in {"of", "the", "and", "for", "de", "&"}]
    return "".join(t[0] for t in tokens) if len(tokens) > 1 else ""
