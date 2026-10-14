"""Polyline merging (linemerge) with endpoint distance threshold."""

from __future__ import annotations
import math
from typing import List
import numpy as np


def merge_polylines(lines: List[np.ndarray], tolerance_mm: float = 0.1) -> List[np.ndarray]:
    """
    Merge polylines whose endpoints are within tolerance_mm.
    Can reverse lines if orientation matches.
    """
    if len(lines) <= 1:
        return lines

    # Keep a pool of available lines
    pool = [l for l in lines if len(l) >= 2]
    if not pool:
        return []

    merged: List[np.ndarray] = []

    while pool:
        current = pool.pop(0)
        extended = True

        while extended:
            extended = False
            cur_start = current[0]
            cur_end = current[-1]

            best_idx = -1
            best_type = ""  # "append", "append_rev", "prepend", "prepend_rev"
            min_dist = tolerance_mm

            for idx, candidate in enumerate(pool):
                cand_start = candidate[0]
                cand_end = candidate[-1]

                # Check dist(cur_end, cand_start) -> append candidate
                d1 = math.hypot(cur_end[0] - cand_start[0], cur_end[1] - cand_start[1])
                if d1 < min_dist:
                    min_dist = d1
                    best_idx = idx
                    best_type = "append"

                # Check dist(cur_end, cand_end) -> append candidate reversed
                d2 = math.hypot(cur_end[0] - cand_end[0], cur_end[1] - cand_end[1])
                if d2 < min_dist:
                    min_dist = d2
                    best_idx = idx
                    best_type = "append_rev"

                # Check dist(cur_start, cand_end) -> prepend candidate
                d3 = math.hypot(cur_start[0] - cand_end[0], cur_start[1] - cand_end[1])
                if d3 < min_dist:
                    min_dist = d3
                    best_idx = idx
                    best_type = "prepend"

                # Check dist(cur_start, cand_start) -> prepend candidate reversed
                d4 = math.hypot(cur_start[0] - cand_start[0], cur_start[1] - cand_start[1])
                if d4 < min_dist:
                    min_dist = d4
                    best_idx = idx
                    best_type = "prepend_rev"

            if best_idx != -1:
                cand = pool.pop(best_idx)
                if best_type == "append":
                    current = np.vstack((current, cand[1:]))
                elif best_type == "append_rev":
                    current = np.vstack((current, cand[::-1][1:]))
                elif best_type == "prepend":
                    current = np.vstack((cand[:-1], current))
                elif best_type == "prepend_rev":
                    current = np.vstack((cand[::-1][:-1], current))
                extended = True

        merged.append(current)

    return merged
