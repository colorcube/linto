"""Douglas-Peucker line simplification in millimeters."""

from __future__ import annotations
import numpy as np
from ..core.geometry import points_to_segment_distances


def ramer_douglas_peucker(points: np.ndarray, epsilon: float) -> np.ndarray:
    """
    Simplify a 2D polyline points (N, 2) using Ramer-Douglas-Peucker algorithm.
    epsilon: distance tolerance in millimeters.
    """
    if len(points) < 3:
        return points

    start = points[0]
    end = points[-1]
    dists = points_to_segment_distances(points[1:-1], start, end)

    if len(dists) == 0:
        return points

    max_idx = np.argmax(dists)
    max_dist = dists[max_idx]

    if max_dist > epsilon:
        # Recursive split
        split_idx = max_idx + 1
        left = ramer_douglas_peucker(points[:split_idx + 1], epsilon)
        right = ramer_douglas_peucker(points[split_idx:], epsilon)
        return np.vstack((left[:-1], right))
    else:
        return np.array([start, end])
