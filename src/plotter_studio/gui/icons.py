"""Monochrome vector icon provider in Breeze/Inkscape minimalist style."""

from __future__ import annotations
from typing import Dict, Optional
from PySide6.QtCore import QByteArray, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor
from PySide6.QtSvg import QSvgRenderer

DEFAULT_ICON_COLOR = "#374151"
DISABLED_ICON_COLOR = "#9ca3af"

SVG_TEMPLATES: Dict[str, str] = {
    "mode-layout": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="{color}" stroke-width="2"/>'
        '<path d="M3 9h18M9 21V9" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "mode-plot": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="{color}" stroke-width="2"/>'
        '<path d="M7 17l4-8 4 8M9 13h4" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<circle cx="17" cy="7" r="1.5" fill="{color}"/>'
        '</svg>'
    ),
    "import": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<polyline points="7 10 12 15 17 10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="12" y1="15" x2="12" y2="3" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "save": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="17 21 17 13 7 13 7 21" fill="none" stroke="{color}" stroke-width="2"/>'
        '<polyline points="7 3 7 8 15 8" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "undo": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M3 7v6h6" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "redo": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M21 7v6h-6" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "delete": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<polyline points="3 6 5 6 21 6" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="10" y1="11" x2="10" y2="17" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="14" y1="11" x2="14" y2="17" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "duplicate": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<rect x="8" y="8" width="13" height="13" rx="2" fill="none" stroke="{color}" stroke-width="2"/>'
        '<path d="M4 16H3a1 1 0 0 1-1-1V4a2 2 0 0 1 2-2h11a2 2 0 0 1 2 2v1" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "zoom-fit": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<polyline points="15 3 21 3 21 9" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="9 21 3 21 3 15" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="21 15 21 21 15 21" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="3 9 3 3 9 3" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "rotate-ccw": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M1 4v6h6" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "rotate-cw": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M23 4v6h-6" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "align-center": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<line x1="12" y1="2" x2="12" y2="22" stroke="{color}" stroke-width="1.5" stroke-dasharray="2 2"/>'
        '<line x1="2" y1="12" x2="22" y2="12" stroke="{color}" stroke-width="1.5" stroke-dasharray="2 2"/>'
        '<rect x="7" y="7" width="10" height="10" rx="1.5" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "align-h-center": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<line x1="12" y1="2" x2="12" y2="22" stroke="{color}" stroke-width="1.5" stroke-dasharray="2 2"/>'
        '<rect x="5" y="5" width="14" height="5" rx="1" fill="none" stroke="{color}" stroke-width="2"/>'
        '<rect x="3" y="14" width="18" height="5" rx="1" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "align-horizontal-center": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<line x1="12" y1="2" x2="12" y2="22" stroke="{color}" stroke-width="1.5" stroke-dasharray="2 2"/>'
        '<rect x="5" y="5" width="14" height="5" rx="1" fill="none" stroke="{color}" stroke-width="2"/>'
        '<rect x="3" y="14" width="18" height="5" rx="1" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "align-v-center": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<line x1="2" y1="12" x2="22" y2="12" stroke="{color}" stroke-width="1.5" stroke-dasharray="2 2"/>'
        '<rect x="5" y="5" width="5" height="14" rx="1" fill="none" stroke="{color}" stroke-width="2"/>'
        '<rect x="14" y="3" width="5" height="18" rx="1" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "align-vertical-center": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<line x1="2" y1="12" x2="22" y2="12" stroke="{color}" stroke-width="1.5" stroke-dasharray="2 2"/>'
        '<rect x="5" y="5" width="5" height="14" rx="1" fill="none" stroke="{color}" stroke-width="2"/>'
        '<rect x="14" y="3" width="5" height="18" rx="1" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "fit-page": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<rect x="2" y="2" width="20" height="20" rx="2" fill="none" stroke="{color}" stroke-width="1.5" stroke-dasharray="3 2"/>'
        '<rect x="6" y="6" width="12" height="12" rx="1" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "original-size": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<rect x="3" y="3" width="18" height="18" rx="2" fill="none" stroke="{color}" stroke-width="1.5"/>'
        '<text x="12" y="15.5" font-family="monospace, sans-serif" font-size="9" font-weight="bold" fill="{color}" text-anchor="middle">1:1</text>'
        '</svg>'
    ),
    "printer": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M6 9V2h12v7M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<rect x="6" y="14" width="12" height="8" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "settings": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<circle cx="12" cy="12" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z" fill="none" stroke="{color}" stroke-width="1.8"/>'
        '</svg>'
    ),
    "refresh": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<polyline points="23 4 23 10 17 10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "search": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<circle cx="11" cy="11" r="7" fill="none" stroke="{color}" stroke-width="2"/>'
        '<line x1="21" y1="21" x2="16" y2="16" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "chain": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "chain-broken": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="2" y1="2" x2="22" y2="22" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "eye": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="12" cy="12" r="3" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "eye-off": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="1" y1="1" x2="23" y2="23" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "lock": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<rect x="3" y="11" width="18" height="11" rx="2" ry="2" fill="none" stroke="{color}" stroke-width="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 10 0v4" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "lock-open": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<rect x="3" y="11" width="18" height="11" rx="2" ry="2" fill="none" stroke="{color}" stroke-width="2"/>'
        '<path d="M7 11V7a5 5 0 0 1 9.9-1" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "arrow-up": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<polyline points="18 15 12 9 6 15" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "arrow-down": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<polyline points="6 9 12 15 18 9" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "play": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<polygon points="5 3 19 12 5 21 5 3" fill="{color}" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "pause": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<rect x="6" y="4" width="4" height="16" fill="{color}" stroke="{color}" stroke-width="2"/>'
        '<rect x="14" y="4" width="4" height="16" fill="{color}" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "stop": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<rect x="4" y="4" width="16" height="16" rx="2" fill="{color}" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "plus": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<line x1="12" y1="5" x2="12" y2="19" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<line x1="5" y1="12" x2="19" y2="12" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "skip-back": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<polygon points="19 20 9 12 19 4 19 20" fill="{color}"/>'
        '<line x1="5" y1="19" x2="5" y2="5" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "skip-forward": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<polygon points="5 4 15 12 5 20 5 4" fill="{color}"/>'
        '<line x1="19" y1="5" x2="19" y2="19" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '</svg>'
    ),
    "page": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<polyline points="14 2 14 8 20 8" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<line x1="8" y1="13" x2="16" y2="13" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>'
        '<line x1="8" y1="17" x2="13" y2="17" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>'
        '</svg>'
    ),
    "pencil": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "travel": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<path d="M22 2L11 13" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<polygon points="22 2 15 22 11 13 2 9 22 2" fill="none" stroke="{color}" stroke-width="2" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "percent": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<line x1="19" y1="5" x2="5" y2="19" stroke="{color}" stroke-width="2" stroke-linecap="round"/>'
        '<circle cx="6.5" cy="6.5" r="2.5" fill="none" stroke="{color}" stroke-width="2"/>'
        '<circle cx="17.5" cy="17.5" r="2.5" fill="none" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
    "clock": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<circle cx="12" cy="12" r="10" fill="none" stroke="{color}" stroke-width="2"/>'
        '<polyline points="12 6 12 12 16 14" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '</svg>'
    ),
    "node": (
        '<svg viewBox="0 0 24 24" width="24" height="24">'
        '<circle cx="12" cy="12" r="4" fill="none" stroke="{color}" stroke-width="2"/>'
        '<circle cx="12" cy="12" r="1.5" fill="{color}"/>'
        '<line x1="12" y1="2" x2="12" y2="6" stroke="{color}" stroke-width="2"/>'
        '<line x1="12" y1="18" x2="12" y2="22" stroke="{color}" stroke-width="2"/>'
        '<line x1="2" y1="12" x2="6" y2="12" stroke="{color}" stroke-width="2"/>'
        '<line x1="18" y1="12" x2="22" y2="12" stroke="{color}" stroke-width="2"/>'
        '</svg>'
    ),
}

