"""Pipeline algorithms: curve flattening, line merging, simplification."""

from .flatten import flatten_cubic_bezier, flatten_quadratic_bezier, flatten_arc
from .simplify import ramer_douglas_peucker
from .merge import merge_polylines
from .sort import sort_and_optimize_lines
from .clip import clip_polylines_to_box, clip_polyline_to_box
from .compiler import (
    PipelineConfig, PlotStep, PlotLayer, PlotJob,
    compile_document_to_plot_job
)

__all__ = [
    "flatten_cubic_bezier",
    "flatten_quadratic_bezier",
    "flatten_arc",
    "ramer_douglas_peucker",
    "merge_polylines",
    "sort_and_optimize_lines",
    "clip_polylines_to_box",
    "clip_polyline_to_box",
    "PipelineConfig",
    "PlotStep",
    "PlotLayer",
    "PlotJob",
    "compile_document_to_plot_job",
]
