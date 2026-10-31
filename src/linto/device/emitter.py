"""HP-GL Emitter for LINTO.

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
    """Translates compiled PlotJob layers into HP-GL instructions.

    Axis handling has two layers:

    1. **Intrinsic device mapping** from the profile (``profile.swap_xy``,
       ``invert_x``, ``invert_y``, ``rotation_deg``). It describes the hardware,
       e.g. XP-500: X = paper feed, Y = carriage. Always applied.
    2. **User correction** (``swap_xy``, ``invert_x``, ``invert_y``,
       ``rotation_deg`` arguments). Applied on top in the centered sheet frame.
       Default: no correction.
    """

    def __init__(
        self,
        profile: DeviceProfile,
        margin_profile: str = "exp",
        points_per_cmd: int = 16,
        swap_xy: Optional[bool] = None,
        invert_x: Optional[bool] = None,
        invert_y: Optional[bool] = None,
        rotation_deg: Optional[int] = None,
        units_per_mm: Optional[float] = None,
        feed_edge: str = "top",
        include_handshake_init: bool = False,
        include_iw_clip: bool = False,
        send_pen_force: Optional[bool] = None,
    ):
        self.profile = profile
        self.margin_profile = margin_profile
        self.points_per_cmd = max(1, points_per_cmd)
        # User corrections (identity by default)
        self.swap_xy = bool(swap_xy)
        self.invert_x = bool(invert_x)
        self.invert_y = bool(invert_y)
        self.rotation_deg = int(rotation_deg or 0)
        self.units_per_mm = float(units_per_mm) if (units_per_mm is not None and units_per_mm > 0) else profile.units_per_mm
        self.feed_edge = feed_edge or "top"
        self.include_handshake_init = include_handshake_init
        self.include_iw_clip = include_iw_clip
        if send_pen_force is None:
            self.send_pen_force = not bool(getattr(profile, "auto_pen_force", False))
        else:
            self.send_pen_force = bool(send_pen_force)

    @staticmethod
    def _apply_axis_ops(
        x: float, y: float, rotation_deg: int, invert_x: bool, invert_y: bool, swap_xy: bool
    ) -> tuple[float, float]:
        """Rotate (CCW, degrees), then invert, then swap."""
        if rotation_deg % 360 != 0:
            rad = math.radians(rotation_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            x, y = x * cos_a - y * sin_a, x * sin_a + y * cos_a
        if invert_x:
            x = -x
        if invert_y:
            y = -y
        if swap_xy:
            x, y = y, x
        return x, y

    def to_plotter_units(
        self,
        x_mm: float,
        y_mm: float,
        sheet_w_mm: float,
        sheet_h_mm: float,
        center_mm: Optional[tuple[float, float]] = None,
    ) -> tuple[int, int]:
        """Convert sheet coordinates (mm, top-left origin) to plotter units."""
        if self.profile.origin == "center":
            if center_mm is not None:
                cx, cy = center_mm
            else:
                cx, cy = self.profile.calculate_center_mm(
                    sheet_w_mm, sheet_h_mm, self.margin_profile, feed_edge=self.feed_edge
                )
            # Base Cartesian coordinates relative to center:
            # +x_c is right, +y_c is up (since sheet y_mm has +Y down)
            x_c = x_mm - cx
            y_c = cy - y_mm
        else:
            # Bottom-left origin
            x_c = x_mm
            y_c = sheet_h_mm - y_mm

        # 1. User correction (identity by default)
        rx, ry = self._apply_axis_ops(
            x_c, y_c, self.rotation_deg, self.invert_x, self.invert_y, self.swap_xy
        )
        # 2. Intrinsic device mapping from the profile
        p = self.profile
        rx, ry = self._apply_axis_ops(
            rx, ry, int(p.rotation_deg or 0), bool(p.invert_x), bool(p.invert_y), bool(p.swap_xy)
        )

        px = int(round(rx * self.units_per_mm))
        py = int(round(ry * self.units_per_mm))
        return (px, py)

    def emit_commands(
        self,
        job: PlotJob,
        document: Optional[Document] = None,
    ) -> list[EmittedCommand]:
        """Generate structured commands with step indices for streaming & progress tracking."""
        sheet_w = getattr(document.page, "width_mm", getattr(document.page, "width", 420.0)) if document else 420.0
        sheet_h = getattr(document.page, "height_mm", getattr(document.page, "height", 297.0)) if document else 297.0

        center_mm: Optional[tuple[float, float]] = None
        if document and hasattr(document, "page") and document.page is not None:
            page = document.page
            # If Document.page has standard width_mm/height_mm (not legacy test attributes .width/.height override)
            if not (hasattr(page, "width") or hasattr(page, "height")) and hasattr(page, "plottable_box"):
                pb = page.plottable_box
                center_mm = (pb.center.x, pb.center.y)

        commands: list[EmittedCommand] = []

        # 1. Initialization
        init_prefix = "\x1b.R\r\x1b.(\r" if self.include_handshake_init else ""
        init_cmd = f"{init_prefix}IN;"
        if self.include_iw_clip and document and hasattr(document, "page") and hasattr(document.page, "plottable_box"):
            pb = document.page.plottable_box
            corners = [
                self.to_plotter_units(pb.min_x, pb.min_y, sheet_w, sheet_h, center_mm=center_mm),
                self.to_plotter_units(pb.max_x, pb.min_y, sheet_w, sheet_h, center_mm=center_mm),
                self.to_plotter_units(pb.max_x, pb.max_y, sheet_w, sheet_h, center_mm=center_mm),
                self.to_plotter_units(pb.min_x, pb.max_y, sheet_w, sheet_h, center_mm=center_mm),
            ]
            iw_x1 = min(c[0] for c in corners)
            iw_y1 = min(c[1] for c in corners)
            iw_x2 = max(c[0] for c in corners)
            iw_y2 = max(c[1] for c in corners)
            init_cmd += f"IW{iw_x1},{iw_y1},{iw_x2},{iw_y2};"

        commands.append(
            EmittedCommand(hpgl=f"{init_cmd}\r\n", step_index=0, pen=0, is_draw=False, dist_mm=0.0)
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
                    if getattr(self.profile, "decimal_speed", True) and abs(speed - round(speed)) > 1e-4:
                        cmd_str += f"VS{speed:g};"
                    else:
                        cmd_str += f"VS{int(round(speed))};"
                if self.send_pen_force and force is not None and force > 0:
                    if getattr(self.profile, "force_unit", "grams") == "hp_level" and force > 8:
                        fs_val = max(1, min(8, int(round(force / 25.0))))
                    else:
                        fs_val = int(round(force))
                    cmd_str += f"FS{fs_val};"

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
                if len(poly) < 1:
                    continue

                # Lift pen and travel to start point (PU)
                start_x, start_y = poly[0]
                u_x0, u_y0 = self.to_plotter_units(start_x, start_y, sheet_w, sheet_h, center_mm=center_mm)
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

                if len(poly) == 1:
                    commands.append(
                        EmittedCommand(
                            hpgl=f"PD{u_x0},{u_y0};\r\n",
                            step_index=global_step_idx,
                            pen=current_pen,
                            is_draw=True,
                            dist_mm=0.0,
                        )
                    )
                    global_step_idx += 1
                    continue

                # Segment into coordinate chains (PD x1,y1, x2,y2, ...)
                remaining_pts = poly[1:]
                prev_x, prev_y = start_x, start_y

                for i in range(0, len(remaining_pts), self.points_per_cmd):
                    chunk = remaining_pts[i:i + self.points_per_cmd]
                    chain_parts: list[str] = []
                    chunk_dist = 0.0

                    for pt in chunk:
                        px, py = pt
                        u_x, u_y = self.to_plotter_units(px, py, sheet_w, sheet_h, center_mm=center_mm)
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


def build_emitter(
    document: Optional[Document] = None,
    device: Optional[object] = None,
    margin_profile: Optional[str] = None,
    overrides: Optional[dict] = None,
) -> HPGLEmitter:
    """Build an HPGLEmitter with a consistent priority order:

    1. Profile defaults and document.page (margin_profile, feed_edge).
       The profile's intrinsic axis mapping is always applied by the emitter.
    2. Active ConfiguredDevice settings (profile, margin_profile, probed_units_per_mm,
       axis *corrections*, send_pen_force).
    3. Explicit margin_profile and GUI overrides (axis corrections rotation_deg,
       swap_xy, invert_x, invert_y, send_pen_force). These replace the device corrections.
    """
    from .profile import get_default_profile

    profile = get_default_profile()
    margin_key = "exp"
    feed_edge = "top"
    if document is not None and hasattr(document, "page") and document.page is not None:
        margin_key = getattr(document.page, "margin_profile", "exp") or "exp"
        feed_edge = getattr(document.page, "feed_edge", "top") or "top"

    units_override: Optional[float] = None
    emitter_opts: dict = {}

    if device is not None:
        if hasattr(device, "get_profile"):
            profile = device.get_profile()
        dev_margin = getattr(device, "margin_profile", None)
        if dev_margin:
            margin_key = dev_margin
        units_override = getattr(device, "probed_units_per_mm", None)
        if hasattr(device, "effective_send_pen_force"):
            send_force = device.effective_send_pen_force(profile)
        elif getattr(device, "send_pen_force", None) is not None:
            send_force = bool(getattr(device, "send_pen_force"))
        else:
            send_force = not bool(getattr(profile, "auto_pen_force", False))
        emitter_opts = {
            "rotation_deg": getattr(device, "rotation", 0),
            "swap_xy": getattr(device, "swap_xy", False),
            "invert_x": getattr(device, "invert_x", False),
            "invert_y": getattr(device, "invert_y", False),
            "send_pen_force": send_force,
        }

    if margin_profile:
        margin_key = margin_profile
    if overrides:
        emitter_opts.update(overrides)

    return HPGLEmitter(
        profile,
        margin_profile=margin_key,
        units_per_mm=units_override,
        feed_edge=feed_edge,
        **emitter_opts,
    )