_icon_cache: Dict[str, QIcon] = {}


def get_icon(name: str, color: str = DEFAULT_ICON_COLOR, size: int = 24) -> QIcon:
    """Return a crisp, monochrome QIcon for the given symbol name."""
    cache_key = f"{name}:{color}:{size}"
    if cache_key in _icon_cache:
        return _icon_cache[cache_key]

    template = SVG_TEMPLATES.get(name)
    if not template:
        return QIcon()

    svg_normal = template.format(color=color)
    svg_disabled = template.format(color=DISABLED_ICON_COLOR)

    icon = QIcon()
    for sz in (16, 20, 24, 32, 48):
        # Normal state
        pix_normal = _render_svg_to_pixmap(svg_normal, sz)
        icon.addPixmap(pix_normal, QIcon.Normal, QIcon.Off)
        icon.addPixmap(pix_normal, QIcon.Normal, QIcon.On)

        # Disabled state
        pix_disabled = _render_svg_to_pixmap(svg_disabled, sz)
        icon.addPixmap(pix_disabled, QIcon.Disabled, QIcon.Off)
        icon.addPixmap(pix_disabled, QIcon.Disabled, QIcon.On)

    _icon_cache[cache_key] = icon
    return icon


def _render_svg_to_pixmap(svg_str: str, size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    renderer = QSvgRenderer(QByteArray(svg_str.encode("utf-8")))
    painter = QPainter(pixmap)
    renderer.render(painter)
    painter.end()
    return pixmap
