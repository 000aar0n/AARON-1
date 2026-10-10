"""Shared Unicode web-font stack for Streamlit and its calendar iframe."""
from __future__ import annotations

GOOGLE_FONT_CSS = (
    "https://fonts.googleapis.com/css2?"
    "family=Noto+Sans+SC&family=Noto+Sans+JP&family=Noto+Sans+KR"
    "&family=Noto+Sans+Arabic&family=Noto+Sans+Math"
    "&family=Noto+Sans+Symbols+2&family=Noto+Emoji&display=swap"
)
FONT_IMPORT = "@import url(\x27" + GOOGLE_FONT_CSS + "\x27);\n"
FONT_STACK = (
    "Inter, -apple-system, BlinkMacSystemFont, Segoe UI, "
    "\x27Noto Sans SC\x27, \x27PingFang SC\x27, \x27Microsoft YaHei\x27, "
    "\x27Noto Sans JP\x27, \x27Hiragino Sans\x27, "
    "\x27Noto Sans KR\x27, \x27Apple SD Gothic Neo\x27, "
    "\x27Noto Sans Arabic\x27, \x27Geeza Pro\x27, "
    "\x27Noto Sans Math\x27, \x27Cambria Math\x27, "
    "\x27Apple Color Emoji\x27, \x27Segoe UI Emoji\x27, \x27Noto Color Emoji\x27, "
    "\x27Noto Sans Symbols 2\x27, \x27Segoe UI Symbol\x27, \x27Noto Emoji\x27, sans-serif"
)
