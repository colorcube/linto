"""Polyline merging (linemerge) with endpoint distance threshold."""

from __future__ import annotations
from typing import List
import numpy as np


def merge_polylines(lines: List[np.ndarray], tolerance_mm: float = 0.1) -> List[np.ndarray]:
    """
    Merge polylines whose endpoints are within tolerance_mm using vectorized NumPy lookup.
    Can reverse lines if orientation matches.
    """
    if len(lines) <= 1:
        return lines

    pool = [l for l in lines if len(l) >= 2]
    if not pool:
        return []

    n = len(pool)
    starts = np.array([l[0] for l in pool], dtype=float)
    ends = np.array([l[-1] for l in pool], dtype=float)
    active = np.ones(n, dtype=bool)
    tol_sq = tolerance_mm * tolerance_mm

    merged: List[np.ndarray] = []

    for seed_idx in range(n):
        if not active[seed_idx]:
            continue
        active[seed_idx] = False
        chunks = [pool[seed_idx]]
        cur_start = starts[seed_idx].copy()
        cur_end = ends[seed_idx].copy()

        while True:
            rem_indices = np.flatnonzero(active)
            if len(rem_indices) == 0:
                break

            cand_starts = starts[rem_indices]
            cand_ends = ends[rem_indices]

            # Squared distances to candidate endpoints:
            # 0: cur_end -> cand_start (append)
            # 1: cur_end -> cand_end   (append_rev)
            # 2: cur_start -> cand_end (prepend)
            # 3: cur_start -> cand_start (prepend_rev)
            d0 = np.sum((cand_starts - cur_end) ** 2, axis=1)
            d1 = np.sum((cand_ends - cur_end) ** 2, axis=1)
            d2 = np.sum((cand_ends - cur_start) ** 2, axis=1)
            d3 = np.sum((cand_starts - cur_start) ** 2, axis=1)

            all_dists = np.vstack((d0, d1, d2, d3))
            min_flat = int(np.argmin(all_dists))
            best_mode, local_idx = divmod(min_flat, len(rem_indices))
            best_dist_sq = all_dists[best_mode, local_idx]

            if best_dist_sq >= tol_sq:
                break

            cand_idx = int(rem_indices[local_idx])
            active[cand_idx] = False
            cand = pool[cand_idx]

            if best_mode == 0:  # append
                chunks.append(cand[1:])
                cur_end = ends[cand_idx].copy()
            elif best_mode == 1:  # append_rev
                chunks.append(cand[::-1][1:])
                cur_end = starts[cand_idx].copy()
            elif best_mode == 2:  # prepend
                chunks.insert(0, cand[:-1])
                cur_start = starts[cand_idx].copy()
            else:  # prepend_rev
                chunks.insert(0, cand[::-1][:-1])
                cur_start = ends[cand_idx].copy()

        if len(chunks) == 1:
            merged.append(chunks[0])
        else:
            merged.append(np.vstack(chunks))

    return merged


def deduplicate_polylines(
    lines: List[np.ndarray],
    tolerance_mm: float = 0.02,
) -> tuple[List[np.ndarray], int]:
    """
    Remove duplicate/overlapping segments (both A->B and B->A) across polylines.
    Returns (cleaned_polylines, removed_segment_count).
    """
    if not lines:
        return [], 0

    grid = max(1e-4, float(tolerance_mm))
    seen_segments: set[tuple[tuple[int, int], tuple[int, int]]] = set()
    cleaned: List[np.ndarray] = []
    removed_count = 0

    for poly in lines:
        if len(poly) < 2:
            continue
        current_run: list[np.ndarray] = [poly[0]]
        for idx in range(len(poly) - 1):
            p0 = poly[idx]
            p1 = poly[idx + 1]
            q0 = (int(round(float(p0[0]) / grid)), int(round(float(p0[1]) / grid)))
            q1 = (int(round(float(p1[0]) / grid)), int(round(float(p1[1]) / grid)))
            if q0 != q1:
                seg_key = (q0, q1) if q0 <= q1 else (q1, q0)
                if seg_key in seen_segments:
                    removed_count += 1
                    if len(current_run) >= 2:
                        cleaned.append(np.array(current_run, dtype=np.float64))
                    current_run = [p1]
                    continue
                seen_segments.add(seg_key)
            current_run.append(p1)

        if len(current_run) >= 2:
            cleaned.append(np.array(current_run, dtype=np.float64))

    return cleaned, removed_count

