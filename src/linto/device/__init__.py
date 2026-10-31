"""Device management, HP-GL emitter, serial streaming and probing."""

from .profile import (
    DeviceProfile,
    DeviceConnectionConfig,
    load_profile,
    get_default_profile,
    get_margin_profile_items,
    list_available_profiles,
)
from .emitter import HPGLEmitter, EmittedCommand, build_emitter
from .probe import ProbeResult, list_serial_ports, probe_plotter
from .streamer import (
    SerialStreamer,
    StreamerState,
    Transport,
    SerialTransport,
    TcpTransport,
)
from .manager import DeviceManager, ConfiguredDevice, DEFAULT_DEVICES

__all__ = [
    "DeviceProfile",
    "DeviceConnectionConfig",
    "load_profile",
    "get_default_profile",
    "get_margin_profile_items",
    "list_available_profiles",
    "HPGLEmitter",
    "EmittedCommand",
    "build_emitter",
    "ProbeResult",
    "list_serial_ports",
    "probe_plotter",
    "SerialStreamer",
    "StreamerState",
    "Transport",
    "SerialTransport",
    "TcpTransport",
    "DeviceManager",
    "ConfiguredDevice",
    "DEFAULT_DEVICES",
]
