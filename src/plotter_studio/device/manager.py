"""Global Device Manager managing configured plotters and user settings persistence."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from pathlib import Path
from typing import List, Optional, Any, Callable
import yaml

from .profile import DeviceProfile, load_profile, get_default_profile
from .probe import list_serial_ports


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


@dataclass
class ConfiguredDevice:
    """User-configured plotter instance with connection settings and profile mapping."""
    id: str
    name: str
    model_id: str = "mutoh_xp500"
    port: str = "/dev/ttyUSB0"
    baudrate: int = 19200
    flow_control: str = "rtscts"  # "rtscts", "dsrdtr", "xonxoff", "none"
    margin_profile: str = "exp"
    rotation: int = 0
    swap_xy: bool = True
    invert_x: bool = False
    invert_y: bool = True
    probed_units_per_mm: Optional[float] = None

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
        swap_xy=True,
        invert_x=False,
        invert_y=True,
    ),
    ConfiguredDevice(
        id="mutoh_xp500_sim",
        name="Mutoh XP-500 Simulator (TCP)",
        model_id="mutoh_xp500",
        port="tcp://127.0.0.1:9999",
        baudrate=19200,
        flow_control="xonxoff",
        margin_profile="exp",
        swap_xy=True,
        invert_x=False,
        invert_y=True,
    ),
]


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
                    if prof is not None:
                        if "swap_xy" not in d:
                            d["swap_xy"] = prof.swap_xy
                        if "invert_x" not in d:
                            d["invert_x"] = prof.invert_x
                        if "invert_y" not in d:
                            d["invert_y"] = prof.invert_y
                        if "rotation" not in d:
                            d["rotation"] = prof.rotation_deg
                    dev_obj = ConfiguredDevice(**d)
                    if dev_obj.id == "mutoh_xp500_usb" and dev_obj.port.startswith("/dev/pts"):
                        dev_obj.port = "/dev/ttyUSB0"
                    self.devices.append(dev_obj)
                self.active_device_id = str(data.get("active_device_id", ""))
            except Exception as e:
                # Fallback to defaults on parse error
                self.devices = [ConfiguredDevice(**asdict(d)) for d in DEFAULT_DEVICES]
                self.active_device_id = self.devices[0].id
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
