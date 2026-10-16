"""Serial port discovery and plotter inquiry.

Probes devices for HP-7585B / Mutoh XP-500 identification (OI, OF, OH).
"""

from __future__ import annotations

import re
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import serial
import serial.tools.list_ports


@dataclass
class ProbeResult:
    port: str
    success: bool
    model: str = ""
    units_per_mm: float = 40.0
    hard_clip_units: Optional[tuple[int, int, int, int]] = None
    hard_clip_mm: Optional[tuple[float, float]] = None
    detected_format: str = ""
    error_message: str = ""
    cts: Optional[bool] = None
    dsr: Optional[bool] = None

    @property
    def error(self) -> str:
        return self.error_message


# Approximate hard-clip width ranges for format detection (mm)
FORMAT_RANGES = {
    "A4": (250.0, 310.0),
    "A3": (360.0, 430.0),
    "A2": (550.0, 620.0),
    "A1": (780.0, 870.0),
    "A0": (1100.0, 1220.0),
}


def list_serial_ports() -> list[str]:
    """Scan and list all available serial ports, including virtual plotter symlinks."""
    ports: list[str] = []

    # 1. Virtual plotter check
    vplotter = Path("./virtual_plotter")
    if vplotter.exists() or vplotter.is_symlink():
        ports.append(str(vplotter.resolve()))

    # 2. System serial ports
    for p in serial.tools.list_ports.comports():
        dev = p.device
        if dev not in ports:
            ports.append(dev)

    # 3. Always ensure standard serial port option exists
    if "/dev/ttyUSB0" not in ports:
        ports.append("/dev/ttyUSB0")

    # 4. Add default TCP option
    ports.append("tcp://127.0.0.1:9999")

    return ports


def probe_plotter(
    port: str,
    baudrate: int = 19200,
    timeout: Optional[float] = None,
) -> ProbeResult:
    """Send inquiry commands (OI, OF, OH) and detect plotter configuration."""
    port_clean = port.strip()
    effective_timeout = timeout if timeout is not None else max(0.8, (50.0 * 10.0 / max(1, baudrate)) + 0.5)

    try:
        raw_resp = bytearray()

        cts_val: Optional[bool] = None
        dsr_val: Optional[bool] = None

        if port_clean.startswith("tcp://"):
            # TCP connection
            host_port = port_clean[6:].split(":")
            host = host_port[0]
            tcp_port = int(host_port[1]) if len(host_port) > 1 else 9999
            with socket.create_connection((host, tcp_port), timeout=effective_timeout) as sock:
                sock.settimeout(effective_timeout)
                sock.sendall(b"OI;OF;OH;\r")
                start = time.time()
                while time.time() - start < effective_timeout:
                    try:
                        chunk = sock.recv(1024)
                        if chunk:
                            raw_resp.extend(chunk)
                            if raw_resp.count(b"\r") >= 3:
                                break
                    except socket.timeout:
                        break
        else:
            # Serial connection
            with serial.Serial(
                port_clean,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                rtscts=False,  # Non-blocking probe without handshake stall
                timeout=effective_timeout,
                write_timeout=effective_timeout,
            ) as ser:
                try:
                    cts_val = bool(ser.cts)
                    dsr_val = bool(ser.dsr)
                except Exception:
                    pass
                ser.reset_input_buffer()
                ser.write(b"OI;OF;OH;\r")
                start = time.time()
                while time.time() - start < effective_timeout:
                    chunk = ser.read(128)
                    if chunk:
                        raw_resp.extend(chunk)
                        if raw_resp.count(b"\r") >= 3:
                            break

        resp_str = raw_resp.decode("ascii", errors="replace")
        parts = [p.strip() for p in resp_str.replace("\n", "").split("\r") if p.strip()]

        if not parts:
            err = "Keine Antwort vom Plotter (Timeout)"
            if cts_val is False:
                err += " – Hinweis: CTS ist LOW (Plotter offline/pausiert oder Kabel ohne Handshake-Leitung)"
            return ProbeResult(
                port=port_clean,
                success=False,
                error_message=err,
                cts=cts_val,
                dsr=dsr_val,
            )

        model = parts[0] if len(parts) > 0 else "Unknown"

        # Units per mm from OF (e.g. "40,40")
        units_per_mm = 40.0
        if len(parts) > 1:
            of_match = re.match(r"^(\d+)[, ](\d+)", parts[1])
            if of_match:
                units_per_mm = float(of_match.group(1))

        # Hard-clip window from OH (e.g. "-7800,-5740,7800,5740")
        hard_clip_units = None
        hard_clip_mm = None
        detected_fmt = "Unbekannt"

        if len(parts) > 2:
            oh_tokens = [int(t) for t in re.findall(r"-?\d+", parts[2])]
            if len(oh_tokens) >= 4:
                xmin, ymin, xmax, ymax = oh_tokens[:4]
                hard_clip_units = (xmin, ymin, xmax, ymax)
                w_mm = abs(xmax - xmin) / units_per_mm
                h_mm = abs(ymax - ymin) / units_per_mm
                hard_clip_mm = (w_mm, h_mm)

                # Format estimation
                larger_dim = max(w_mm, h_mm)
                for fmt, (f_min, f_max) in FORMAT_RANGES.items():
                    if f_min <= larger_dim <= f_max:
                        detected_fmt = fmt
                        break

        return ProbeResult(
            port=port_clean,
            success=True,
            model=model,
            units_per_mm=units_per_mm,
            hard_clip_units=hard_clip_units,
            hard_clip_mm=hard_clip_mm,
            detected_format=detected_fmt,
            cts=cts_val,
            dsr=dsr_val,
        )

    except Exception as e:
        return ProbeResult(
            port=port_clean,
            success=False,
            error_message=str(e),
            cts=cts_val if 'cts_val' in locals() else None,
            dsr=dsr_val if 'dsr_val' in locals() else None,
        )
