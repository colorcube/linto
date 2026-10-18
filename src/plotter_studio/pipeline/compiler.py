"""Plot Job Compiler translating Document into optimized, plottable vector layers."""

from __future__ import annotations
import math
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional
import numpy as np

from ..core.document import Document, LogicalPen
from .merge import merge_polylines
from .simplify import ramer_douglas_peucker
from .sort import sort_and_optimize_lines, compute_polyline_length, compute_unsorted_travel_distance
from .clip import clip_polylines_to_box


@dataclass
class PipelineConfig:
    """Configuration options for pipeline optimization."""
    flatten_tolerance_mm: float = 0.05
    merge_tolerance_mm: float = 0.10
    simplify_tolerance_mm: float = 0.02
    sort_paths: bool = True
    use_2opt: bool = True
    clip_to_plottable: bool = False
    travel_speed_mm_s: float = 500.0       # Pen-up travel speed
    pen_change_time_s: float = 4.0        # Overhead per pen carousel change
    pen_actuation_time_s: float = 0.03    # Overhead per pen-down / pen-up


@dataclass
class PlotStep:
    """An atomic step in the plot execution (for simulation and streaming)."""
    action: str  # "DRAW" or "TRAVEL"
    points: np.ndarray  # Shape (N, 2)
    pen_id: int
    step_index: int = 0


@dataclass
class PlotLayer:
    """Compiled, optimized vector paths and statistics for a single logical pen."""
    pen_id: int
    pen: LogicalPen
    lines: List[np.ndarray] = field(default_factory=list)
    travels: List[Tuple[Tuple[float, float], Tuple[float, float]]] = field(default_factory=list)
    draw_distance_mm: float = 0.0
    travel_distance_mm: float = 0.0
    unsorted_travel_mm: float = 0.0
    estimated_duration_s: float = 0.0

    @property
    def point_count(self) -> int:
        return sum(len(l) for l in self.lines)


@dataclass
class PlotJob:
    """Complete compiled plot job ready for visualization or hardware streaming."""
    layers: Dict[int, PlotLayer] = field(default_factory=dict)
    total_draw_mm: float = 0.0
    total_travel_mm: float = 0.0
    total_unsorted_travel_mm: float = 0.0
    pen_changes: int = 0
    estimated_duration_s: float = 0.0
    warnings: List[str] = field(default_factory=list)
    steps: List[PlotStep] = field(default_factory=list)
    total_points: int = 0

    @property
    def travel_savings_pct(self) -> float:
        if self.total_unsorted_travel_mm <= 1e-4:
            return 0.0
        saved = self.total_unsorted_travel_mm - self.total_travel_mm
        return max(0.0, (saved / self.total_unsorted_travel_mm) * 100.0)

    @property
    def formatted_duration(self) -> str:
        sec = int(self.estimated_duration_s)
        minutes = sec // 60
        rem_sec = sec % 60
        hours = minutes // 60
        rem_min = minutes % 60
        if hours > 0:
            return f"{hours}h {rem_min:02d}m {rem_sec:02d}s"
        return f"{minutes:02d}m {rem_sec:02d}s"


