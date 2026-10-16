"""HP-GL Emitter for Plotter Studio.

Converts a compiled PlotJob into optimized HP-GL command streams, mapping
sheet coordinates (mm) to plotter units (center-origin or corner-origin).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..pipeline.compiler import PlotJob
    from ..core.document import Document
    from .profile import DeviceProfile


@dataclass
class EmittedCommand:
    hpgl: str
    step_index: int
    pen: int
    is_draw: bool
    dist_mm: float


class HPGLEmitter:
    """Translates compiled PlotJob layers into HP-GL instructions."""

    def __init__(
        self,
        profile: DeviceProfile,
        margin_profile: str = "exp",
        points_per_cmd: int = 16,
        swap_xy: Optional[bool] = None,
        invert_x: Optional[bool] = None,
        invert_y: Optional[bool] = None,
        rotation_deg: Optional[int] = None,
    ):
        self.profile = profile
        self.margin_profile = margin_profile
        self.points_per_cmd = max(1, points_per_cmd)
        self.swap_xy = profile.swap_xy if swap_xy is None else swap_xy
        self.invert_x = profile.invert_x if invert_x is None else invert_x
        self.invert_y = profile.invert_y if invert_y is None else invert_y
        self.rotation_deg = profile.rotation_deg if rotation_deg is None else rotation_deg

    def to_plotter_units(
        self,
        x_mm: float,
        y_mm: float,
        sheet_w_mm: float,
        sheet_h_mm: float,
    ) -> tuple[int, int]:
        """Convert sheet coordinates (mm, top-left origin) to plotter units."""
        if self.profile.origin == "center":
            cx, cy = self.profile.calculate_center_mm(sheet_w_mm, sheet_h_mm, self.margin_profile)
            # Base Cartesian coordinates relative to center:
            # +x_c is right, +y_c is up (since sheet y_mm has +Y down)
            x_c = x_mm - cx
            y_c = cy - y_mm
        else:
            # Bottom-left origin
            x_c = x_mm
            y_c = sheet_h_mm - y_mm

        # 1. Apply rotation around origin
        if self.rotation_deg % 360 != 0:
            rad = math.radians(self.rotation_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            rx = x_c * cos_a - y_c * sin_a
            ry = x_c * sin_a + y_c * cos_a
        else:
            rx, ry = x_c, y_c

        # 2. Invert axes if requested
        if self.invert_x:
            rx = -rx
        if self.invert_y:
            ry = -ry

        # 3. Swap axes if requested
        if self.swap_xy:
            rx, ry = ry, rx

        px = int(round(rx * self.profile.units_per_mm))
        py = int(round(ry * self.profile.units_per_mm))
        return (px, py)

    def emit_commands(
        self,
        job: PlotJob,
        document: Optional[Document] = None,
    ) -> list[EmittedCommand]:
        """Generate structured commands with step indices for streaming & progress tracking."""
        sheet_w = getattr(document.page, "width_mm", getattr(document.page, "width", 420.0)) if document else 420.0
        sheet_h = getattr(document.page, "height_mm", getattr(document.page, "height", 297.0)) if document else 297.0

        commands: list[EmittedCommand] = []

        # 1. Initialization
        commands.append(
            EmittedCommand(hpgl="IN;\r\n", step_index=0, pen=0, is_draw=False, dist_mm=0.0)
        )

        global_step_idx = 0
        current_pen = 0

        # Pen configuration map from document
        pen_settings: dict[int, tuple[Optional[float], Optional[float]]] = {}
        if document:
            for p in document.pens:
                pen_nr = getattr(p, "pen_id", getattr(p, "number", 1))
                speed = getattr(p, "speed_cm_s", None)
                force = getattr(p, "force_g", getattr(p, "force", None))
                pen_settings[pen_nr] = (speed, force)

        # 2. Iterate through each pen layer
        layers = job.layers.values() if isinstance(job.layers, dict) else job.layers
        for layer in layers:
            lines = getattr(layer, "lines", None)
            if lines is None:
                lines = getattr(layer, "polylines", [])
            if not lines:
                continue

            pen_nr = getattr(layer, "pen_id", getattr(layer, "pen_number", 1))

            # Select Pen if changed
            if pen_nr != current_pen:
                current_pen = pen_nr
                cmd_str = f"SP{pen_nr};"

                # Pen speed and force
                speed, force = pen_settings.get(pen_nr, (None, None))
                if speed is not None and speed > 0:
                    cmd_str += f"VS{int(round(speed))};"
                if force is not None and force > 0:
                    cmd_str += f"FS{int(round(force))};"

                commands.append(
                    EmittedCommand(
                        hpgl=cmd_str + "\r\n",
                        step_index=global_step_idx,
                        pen=current_pen,
                        is_draw=False,
                        dist_mm=0.0,
                    )
                )

            # Draw each polyline
            for poly in lines:
                if len(poly) < 2:
                    continue

                # Lift pen and travel to start point (PU)
                start_x, start_y = poly[0]
                u_x0, u_y0 = self.to_plotter_units(start_x, start_y, sheet_w, sheet_h)
                commands.append(
                    EmittedCommand(
                        hpgl=f"PU{u_x0},{u_y0};\r\n",
                        step_index=global_step_idx,
                        pen=current_pen,
                        is_draw=False,
                        dist_mm=0.0,
                    )
                )
                global_step_idx += 1

                # Segment into coordinate chains (PD x1,y1, x2,y2, ...)
                remaining_pts = poly[1:]
                prev_x, prev_y = start_x, start_y

                for i in range(0, len(remaining_pts), self.points_per_cmd):
                    chunk = remaining_pts[i:i + self.points_per_cmd]
                    chain_parts: list[str] = []
                    chunk_dist = 0.0

                    for pt in chunk:
                        px, py = pt
                        u_x, u_y = self.to_plotter_units(px, py, sheet_w, sheet_h)
                        chain_parts.append(f"{u_x},{u_y}")
                        chunk_dist += math.hypot(px - prev_x, py - prev_y)
                        prev_x, prev_y = px, py

                    commands.append(
                        EmittedCommand(
                            hpgl=f"PD{','.join(chain_parts)};\r\n",
                            step_index=global_step_idx,
                            pen=current_pen,
                            is_draw=True,
                            dist_mm=chunk_dist,
                        )
                    )
                    global_step_idx += len(chunk)

        # 3. Finalization: lift pen and park
        commands.append(
            EmittedCommand(
                hpgl="PU;SP0;\r\n",
                step_index=global_step_idx,
                pen=0,
                is_draw=False,
                dist_mm=0.0,
            )
        )

        return commands

    def emit_string(self, job: PlotJob, document: Optional[Document] = None) -> str:
        """Produce full HP-GL output string."""
        cmds = self.emit_commands(job, document)
        return "".join(c.hpgl for c in cmds)
