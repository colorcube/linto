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
    Greedy nearest-neighbor sorting of polylines to minimize pen-up travel.
    Returns: (sorted_lines, travels, total_travel_distance)
    """
    valid_lines = [l for l in lines if len(l) >= 2]
    if not valid_lines:
        return [], [], 0.0

    pool = list(valid_lines)
    sorted_lines: List[np.ndarray] = []
    travels: List[Tuple[Tuple[float, float], Tuple[float, float]]] = []
    total_travel = 0.0

    cur_x, cur_y = start_pos

    while pool:
        best_idx = 0
        best_dist = float("inf")
        best_reverse = False

        for idx, line in enumerate(pool):
            s_x, s_y = line[0, 0], line[0, 1]
            d_start = math.hypot(s_x - cur_x, s_y - cur_y)
            if d_start < best_dist:
                best_dist = d_start
                best_idx = idx
                best_reverse = False

            if allow_reverse:
                e_x, e_y = line[-1, 0], line[-1, 1]
                d_end = math.hypot(e_x - cur_x, e_y - cur_y)
                if d_end < best_dist:
                    best_dist = d_end
                    best_idx = idx
                    best_reverse = True

        chosen = pool.pop(best_idx)
        if best_reverse:
            chosen = chosen[::-1]

        target_start = (float(chosen[0, 0]), float(chosen[0, 1]))
        travels.append(((cur_x, cur_y), target_start))
        total_travel += best_dist

        sorted_lines.append(chosen)
        cur_x, cur_y = float(chosen[-1, 0]), float(chosen[-1, 1])

    return sorted_lines, travels, total_travel


def optimize_paths_2opt(
    lines: List[np.ndarray],
    travels: List[Tuple[Tuple[float, float], Tuple[float, float]]],
    total_travel: float,
    start_pos: Tuple[float, float] = (0.0, 0.0),
    max_passes: int = 5,
) -> Tuple[List[np.ndarray], List[Tuple[Tuple[float, float], Tuple[float, float]]], float]:
    """
    Refine line order using 2-opt swaps to resolve crossing travel lines.
    """
    n = len(lines)
    if n < 4:
        return lines, travels, total_travel

    current_lines = list(lines)
    improved = True
    passes = 0

    while improved and passes < max_passes:
        improved = False
        passes += 1

        for i in range(1, n - 1):
            for j in range(i + 1, n):
                p_prev_end = (current_lines[i - 1][-1, 0], current_lines[i - 1][-1, 1])
                p_i_start = (current_lines[i][0, 0], current_lines[i][0, 1])
                d_i = math.hypot(p_i_start[0] - p_prev_end[0], p_i_start[1] - p_prev_end[1])

                p_j_end = (current_lines[j][-1, 0], current_lines[j][-1, 1])
                if j + 1 < n:
                    p_next_start = (current_lines[j + 1][0, 0], current_lines[j + 1][0, 1])
                    d_j = math.hypot(p_next_start[0] - p_j_end[0], p_next_start[1] - p_j_end[1])
                else:
                    d_j = 0.0

                old_dist = d_i + d_j

                p_new_i_start = p_j_end
                new_d_i = math.hypot(p_new_i_start[0] - p_prev_end[0], p_new_i_start[1] - p_prev_end[1])

                if j + 1 < n:
                    p_new_j_end = p_i_start
                    new_d_j = math.hypot(p_next_start[0] - p_new_j_end[0], p_next_start[1] - p_new_j_end[1])
                else:
                    new_d_j = 0.0

                new_dist = new_d_i + new_d_j

                if new_dist < old_dist - 1e-4:
                    reversed_block = [l[::-1] for l in reversed(current_lines[i : j + 1])]
                    current_lines[i : j + 1] = reversed_block
                    improved = True
                    break
            if improved:
                break

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