def compile_document_to_plot_job(
    doc: Document,
    config: Optional[PipelineConfig] = None,
) -> PlotJob:
    """
    Compile document items into an optimized PlotJob with per-pen layers,
    travel paths, statistics, and sequential simulation steps.
    """
    cfg = config or PipelineConfig()
    job = PlotJob()

    # Step 1: Collect transformed paths grouped by effective pen ID
    raw_by_pen: Dict[int, List[np.ndarray]] = {}
    pens_dict = {p.pen_id: p for p in doc.pens}

    # Bounding box check for warnings
    pb = doc.page.plottable_box
    max_overhang = 0.0

    for item in doc.items:
        if not item.visible:
            continue
        for path in item.paths:
            pen = pens_dict.get(path.pen_id)
            if pen is None:
                # Fallback to default pen 1
                pen = pens_dict.get(1, LogicalPen(pen_id=1, name="Standard", color_hex="#000000"))

            # Skip disabled pens (both source pen and remapped target pen)
            if not pen.enabled:
                continue

            eff_id = pen.effective_pen_id
            target_pen = pens_dict.get(eff_id)
            if target_pen is not None and not target_pen.enabled:
                continue
            pts = path.to_polyline(
                tolerance_mm=cfg.flatten_tolerance_mm,
                transform=item.transform,
            )
            if len(pts) < 2:
                continue

            # Check overhang
            min_x, min_y = float(np.min(pts[:, 0])), float(np.min(pts[:, 1]))
            max_x, max_y = float(np.max(pts[:, 0])), float(np.max(pts[:, 1]))
            oh_left = max(0.0, pb.min_x - min_x)
            oh_right = max(0.0, max_x - pb.max_x)
            oh_top = max(0.0, pb.min_y - min_y)
            oh_bottom = max(0.0, max_y - pb.max_y)
            overhang = max(oh_left, oh_right, oh_top, oh_bottom)
            if overhang > max_overhang:
                max_overhang = overhang

            if eff_id not in raw_by_pen:
                raw_by_pen[eff_id] = []
            raw_by_pen[eff_id].append(pts)

    if max_overhang > 0.2:
        job.warnings.append(
            f"Zeichnung ragt um {max_overhang:.1f} mm über den plottbaren Bereich hinaus."
        )

    # Step 2: Process each pen layer
    cur_sim_pos = (0.0, 0.0)
    step_counter = 0

    sorted_pen_ids = sorted(raw_by_pen.keys())

    for pen_id in sorted_pen_ids:
        raw_lines = raw_by_pen[pen_id]
        pen_obj = pens_dict.get(pen_id, LogicalPen(pen_id=pen_id, name=f"Stift {pen_id}", color_hex="#000000"))

        # Optional clipping
        if cfg.clip_to_plottable:
            clipped = clip_polylines_to_box(raw_lines, pb.min_x, pb.min_y, pb.max_x, pb.max_y)
        else:
            clipped = raw_lines

        # Merge
        if cfg.merge_tolerance_mm > 0:
            merged = merge_polylines(clipped, tolerance_mm=cfg.merge_tolerance_mm)
        else:
            merged = clipped

        # Simplify
        if cfg.simplify_tolerance_mm > 0:
            simplified = [
                ramer_douglas_peucker(line, epsilon=cfg.simplify_tolerance_mm)
                for line in merged
                if len(line) >= 2
            ]
        else:
            simplified = [line for line in merged if len(line) >= 2]

        # Sorting
        if cfg.sort_paths:
            opt_lines, travels, travel_mm, unsorted_travel_mm = sort_and_optimize_lines(
                simplified,
                start_pos=cur_sim_pos,
                use_2opt=cfg.use_2opt,
                allow_reverse=True,
            )
        else:
            opt_lines = simplified
            travels = []
            travel_mm = 0.0
            unsorted_travel_mm = compute_unsorted_travel_distance(simplified, cur_sim_pos)
            c_pos = cur_sim_pos
            for l in opt_lines:
                t_target = (float(l[0, 0]), float(l[0, 1]))
                travels.append((c_pos, t_target))
                travel_mm += math.hypot(t_target[0] - c_pos[0], t_target[1] - c_pos[1])
                c_pos = (float(l[-1, 0]), float(l[-1, 1]))

        # Calculate draw length
        draw_mm = sum(compute_polyline_length(l) for l in opt_lines)

        # Estimate duration
        # draw_speed = pen_obj.speed_cm_s * 10.0 (in mm/s)
        speed_mm_s = max(10.0, pen_obj.speed_cm_s * 10.0)
        draw_time_s = draw_mm / speed_mm_s
        travel_time_s = travel_mm / max(50.0, cfg.travel_speed_mm_s)
        actuation_time_s = len(opt_lines) * 2 * cfg.pen_actuation_time_s
        layer_duration_s = draw_time_s + travel_time_s + actuation_time_s

        layer = PlotLayer(
            pen_id=pen_id,
            pen=pen_obj,
            lines=opt_lines,
            travels=travels,
            draw_distance_mm=draw_mm,
            travel_distance_mm=travel_mm,
            unsorted_travel_mm=unsorted_travel_mm,
            estimated_duration_s=layer_duration_s,
        )
        job.layers[pen_id] = layer

        job.total_draw_mm += draw_mm
        job.total_travel_mm += travel_mm
        job.total_unsorted_travel_mm += unsorted_travel_mm
        job.estimated_duration_s += layer_duration_s
        job.total_points += layer.point_count

        # Build linear steps for simulation: segment by segment so curves and shapes
        # are drawn line-by-line during playback/scrubbing
        for idx, line in enumerate(opt_lines):
            # Travel step
            t_from, t_to = travels[idx]
            t_arr = np.array([t_from, t_to], dtype=np.float64)
            job.steps.append(PlotStep(action="TRAVEL", points=t_arr, pen_id=pen_id, step_index=step_counter))
            step_counter += 1

            # Draw steps: segment by segment
            for seg_idx in range(len(line) - 1):
                seg_pts = line[seg_idx : seg_idx + 2]
                job.steps.append(PlotStep(action="DRAW", points=seg_pts, pen_id=pen_id, step_index=step_counter))
                step_counter += 1

        if opt_lines:
            cur_sim_pos = (float(opt_lines[-1][-1, 0]), float(opt_lines[-1][-1, 1]))

    # Pen change overhead
    num_layers = len(job.layers)
    if num_layers > 1:
        job.pen_changes = num_layers - 1
        job.estimated_duration_s += job.pen_changes * cfg.pen_change_time_s

    return job
