"""Device management, HP-GL emitter, serial streaming and probing."""

from .profile import DeviceProfile, DeviceConnectionConfig, load_profile, get_default_profile, list_available_profiles
from .emitter import HPGLEmitter, EmittedCommand
from .probe import ProbeResult, list_serial_ports, probe_plotter
from .streamer import SerialStreamer, StreamerState
from .manager import DeviceManager, ConfiguredDevice, DEFAULT_DEVICES

__all__ = [
    "DeviceProfile",
    "DeviceConnectionConfig",
    "load_profile",
    "get_default_profile",
    "list_available_profiles",
    "HPGLEmitter",
    "EmittedCommand",
    "ProbeResult",
    "list_serial_ports",
    "probe_plotter",
    "SerialStreamer",
    "StreamerState",
    "DeviceManager",
    "ConfiguredDevice",
    "DEFAULT_DEVICES",
]
