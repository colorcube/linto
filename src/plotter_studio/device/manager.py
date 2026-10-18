"""Global Device Manager managing configured plotters and user settings persistence."""

from __future__ import annotations

import logging
from dataclasses import dataclass, asdict, fields
from pathlib import Path
from typing import List, Optional, Any, Callable
import yaml

from .profile import DeviceProfile, load_profile, get_default_profile
from .probe import list_serial_ports

logger = logging.getLogger("plotter_studio.device.manager")


class _EventSignal:
    """Lightweight pure-Python signal supporting .connect(), .disconnect(), and .emit()."""

    def __init__(self):
        self._callbacks: List[Callable[..., Any]] = []

    def connect(self, callback: Callable[..., Any]):
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def disconnect(self, callback: Callable[..., Any]):
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def emit(self, *args: Any, **kwargs: Any):
        for cb in list(self._callbacks):
            cb(*args, **kwargs)


AXIS_SCHEMA_VERSION = 2  # 2 = rotation/swap/invert are user corrections on top of the profile


@dataclass
class ConfiguredDevice:
    """User-configured plotter instance with connection settings and profile mapping.

    ``rotation``/``swap_xy``/``invert_x``/``invert_y`` are *corrections* on top of the
    profile's intrinsic axis mapping. Default: no correction.
    """
    id: str
    name: str
    model_id: str = "mutoh_xp500"
    port: str = "/dev/ttyUSB0"
    baudrate: int = 19200
    flow_control: str = "rtscts"  # "rtscts", "xonxoff", "none"
    margin_profile: str = "exp"
    rotation: int = 0
    swap_xy: bool = False
    invert_x: bool = False
    invert_y: bool = False
    probed_units_per_mm: Optional[float] = None
    axis_schema: int = AXIS_SCHEMA_VERSION

    def get_profile(self) -> DeviceProfile:
        """Load the associated DeviceProfile."""
        try:
            return load_profile(self.model_id)
        except Exception:
            return get_default_profile()


DEFAULT_DEVICES = [
    ConfiguredDevice(
        id="mutoh_xp500_usb",
        name="Mutoh XP-500 (Seriell)",
        model_id="mutoh_xp500",
        port="/dev/ttyUSB0",
        baudrate=19200,
        flow_control="rtscts",
        margin_profile="exp",
    ),
    ConfiguredDevice(
        id="mutoh_xp500_sim",
        name="Mutoh XP-500 Simulator (TCP)",
        model_id="mutoh_xp500",
        port="tcp://127.0.0.1:9999",
        baudrate=19200,
        flow_control="xonxoff",
        margin_profile="exp",
    ),
]


def _migrate_axis_settings(d: dict, prof: Optional[DeviceProfile]) -> None:
    """Convert pre-v2 absolute axis settings into corrections relative to the profile.

    Before v2 the device values *replaced* the profile mapping. Values that are all
    identity or equal to the profile mapping meant "no correction"; anything else is
    kept as an explicit correction.
    """
    if int(d.get("axis_schema", 1) or 1) >= AXIS_SCHEMA_VERSION:
        return
    old = (
        int(d.get("rotation", 0) or 0),
        bool(d.get("swap_xy", False)),
        bool(d.get("invert_x", False)),
        bool(d.get("invert_y", False)),
    )
    identity = (0, False, False, False)
    prof_axes = (
        (int(prof.rotation_deg or 0), bool(prof.swap_xy), bool(prof.invert_x), bool(prof.invert_y))
        if prof is not None else identity
    )
    if old in (identity, prof_axes):
        d["rotation"], d["swap_xy"], d["invert_x"], d["invert_y"] = identity
    else:
        logger.warning(
            "Device %s: keeping custom axis settings %s as correction on top of the profile; "
            "please verify with an orientation plot.", d.get("id", "?"), old,
        )
    d["axis_schema"] = AXIS_SCHEMA_VERSION


def _get_config_path() -> Path:
    """Return path to user's devices.yaml in ~/.config/plotter-studio/."""
    config_dir = Path.home() / ".config" / "plotter-studio"
    return config_dir / "devices.yaml"


