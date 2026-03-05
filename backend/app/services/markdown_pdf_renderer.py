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
            href = token.attrGet("href") or ""
            if _is_safe_url(href):
                href_escaped = _html_escape(href, quote=True)
                parts.append(f'<a href="{href_escaped}" color="{_LINK_COLOR_HEX}"><u>')
            else:
                # Unsafe protocol (javascript:, data:, etc.) — render as plain text
                parts.append("<u>")
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
# Block Token → Flowable Conversion
# =============================================================================


def _tokens_to_flowables(tokens: list, styles: dict[str, ParagraphStyle]) -> list:
    """Convert markdown-it block tokens to ReportLab flowables.

    Walks the flat token list and emits Paragraph, HRFlowable, and Spacer
    flowables based on token types.

    Args:
        tokens: List of block-level tokens from markdown-it.
        styles: Pre-built paragraph styles.

    Returns:
        List of ReportLab flowables.
    """
    flowables: list = []
    i = 0
    ordered_counter = 0

    while i < len(tokens):
        token = tokens[i]

        # --- Headings ---
        if token.type == "heading_open":
            level = int(token.tag[1])  # h1→1, h2→2, etc.
            style_key = f"heading_{min(level, 4)}"
            # Next token is the inline content
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                text = _extract_inline_text(tokens[i + 1])
                flowables.append(Paragraph(text, styles[style_key]))
                i += 3  # heading_open, inline, heading_close
                continue

        # --- Paragraphs ---
        elif token.type == "paragraph_open":
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                text = _extract_inline_text(tokens[i + 1])
                flowables.append(Paragraph(text, styles["body"]))
                i += 3  # paragraph_open, inline, paragraph_close
                continue

        # --- Horizontal Rule ---
        elif token.type == "hr":
            flowables.append(Spacer(1, 4))
            flowables.append(HRFlowable(width="100%", thickness=0.5, color="black"))
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        # --- Unordered List ---
        elif token.type in ("bullet_list_open", "bullet_list_close"):
            i += 1
            continue

        # --- Ordered List ---
        elif token.type in ("ordered_list_open", "ordered_list_close"):
            ordered_counter = 0
            i += 1
            continue

        # --- List Items ---
        elif token.type == "list_item_open":
            # Determine if inside ordered or unordered list
            # Look backwards for the list open token
            is_ordered = _is_inside_ordered_list(tokens, i)
            if is_ordered:
                ordered_counter += 1

            # Find the inline content within this list item
            j = i + 1
            while j < len(tokens) and tokens[j].type != "list_item_close":
                if tokens[j].type == "inline":
                    text = _extract_inline_text(tokens[j])
                    if is_ordered:
                        bullet_text = f"{ordered_counter}."
                        flowables.append(
                            Paragraph(
                                text,
                                styles["ordered"],
                                bulletText=bullet_text,
                            )
                        )
                    else:
                        flowables.append(
                            Paragraph(
                                text,
                                styles["bullet"],
                                bulletText="\u2022",
                            )
                        )
                j += 1
            i = j + 1  # Skip past list_item_close
            continue

        # --- Blockquote ---
        elif token.type == "blockquote_open":
            # Collect content until blockquote_close
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
                flowables.append(
                    Paragraph(" ".join(bq_text_parts), styles["blockquote"])
                )
            i = j
            continue

        # --- Code Block / Fence ---
        elif token.type == "fence" or token.type == "code_block":
            text = _xml_escape(token.content.rstrip("\n"))
            flowables.append(Paragraph(text.replace("\n", "<br/>"), styles["code"]))
            i += 1
            continue

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
