"""Douglas-Peucker line simplification in millimeters."""

from __future__ import annotations
import numpy as np


def ramer_douglas_peucker(points: np.ndarray, epsilon: float) -> np.ndarray:
    """
    Simplify a 2D polyline points (N, 2) using Ramer-Douglas-Peucker algorithm.
    epsilon: distance tolerance in millimeters.
    """
    if len(points) < 3:
        return points

    start = points[0]
    end = points[-1]

    # Vector along baseline
    line_vec = end - start
    line_len_sq = np.dot(line_vec, line_vec)

    if line_len_sq < 1e-12:
        # Start and end are virtually identical
        dists = np.linalg.norm(points[1:-1] - start, axis=1)
    else:
        # Distance from points to line segment
        # Cross product in 2D gives area of parallelogram
        # dist = |(P - start) x (end - start)| / |end - start|
        d_vec = points[1:-1] - start
        cross = np.abs(d_vec[:, 0] * line_vec[1] - d_vec[:, 1] * line_vec[0])
        dists = cross / np.sqrt(line_len_sq)

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