class DeviceManager:
    """
    Central manager for configured plotters.
    Emits signals when active device or device list changes so all UI docks stay synchronized.
    """

    def __init__(self, config_path: Optional[Path] = None, parent: Optional[Any] = None):
        self.device_changed = _EventSignal()
        self.devices_updated = _EventSignal()
        self.config_path = config_path or _get_config_path()
        self.devices: List[ConfiguredDevice] = []
        self.active_device_id: str = ""
        self.load()

    def load(self):
        """Load device list and active selection from config file or initialize defaults."""
        migrated = False
        if self.config_path.is_file():
            try:
                data = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
                raw_devices = data.get("devices", [])
                self.devices = []
                for d in raw_devices:
                    prof = None
                    try:
                        prof = load_profile(d.get("model_id", "mutoh_xp500"))
                    except Exception:
                        pass
                    if "flow_control" not in d:
                        if prof is not None:
                            d["flow_control"] = prof.connection.flow_control
                        else:
                            d["flow_control"] = "xonxoff" if str(d.get("port", "")).startswith("tcp://") else "rtscts"
                    if str(d.get("flow_control", "")).lower() == "dsrdtr":
                        # pyserial has no DSR/DTR flow control on Linux; the XP-500 busy
                        # line is wired to the PC's CTS, so RTS/CTS is the right setting.
                        d["flow_control"] = "rtscts"
                        migrated = True
                    if int(d.get("axis_schema", 1) or 1) < AXIS_SCHEMA_VERSION:
                        _migrate_axis_settings(d, prof)
                        migrated = True
                    known = {f.name for f in fields(ConfiguredDevice)}
                    unknown = [k for k in d if k not in known]
                    if unknown:
                        logger.warning("Ignoring unknown device keys %s in %s", unknown, self.config_path)
                    dev_obj = ConfiguredDevice(**{k: v for k, v in d.items() if k in known})
                    if dev_obj.id == "mutoh_xp500_usb" and dev_obj.port.startswith("/dev/pts"):
                        dev_obj.port = "/dev/ttyUSB0"
                    self.devices.append(dev_obj)
                self.active_device_id = str(data.get("active_device_id", ""))
            except Exception as e:
                # Fallback to defaults on parse error
                logger.error("Could not read %s (%s) – using default devices", self.config_path, e)
                self.devices = [ConfiguredDevice(**asdict(d)) for d in DEFAULT_DEVICES]
                self.active_device_id = self.devices[0].id
                migrated = False
        else:
            self.devices = [ConfiguredDevice(**asdict(d)) for d in DEFAULT_DEVICES]
            # Try to auto-select detected USB serial port if available
            avail_usb = [p for p in list_serial_ports() if "ttyUSB" in p or "ttyACM" in p]
            if avail_usb:
                self.devices[0].port = avail_usb[0]
            self.active_device_id = self.devices[0].id
            self.save()

        # Ensure active_device_id is valid
        if not any(d.id == self.active_device_id for d in self.devices) and self.devices:
            self.active_device_id = self.devices[0].id

        if migrated:
            self.save()

    def save(self):
        """Persist current devices and active selection to config file."""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "active_device_id": self.active_device_id,
                "devices": [asdict(d) for d in self.devices],
            }
            self.config_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        except Exception:
            pass

    def get_active_device(self) -> ConfiguredDevice:
        """Return currently active device, or first device as fallback."""
        for d in self.devices:
            if d.id == self.active_device_id:
                return d
        if self.devices:
            return self.devices[0]
        # Fallback if list is empty
        fallback = ConfiguredDevice(**asdict(DEFAULT_DEVICES[0]))
        self.devices.append(fallback)
        self.active_device_id = fallback.id
        return fallback

    def set_active_device(self, device_id: str):
        """Set the active device by its ID and notify listeners."""
        if device_id != self.active_device_id:
            for d in self.devices:
                if d.id == device_id:
                    self.active_device_id = device_id
                    self.save()
                    self.device_changed.emit(d)
                    return

    def list_devices(self) -> List[ConfiguredDevice]:
        """Return a copy of the list of all configured devices."""
        return list(self.devices)

    def get_device(self, device_id: str) -> Optional[ConfiguredDevice]:
        """Get device by ID."""
        for d in self.devices:
            if d.id == device_id:
                return d
        return None

    def add_device(self, device: ConfiguredDevice):
        """Add a new configured device."""
        self.devices.append(device)
        self.save()
        self.devices_updated.emit()

    def update_device(self, device: ConfiguredDevice):
        """Update an existing device configuration."""
        for i, d in enumerate(self.devices):
            if d.id == device.id:
                self.devices[i] = device
                self.save()
                if self.active_device_id == device.id:
                    self.device_changed.emit(device)
                self.devices_updated.emit()
                return

    def delete_device(self, device_id: str):
        """Remove a device by ID."""
        self.devices = [d for d in self.devices if d.id != device_id]
        if self.active_device_id == device_id and self.devices:
            self.active_device_id = self.devices[0].id
            self.device_changed.emit(self.devices[0])
        self.save()
        self.devices_updated.emit()
