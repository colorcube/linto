"""Device profile data model and loader.

Defines plotter parameters, connection defaults, and coordinate settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import yaml


@dataclass
class DeviceConnectionConfig:
    baudrate: int = 19200
    bytesize: int = 8
    parity: str = "N"
    stopbits: int = 1
    rtscts: Optional[bool] = None
    xonxoff: Optional[bool] = None
    dsrdtr: Optional[bool] = None
    flow_control: str = ""

    def __post_init__(self) -> None:
        fc = (self.flow_control or "").strip().lower()
        if not fc:
            if self.xonxoff:
                fc = "xonxoff"
            elif self.dsrdtr:
                fc = "dsrdtr"
            elif self.rtscts is False:
                fc = "none"
            else:
                fc = "rtscts"
        self.flow_control = fc
        self.rtscts = (fc == "rtscts") if self.rtscts is None else bool(self.rtscts)
        self.xonxoff = (fc == "xonxoff") if self.xonxoff is None else bool(self.xonxoff)
        self.dsrdtr = (fc == "dsrdtr") if self.dsrdtr is None else bool(self.dsrdtr)


@dataclass
class DeviceProfile:
    model_id: str
    name: str
    manufacturer: str
    emulation: str = "HP-7585B"
    protocol: str = "hpgl"
    origin: str = "center"  # "center" or "bottom_left"
    units_per_mm: float = 40.0  # 0.025 mm / unit
    max_pens: int = 8
    max_speed_mm_s: float = 900.0
    travel_speed_mm_s: float = 900.0
    pen_change_time_s: float = 2.5
    pen_actuation_time_s: float = 0.04
    # Intrinsic axis mapping of the hardware (sheet frame -> plotter axes).
    # Always applied by the emitter; user corrections come on top.
    swap_xy: bool = False
    invert_x: bool = False
    invert_y: bool = False
    rotation_deg: int = 0
    connection: DeviceConnectionConfig = field(default_factory=DeviceConnectionConfig)
    margins_mm: dict[str, dict[str, float]] = field(default_factory=dict)
    default_margin_profile: str = "exp"
    force_unit: str = "grams"  # "grams" (10..500) or "hp_level" (1..8)
    decimal_speed: bool = True
    auto_pen_force: bool = False  # True if hardware detects pen type and sets pen force automatically

    @property
    def axes_swapped(self) -> bool:
        """True if plotter X runs along the sheet's vertical axis (e.g. XP-500: X = feed)."""
        quarter_turn = (int(self.rotation_deg or 0) % 180) == 90
        return bool(self.swap_xy) != quarter_turn

    def get_margins(self, profile_name: str = "") -> tuple[float, float, float, float]:
        """Return (top, bottom, left, right) margins in mm."""
        name = (profile_name or self.default_margin_profile).lower()
        if name in self.margins_mm:
            m = self.margins_mm[name]
            return (
                float(m.get("top", 25.0)),
                float(m.get("bottom", 5.0)),
                float(m.get("left", 5.0)),
                float(m.get("right", 5.0)),
            )
        # Default fallback
        return (25.0, 5.0, 5.0, 5.0)

    def calculate_center_mm(
        self,
        sheet_w_mm: float,
        sheet_h_mm: float,
        profile_name: str = "",
        feed_edge: str = "top",
    ) -> tuple[float, float]:
        """Return (center_x, center_y) of hard-clip window in sheet coordinates (mm)."""
        lead_m, trail_m, side_l, side_r = self.get_margins(profile_name)
        edge = (feed_edge or "top").lower()
        if edge == "bottom":
            top_m, bottom_m, left_m, right_m = trail_m, lead_m, side_l, side_r
        elif edge == "left":
            top_m, bottom_m, left_m, right_m = side_l, side_r, lead_m, trail_m
        elif edge == "right":
            top_m, bottom_m, left_m, right_m = side_l, side_r, trail_m, lead_m
        else:
            top_m, bottom_m, left_m, right_m = lead_m, trail_m, side_l, side_r

        hard_clip_w = max(1.0, sheet_w_mm - (left_m + right_m))
        hard_clip_h = max(1.0, sheet_h_mm - (top_m + bottom_m))

        center_x = left_m + (hard_clip_w / 2.0)
        center_y = top_m + (hard_clip_h / 2.0)
        return (center_x, center_y)


def _get_devices_dir() -> Path:
    from .. import RESOURCES_DIR

    return RESOURCES_DIR / "devices"


