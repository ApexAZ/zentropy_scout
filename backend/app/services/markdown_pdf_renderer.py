"""Markdown-to-PDF renderer using markdown-it-py and ReportLab.

REQ-025 §5.2, §5.5: Parses markdown into AST tokens via markdown-it-py,
then maps tokens to ReportLab Platypus flowables for PDF generation.

Public API:
- render_pdf(markdown_content: str) -> bytes
"""

import io
from html import escape as _html_escape
from urllib.parse import urlparse
from xml.sax.saxutils import (
    escape as _xml_escape,  # nosec B406 — output escaping, not XML parsing
)

from markdown_it import MarkdownIt
from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

# =============================================================================
# Constants
# =============================================================================

_MARGIN_SIDE = 0.75 * inch
_MARGIN_TOP = 0.5 * inch
_MARGIN_BOTTOM = 0.5 * inch

_LINK_COLOR_HEX = "#0000EE"

_SAFE_URL_SCHEMES = frozenset({"http", "https", "mailto"})

_MAX_MARKDOWN_LENGTH = 100_000  # ~100KB, sufficient for a resume

# =============================================================================
# Styles (REQ-025 §5.5)
# =============================================================================


def _build_styles() -> dict[str, ParagraphStyle]:
    """Build paragraph styles matching REQ-025 §5.5 feature mapping."""
    base = getSampleStyleSheet()

    return {
        "heading_1": ParagraphStyle(
            "MdH1",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            alignment=TA_CENTER,
            spaceBefore=0,
            spaceAfter=6,
        ),
        "heading_2": ParagraphStyle(
            "MdH2",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            alignment=TA_LEFT,
            spaceBefore=8,
            spaceAfter=4,
        ),
        "heading_3": ParagraphStyle(
            "MdH3",
            parent=base["Heading3"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            spaceBefore=6,
            spaceAfter=3,
        ),
        "heading_4": ParagraphStyle(
            "MdH4",
            parent=base["Heading4"],
            fontName="Helvetica-Bold",
            fontSize=10,
            leading=13,
            alignment=TA_LEFT,
            spaceBefore=4,
            spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "MdBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            spaceAfter=4,
        ),
        "bullet": ParagraphStyle(
            "MdBullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            leftIndent=18,
            bulletIndent=6,
            spaceAfter=2,
        ),
        "ordered": ParagraphStyle(
            "MdOrdered",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            leftIndent=18,
            bulletIndent=6,
            spaceAfter=2,
        ),
        "blockquote": ParagraphStyle(
            "MdBlockquote",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=12,
            leftIndent=18,
            spaceAfter=4,
            textColor=HexColor("#555555"),
        ),
        "code": ParagraphStyle(
            "MdCode",
            parent=base["Normal"],
            fontName="Courier",
            fontSize=8,
            leading=10,
            leftIndent=12,
            spaceAfter=4,
        ),
    }


# =============================================================================
# Inline Token → XML Markup Conversion
# =============================================================================


def _is_safe_url(url: str) -> bool:
    """Check if a URL uses a safe protocol.

    Blocks javascript:, data:, and other dangerous schemes.

    Args:
        url: URL string to validate.

    Returns:
        True if the URL scheme is safe for linking.
    """
    if not url:
        return False
    # Allow fragment-only URLs (anchor links)
    if url.startswith("#"):
        return True
    parsed = urlparse(url)
    return parsed.scheme in _SAFE_URL_SCHEMES


def _render_link_open_tag(token) -> str:
    """Render a link_open token as ReportLab XML markup.

    Args:
        token: A markdown-it link_open token.

    Returns:
        Opening tag(s) for the link.
    """
    href = token.attrGet("href") or ""
    if _is_safe_url(href):
        href_escaped = _html_escape(href, quote=True)
        return f'<a href="{href_escaped}" color="{_LINK_COLOR_HEX}"><u>'
    return "<u>"


def _render_inline_tokens(tokens: list) -> str:
    """Convert inline markdown-it tokens to ReportLab XML markup.

    Handles: text, bold, italic, links, code_inline, softbreak.

    Args:
        tokens: List of inline child tokens from markdown-it.

    Returns:
        XML string suitable for ReportLab Paragraph.
    """
    parts: list[str] = []
    for token in tokens:
        if token.type == "text":
            parts.append(_xml_escape(token.content))
        elif token.type == "code_inline":
            parts.append(f"<font face='Courier'>{_xml_escape(token.content)}</font>")
        elif token.type == "strong_open":
            parts.append("<b>")
        elif token.type == "strong_close":
            parts.append("</b>")
        elif token.type == "em_open":
            parts.append("<i>")
        elif token.type == "em_close":
            parts.append("</i>")
        elif token.type == "link_open":
            parts.append(_render_link_open_tag(token))
        elif token.type == "link_close":
            parts.append(
                "</u></a>"
            )  # Works for both safe (has <a>) and unsafe (just </u>)
        elif token.type in ("softbreak", "hardbreak"):
            parts.append("<br/>")
    return "".join(parts)


def _extract_inline_text(token) -> str:
    """Extract inline markup from a token that has children.

    Args:
        token: A markdown-it token (typically inline type).

    Returns:
        XML string for ReportLab Paragraph.
    """
    if token.children:
        return _render_inline_tokens(token.children)
    return _xml_escape(token.content) if token.content else ""


# =============================================================================
# Block Token Handlers
# =============================================================================


def _handle_heading_pdf(
    tokens: list,
    i: int,
    styles: dict[str, ParagraphStyle],
) -> tuple[int, list] | None:
    """Handle a heading_open token: create heading paragraph."""
    if i + 1 >= len(tokens) or tokens[i + 1].type != "inline":
        return None
    level = int(tokens[i].tag[1])
    style_key = f"heading_{min(level, 4)}"
    text = _extract_inline_text(tokens[i + 1])
    return i + 3, [Paragraph(text, styles[style_key])]


def _handle_paragraph_pdf(
    tokens: list,
    i: int,
    styles: dict[str, ParagraphStyle],
) -> tuple[int, list] | None:
    """Handle a paragraph_open token: create body paragraph."""
    if i + 1 >= len(tokens) or tokens[i + 1].type != "inline":
        return None
    text = _extract_inline_text(tokens[i + 1])
    return i + 3, [Paragraph(text, styles["body"])]


def _handle_list_item_pdf(
    tokens: list,
    i: int,
    styles: dict[str, ParagraphStyle],
    ordered_counter: list[int],
) -> tuple[int, list]:
    """Handle a list_item_open token: create bullet or numbered paragraph(s)."""
    is_ordered = _is_inside_ordered_list(tokens, i)
    if is_ordered:
        ordered_counter[0] += 1
    result_flowables: list = []
    j = i + 1
    while j < len(tokens) and tokens[j].type != "list_item_close":
        if tokens[j].type == "inline":
            text = _extract_inline_text(tokens[j])
            if is_ordered:
                result_flowables.append(
                    Paragraph(
                        text,
                        styles["ordered"],
                        bulletText=f"{ordered_counter[0]}.",
                    )
                )
            else:
                result_flowables.append(
                    Paragraph(text, styles["bullet"], bulletText="\u2022")
                )
        j += 1
    return j + 1, result_flowables


def _handle_blockquote_pdf(
    tokens: list,
    i: int,
    styles: dict[str, ParagraphStyle],
) -> tuple[int, list]:
    """Handle a blockquote_open token: collect content into styled paragraph."""
    j = i + 1
    bq_text_parts: list[str] = []
    depth = 1
    while j < len(tokens) and depth > 0:
        if tokens[j].type == "blockquote_open":
            depth += 1
        elif tokens[j].type == "blockquote_close":
            depth -= 1
        elif tokens[j].type == "inline":
            bq_text_parts.append(_extract_inline_text(tokens[j]))
        j += 1
    if bq_text_parts:
        return j, [Paragraph(" ".join(bq_text_parts), styles["blockquote"])]
    return j, []


def _handle_code_block_pdf(
    tokens: list,
    i: int,
    styles: dict[str, ParagraphStyle],
) -> tuple[int, list]:
    """Handle a fence or code_block token: create monospaced paragraph."""
    text = _xml_escape(tokens[i].content.rstrip("\n"))
    return i + 1, [Paragraph(text.replace("\n", "<br/>"), styles["code"])]


def _dispatch_block_pdf(
    tokens: list,
    i: int,
    styles: dict[str, ParagraphStyle],
    ordered_counter: list[int],
) -> tuple[int, list] | None:
    """Route a block token to its handler.

    Returns:
        (next_index, flowables) if handled, None otherwise.
    """
    tok = tokens[i]
    if tok.type == "heading_open":
        return _handle_heading_pdf(tokens, i, styles)
    if tok.type == "paragraph_open":
        return _handle_paragraph_pdf(tokens, i, styles)
    if tok.type == "hr":
        return i + 1, [
            Spacer(1, 4),
            HRFlowable(width="100%", thickness=0.5, color="black"),
            Spacer(1, 4),
        ]
    if tok.type in ("bullet_list_open", "bullet_list_close"):
        return i + 1, []
    if tok.type in ("ordered_list_open", "ordered_list_close"):
        ordered_counter[0] = 0
        return i + 1, []
    if tok.type == "list_item_open":
        return _handle_list_item_pdf(tokens, i, styles, ordered_counter)
    if tok.type == "blockquote_open":
        return _handle_blockquote_pdf(tokens, i, styles)
    if tok.type in ("fence", "code_block"):
        return _handle_code_block_pdf(tokens, i, styles)
    return None


# =============================================================================
# Block Token → Flowable Conversion
# =============================================================================


def _tokens_to_flowables(tokens: list, styles: dict[str, ParagraphStyle]) -> list:
    """Convert markdown-it block tokens to ReportLab flowables.

    Args:
        tokens: List of block-level tokens from markdown-it.
        styles: Pre-built paragraph styles.

    Returns:
        List of ReportLab flowables.
    """
    flowables: list = []
    i = 0
    ordered_counter: list[int] = [0]
    while i < len(tokens):
        result = _dispatch_block_pdf(tokens, i, styles, ordered_counter)
        if result is not None:
            i, new_flowables = result
            flowables.extend(new_flowables)
        else:
            i += 1
    return flowables


def _is_inside_ordered_list(tokens: list, current_idx: int) -> bool:
    """Check if a list_item_open at current_idx is inside an ordered list.

    Walks backwards to find the nearest list open token.

    Args:
        tokens: Full token list.
        current_idx: Index of the list_item_open token.

    Returns:
        True if inside an ordered_list, False otherwise.
    """
    depth = 0
    for j in range(current_idx - 1, -1, -1):
        if tokens[j].type == "list_item_close":
            depth += 1
        elif tokens[j].type == "list_item_open":
            if depth > 0:
                depth -= 1
            else:
                continue
        elif tokens[j].type == "ordered_list_open":
            return True
        elif tokens[j].type == "bullet_list_open":
            return False
    return False


# =============================================================================
# Public API
# =============================================================================


def render_pdf(markdown_content: str) -> bytes:
    """Render markdown content to PDF bytes.

    REQ-025 §5.2: Parses markdown via markdown-it-py, maps tokens to
    ReportLab Platypus flowables, and builds a PDF document.

    Args:
        markdown_content: Markdown string to render.

    Returns:
        PDF document as bytes.

    Raises:
        ValueError: If markdown_content is empty or whitespace-only.
    """
    if not markdown_content or not markdown_content.strip():
        raise ValueError("Markdown content cannot be empty.")

    if len(markdown_content) > _MAX_MARKDOWN_LENGTH:
        raise ValueError(
            f"Markdown content exceeds maximum length of {_MAX_MARKDOWN_LENGTH} characters."
        )

    md = MarkdownIt("commonmark")
    tokens = md.parse(markdown_content)

    styles = _build_styles()
    flowables = _tokens_to_flowables(tokens, styles)

    if not flowables:
        raise ValueError("Markdown content produced no renderable elements.")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        leftMargin=_MARGIN_SIDE,
        rightMargin=_MARGIN_SIDE,
        topMargin=_MARGIN_TOP,
        bottomMargin=_MARGIN_BOTTOM,
    )
    doc.build(flowables)
    return buf.getvalue()
