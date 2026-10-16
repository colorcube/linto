"""Path sorting and travel optimization (minimizing pen-up movements)."""

from __future__ import annotations
import math
from typing import List, Tuple, Optional
import numpy as np


def compute_polyline_length(points: np.ndarray) -> float:
    """Compute total length of polyline in millimeters."""
    if len(points) < 2:
        return 0.0
    deltas = np.diff(points, axis=0)
    return float(np.sum(np.hypot(deltas[:, 0], deltas[:, 1])))


def compute_unsorted_travel_distance(
    lines: List[np.ndarray],
    start_pos: Tuple[float, float] = (0.0, 0.0),
) -> float:
    """Calculate total pen-up travel distance without sorting."""
    travel = 0.0
    cur = start_pos
    for line in lines:
        if len(line) == 0:
            continue
        p_start = line[0]
        travel += math.hypot(p_start[0] - cur[0], p_start[1] - cur[1])
        cur = (float(line[-1, 0]), float(line[-1, 1]))
    return travel


def optimize_paths_greedy(
    lines: List[np.ndarray],
    start_pos: Tuple[float, float] = (0.0, 0.0),
    allow_reverse: bool = True,
) -> Tuple[List[np.ndarray], List[Tuple[Tuple[float, float], Tuple[float, float]]], float]:
    """
    Vectorized greedy nearest-neighbor sorting of polylines to minimize pen-up travel.
    Returns: (sorted_lines, travels, total_travel_distance)
    """
    valid_lines = [l for l in lines if len(l) >= 2]
    n = len(valid_lines)
    if n == 0:
        return [], [], 0.0

    starts = np.array([l[0] for l in valid_lines], dtype=float)
    ends = np.array([l[-1] for l in valid_lines], dtype=float)
    active = np.ones(n, dtype=bool)

    sorted_lines: List[np.ndarray] = []
    travels: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    total_travel = 0.0

    cur = np.array(start_pos, dtype=float)

    for _ in range(n):
        rem_indices = np.flatnonzero(active)
        d_start_sq = np.sum((starts[rem_indices] - cur) ** 2, axis=1)
        min_start_local = int(np.argmin(d_start_sq))
        best_dist_sq = float(d_start_sq[min_start_local])
        best_idx = int(rem_indices[min_start_local])
        best_reverse = False

        if allow_reverse:
            d_end_sq = np.sum((ends[rem_indices] - cur) ** 2, axis=1)
            min_end_local = int(np.argmin(d_end_sq))
            if float(d_end_sq[min_end_local]) < best_dist_sq:
                best_dist_sq = float(d_end_sq[min_end_local])
                best_idx = int(rem_indices[min_end_local])
                best_reverse = True

        active[best_idx] = False
        chosen = valid_lines[best_idx]
        if best_reverse:
            chosen = chosen[::-1]

        target_start = (float(chosen[0, 0]), float(chosen[0, 1]))
        travels.append(((float(cur[0]), float(cur[1])), target_start))
        total_travel += math.sqrt(best_dist_sq)

        sorted_lines.append(chosen)
        cur = chosen[-1]

    return sorted_lines, travels, total_travel


def optimize_paths_2opt(
    lines: List[np.ndarray],
    travels: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    total_travel: float,
    start_pos: Tuple[float, float] = (0.0, 0.0),
    max_passes: int = 5,
) -> Tuple[List[np.ndarray], List[Tuple[Tuple[float, float], Tuple[float, float]]], float]:
    """
    Refine line order using vectorized 2-opt swaps to resolve crossing travel lines.
    """
    n = len(lines)
    if n < 4:
        return lines, travels, total_travel

    current_lines = list(lines)
    starts = np.array([l[0] for l in current_lines], dtype=float)
    ends = np.array([l[-1] for l in current_lines], dtype=float)

    improved = True
    passes = 0

    while improved and passes < max_passes:
        improved = False
        passes += 1

        for i in range(1, n - 1):
            p_prev_end = ends[i - 1]
            p_i_start = starts[i]
            d_i = float(np.hypot(p_i_start[0] - p_prev_end[0], p_i_start[1] - p_prev_end[1]))

            # Vectorized candidate j in range(i + 1, n)
            j_ends = ends[i + 1 : n]
            new_d_i = np.hypot(j_ends[:, 0] - p_prev_end[0], j_ends[:, 1] - p_prev_end[1])

            d_j = np.zeros(n - (i + 1), dtype=float)
            new_d_j = np.zeros(n - (i + 1), dtype=float)
            if i + 2 < n:
                next_starts = starts[i + 2 : n]
                d_j[:-1] = np.hypot(
                    next_starts[:, 0] - j_ends[:-1, 0],
                    next_starts[:, 1] - j_ends[:-1, 1],
                )
                new_d_j[:-1] = np.hypot(
                    next_starts[:, 0] - p_i_start[0],
                    next_starts[:, 1] - p_i_start[1],
                )

            gains = (d_i + d_j) - (new_d_i + new_d_j)
            best_local = int(np.argmax(gains))
            if gains[best_local] > 1e-4:
                j = i + 1 + best_local
                current_lines[i : j + 1] = [l[::-1] for l in reversed(current_lines[i : j + 1])]
                # Flip and swap starts/ends in-place for slice [i : j + 1]
                new_starts = ends[i : j + 1][::-1].copy()
                new_ends = starts[i : j + 1][::-1].copy()
                starts[i : j + 1] = new_starts
                ends[i : j + 1] = new_ends
                improved = True

    # Rebuild travels
    rebuilt_travels: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    cur_x, cur_y = start_pos
    new_total_travel = 0.0
    for line in current_lines:
        t_start = (float(line[0, 0]), float(line[0, 1]))
        rebuilt_travels.append(((cur_x, cur_y), t_start))
        new_total_travel += math.hypot(t_start[0] - cur_x, t_start[1] - cur_y)
        cur_x, cur_y = float(line[-1, 0]), float(line[-1, 1])

    return current_lines, rebuilt_travels, new_total_travel


def sort_and_optimize_lines(
    lines: List[np.ndarray],
    start_pos: Tuple[float, float] = (0.0, 0.0),
    use_2opt: bool = True,
    allow_reverse: bool = True,
) -> Tuple[List[np.ndarray], List[Tuple[Tuple[float, float], Tuple[float, float]]], float, float]:
    """
    Complete path optimization pipeline for a set of polylines.
    Returns: (optimized_lines, travels, final_travel_mm, unsorted_travel_mm)
    """
    valid_lines = [l for l in lines if len(l) >= 2]
    if not valid_lines:
        return [], [], 0.0, 0.0

    unsorted_travel = compute_unsorted_travel_distance(valid_lines, start_pos)
    sorted_lines, travels, greedy_travel = optimize_paths_greedy(
        valid_lines, start_pos=start_pos, allow_reverse=allow_reverse
    )

    if use_2opt and len(sorted_lines) > 3:
        sorted_lines, travels, final_travel = optimize_paths_2opt(
            sorted_lines, travels, greedy_travel, start_pos=start_pos
        )
    else:
        final_travel = greedy_travel

    return sorted_lines, travels, final_travel, unsorted_travel
