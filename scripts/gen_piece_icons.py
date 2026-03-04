#!/usr/bin/env python3
"""Generate frontend piece SVG icons from favicon.svg template."""

from __future__ import annotations

from pathlib import Path
import re

ROOT_DIR = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = ROOT_DIR / "frontend/public/favicon.svg"
OUTPUT_DIR = ROOT_DIR / "frontend/public/pieces"

BLACK_PIECE_COLOR = "#1f2937"
PLACEHOLDER_TEXT = "{{PIECE_TEXT}}"
PLACEHOLDER_COLOR = "{{PIECE_COLOR}}"

PIECE_TEXT_MAP: dict[str, str] = {
    "R_SHI": "仕",
    "B_SHI": "士",
    "R_XIANG": "相",
    "B_XIANG": "象",
    "R_MA": "傌",
    "B_MA": "馬",
    "R_CHE": "俥",
    "B_CHE": "車",
    "R_GOU": "炮",
    "B_GOU": "砲",
    "R_NIU": "兵",
    "B_NIU": "卒",
}

TEXT_NODE_PATTERN = re.compile(r"(<text\b[^>]*>)(.*?)(</text>)", flags=re.IGNORECASE | re.DOTALL)
FILL_ATTR_PATTERN = re.compile(r"""\bfill\s*=\s*(["'])([^"']+)\1""", flags=re.IGNORECASE)


def _extract_base_color(template_svg: str) -> str:
    text_match = TEXT_NODE_PATTERN.search(template_svg)
    if text_match is None:
        raise ValueError("Template SVG must contain a <text> node or use placeholders.")
    open_tag = text_match.group(1)
    fill_match = FILL_ATTR_PATTERN.search(open_tag)
    if fill_match is None:
        raise ValueError("Template <text> must contain fill attribute or use placeholders.")
    return fill_match.group(2)


def _replace_first_text_node(template_svg: str, target_text: str) -> str:
    def replacer(match: re.Match[str]) -> str:
        return f"{match.group(1)}{target_text}{match.group(3)}"

    output, replaced_count = TEXT_NODE_PATTERN.subn(replacer, template_svg, count=1)
    if replaced_count != 1:
        raise ValueError("Template SVG must contain one replaceable <text> node.")
    return output


def _render_piece_svg(
    *,
    template_svg: str,
    piece_text: str,
    piece_color: str,
    base_color: str,
    use_placeholders: bool,
) -> str:
    if use_placeholders:
        return template_svg.replace(PLACEHOLDER_TEXT, piece_text).replace(PLACEHOLDER_COLOR, piece_color)

    with_piece_text = _replace_first_text_node(template_svg, piece_text)
    return re.sub(re.escape(base_color), piece_color, with_piece_text, flags=re.IGNORECASE)


def main() -> None:
    if not TEMPLATE_PATH.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE_PATH}")

    template_svg = TEMPLATE_PATH.read_text(encoding="utf-8")
    use_placeholders = PLACEHOLDER_TEXT in template_svg and PLACEHOLDER_COLOR in template_svg
    base_color = _extract_base_color(template_svg)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated: list[Path] = []
    for piece_code, piece_text in PIECE_TEXT_MAP.items():
        piece_color = BLACK_PIECE_COLOR if piece_code.startswith("B_") else base_color
        output_svg = _render_piece_svg(
            template_svg=template_svg,
            piece_text=piece_text,
            piece_color=piece_color,
            base_color=base_color,
            use_placeholders=use_placeholders,
        )
        output_path = OUTPUT_DIR / f"{piece_code}.svg"
        output_path.write_text(output_svg, encoding="utf-8")
        generated.append(output_path)

    print(f"Generated {len(generated)} icons in {OUTPUT_DIR}")
    for path in generated:
        print(f"- {path.relative_to(ROOT_DIR)}")


if __name__ == "__main__":
    main()
