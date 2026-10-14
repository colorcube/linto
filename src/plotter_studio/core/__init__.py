"""Core package containing geometry, document model and SVG handlers."""

from .geometry import Point, BoundingBox, AffineTransform
from .document import Page, LogicalPen, VectorPath, ImportItem, Document, PAPER_PRESETS, DEFAULT_PENS
from .svg_import import load_svg
from .svg_export import export_document_to_svg
from .color_cluster import cluster_colors_to_pens

__all__ = [
    "Point",
    "BoundingBox",
    "AffineTransform",
    "Page",
    "LogicalPen",
    "VectorPath",
    "ImportItem",
    "Document",
    "PAPER_PRESETS",
    "DEFAULT_PENS",
    "load_svg",
    "export_document_to_svg",
    "cluster_colors_to_pens",
]