def load_profile(path_or_id: str | Path) -> DeviceProfile:
    """Load DeviceProfile from a YAML file path or model ID."""
    p = Path(path_or_id)
    if not p.is_file():
        # Check resources/devices/<id>.yaml
        candidate = _get_devices_dir() / f"{path_or_id}.yaml"
        if candidate.is_file():
            p = candidate
        else:
            raise FileNotFoundError(f"Device profile not found: {path_or_id}")

    data = yaml.safe_load(p.read_text(encoding="utf-8"))

    conn_data = data.get("connection", {})
    rtscts = bool(conn_data.get("rtscts", True))
    xonxoff = bool(conn_data.get("xonxoff", False))
    dsrdtr = bool(conn_data.get("dsrdtr", False))
    flow_ctrl = str(conn_data.get("flow_control", "")).lower()
    if not flow_ctrl:
        if xonxoff:
            flow_ctrl = "xonxoff"
        elif dsrdtr:
            flow_ctrl = "dsrdtr"
        elif rtscts:
            flow_ctrl = "rtscts"
        else:
            flow_ctrl = "none"

    conn = DeviceConnectionConfig(
        baudrate=int(conn_data.get("baudrate", 19200)),
        bytesize=int(conn_data.get("bytesize", 8)),
        parity=str(conn_data.get("parity", "N")),
        stopbits=int(conn_data.get("stopbits", 1)),
        rtscts=(flow_ctrl == "rtscts"),
        xonxoff=(flow_ctrl == "xonxoff"),
        dsrdtr=(flow_ctrl == "dsrdtr"),
        flow_control=flow_ctrl,
    )

    return DeviceProfile(
        model_id=str(data.get("model_id", p.stem)),
        name=str(data.get("name", "Unknown Plotter")),
        manufacturer=str(data.get("manufacturer", "Unknown")),
        emulation=str(data.get("emulation", "HP-7585B")),
        protocol=str(data.get("protocol", "hpgl")),
        origin=str(data.get("origin", "center")),
        units_per_mm=float(data.get("units_per_mm", 40.0)),
        max_pens=int(data.get("max_pens", 8)),
        max_speed_mm_s=float(data.get("max_speed_mm_s", 900.0)),
        travel_speed_mm_s=float(data.get("travel_speed_mm_s", 900.0)),
        pen_change_time_s=float(data.get("pen_change_time_s", 2.5)),
        pen_actuation_time_s=float(data.get("pen_actuation_time_s", 0.04)),
        swap_xy=bool(data.get("swap_xy", False)),
        invert_x=bool(data.get("invert_x", False)),
        invert_y=bool(data.get("invert_y", False)),
        rotation_deg=int(data.get("rotation_deg", 0)),
        connection=conn,
        margins_mm=data.get("margins_mm", {}),
        default_margin_profile=str(data.get("default_margin_profile", "exp")),
        force_unit=str(data.get("force_unit", "grams")).lower(),
        decimal_speed=bool(data.get("decimal_speed", True)),
        auto_pen_force=bool(data.get("auto_pen_force", False)),
    )


def get_default_profile() -> DeviceProfile:
    """Return the default Mutoh XP-500 profile."""
    try:
        return load_profile("mutoh_xp500")
    except Exception:
        # Hardcoded fallback if yaml missing
        return DeviceProfile(
            model_id="mutoh_xp500",
            name="Mutoh XP-500",
            manufacturer="Mutoh",
            swap_xy=True,
            invert_x=False,
            invert_y=True,
            auto_pen_force=True,
            margins_mm={
                "exp": {"top": 25.0, "bottom": 5.0, "left": 5.0, "right": 5.0},
                "norm": {"top": 35.0, "bottom": 15.0, "left": 15.0, "right": 15.0},
                "type1": {"top": 25.0, "bottom": 5.0, "left": 11.0, "right": 11.0},
                "type3": {"top": 25.0, "bottom": 10.0, "left": 10.0, "right": 10.0},
            },
        )


_MARGIN_PROFILE_LABELS: dict[str, str] = {
    "exp": "EXP (Erweitert",
    "norm": "NORM (Normal",
    "type1": "TYPE1 (",
    "type3": "TYPE3 (",
}


def get_margin_profile_items(profile: Optional[DeviceProfile] = None) -> list[tuple[str, str]]:
    """Return list of (display_label, profile_key) derived from the DeviceProfile YAML."""
    prof = profile or get_default_profile()
    keys = list(prof.margins_mm.keys()) if prof.margins_mm else ["exp", "norm", "type1", "type3"]
    items: list[tuple[str, str]] = []
    for key in keys:
        k_low = key.lower()
        top_m, bottom_m, left_m, right_m = prof.get_margins(k_low)
        dims = f"{top_m:.0f} / {bottom_m:.0f} / {left_m:.0f} / {right_m:.0f} mm"
        prefix = _MARGIN_PROFILE_LABELS.get(k_low)
        if prefix:
            sep = ": " if not prefix.endswith("(") else ""
            label = f"{prefix}{sep}{dims})"
        else:
            label = f"{k_low.upper()} ({dims})"
        items.append((label, k_low))
    return items


def list_available_profiles() -> list[DeviceProfile]:
    """Scan resources/devices/ and return all valid DeviceProfiles."""
    profiles: list[DeviceProfile] = []
    d = _get_devices_dir()
    if d.is_dir():
        for yaml_file in sorted(d.glob("*.yaml")):
            try:
                profiles.append(load_profile(yaml_file))
            except Exception:
                pass
    if not profiles:
        profiles.append(get_default_profile())
    return profiles
