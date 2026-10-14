"""Pipeline algorithms: curve flattening, line merging, simplification."""

from .flatten import flatten_cubic_bezier, flatten_quadratic_bezier, flatten_arc
from .simplify import ramer_douglas_peucker
from .merge import merge_polylines

__all__ = [
    "flatten_cubic_bezier",
    "flatten_quadratic_bezier",
    "flatten_arc",
    "ramer_douglas_peucker",
    "merge_polylines",
]
