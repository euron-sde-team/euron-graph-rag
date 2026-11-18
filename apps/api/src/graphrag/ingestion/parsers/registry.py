from __future__ import annotations

from collections.abc import Callable

from graphrag.ingestion.parsers.docx import parse_docx
from graphrag.ingestion.parsers.pdf import parse_pdf
from graphrag.ingestion.parsers.tables import parse_csv
from graphrag.ingestion.parsers.text import parse_html, parse_markdown, parse_txt
from graphrag.ingestion.types import ParsedDocument, ParseLimits
from graphrag.models.enums import DocumentKind

Parser = Callable[[bytes, ParseLimits], ParsedDocument]

PARSERS: dict[DocumentKind, Parser] = {
    DocumentKind.PDF: parse_pdf,
    DocumentKind.DOCX: parse_docx,
    DocumentKind.MD: parse_markdown,
    DocumentKind.HTML: parse_html,
    DocumentKind.TXT: parse_txt,
    DocumentKind.CSV: parse_csv,
}


def parse(kind: DocumentKind, data: bytes, limits: ParseLimits) -> ParsedDocument:
    return PARSERS[kind](data, limits)
