#!/usr/bin/env python3
"""Hardware inquiry and diagnostic tool for Mutoh XP-500 (and HP-7585B compatible plotters).

Performs all verification queries specified in docs/devices/mutoh-xp500/testplan.md:
- Serial modem signals (CTS, DSR)
- Standard inquiries: OI, OF, OH, OS, OE, OA, OO, OT
- Extended ESC sequences: ESC.A, ESC.L, ESC.B, ESC.O, ESC.E
- Optional raw command dispatch and minimal test line
"""

import argparse
import re
import socket
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

import serial
import serial.tools.list_ports

# Add src to pythonpath so plotter_studio modules can be imported if needed
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from plotter_studio.device.probe import FORMAT_RANGES, list_serial_ports


def send_query(
    conn,
    query_bytes: bytes,
    timeout: float = 0.8,
    is_tcp: bool = False,
    terminator: bytes = b"\r",
) -> str:
    """Send query and read response until terminator or timeout."""
    if is_tcp:
        conn.settimeout(timeout)
        try:
            conn.sendall(query_bytes)
            start = time.time()
            buf = bytearray()
            while time.time() - start < timeout:
                chunk = conn.recv(256)
                if not chunk:
                    break
                buf.extend(chunk)
                if terminator in buf:
                    break
            return buf.decode("ascii", errors="replace").strip()
        except socket.timeout:
            return ""
    else:
        conn.timeout = timeout
        conn.reset_input_buffer()
        conn.write(query_bytes)
        start = time.time()
        buf = bytearray()
        while time.time() - start < timeout:
            chunk = conn.read(64)
            if chunk:
                buf.extend(chunk)
                if terminator in buf:
                    break
        return buf.decode("ascii", errors="replace").strip()


def run_diagnostics(port: str, baudrate: int = 19200, timeout: float = 0.8, raw_cmd: Optional[str] = None):
    print("=" * 65)
    print("  PLOTTER STUDIO – Mutoh XP-500 Hardware-Diagnose (AP0)")
    print("=" * 65)
    print(f"Ziel:      {port}")
    print(f"Baudrate:  {baudrate}")
    print(f"Timeout:   {timeout} s")
    print("-" * 65)

    is_tcp = port.startswith("tcp://")
    conn = None
    cts = None
    dsr = None

    try:
        if is_tcp:
            hp = port[6:].split(":")
            host = hp[0]
            tport = int(hp[1]) if len(hp) > 1 else 9999
            conn = socket.create_connection((host, tport), timeout=timeout)
            print("Verbindung: TCP-Socket erfolgreich hergestellt.")
        else:
            conn = serial.Serial(
                port,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                rtscts=False,  # Don't block if CTS is low during query
                timeout=timeout,
                write_timeout=timeout,
            )
            try:
                cts = conn.cts
                dsr = conn.dsr
            except Exception:
                pass
            print(f"Verbindung: Serieller Port geöffnet. Signals: CTS={cts}, DSR={dsr}")
            if cts is False:
                print("⚠️  WARNUNG: CTS ist LOW! Der Plotter meldet Puffer voll oder ist offline/pausiert.")

        if raw_cmd:
            print(f"\nSende Rohbefehl: {raw_cmd!r}")
            cmd_bytes = raw_cmd.encode("ascii")
            if not cmd_bytes.endswith(b"\r") and not cmd_bytes.endswith(b";"):
                cmd_bytes += b";"
            if not cmd_bytes.endswith(b"\r"):
                cmd_bytes += b"\r"
            resp = send_query(conn, cmd_bytes, timeout=timeout, is_tcp=is_tcp)
            print(f"Antwort: {resp!r}")
            return

        print("\nAbfrage-Ergebnisse:")
        print("-" * 65)

        queries = [
            ("OI;", "Modell-Identifikation (Standard)", "Erwartet z.B. 7585B oder XP-500"),
            ("OF;", "Zeicheneinheit (Units/mm)", "Erwartet z.B. 40,40 (= 0,025 mm)"),
            ("OH;", "Plottbereich / Hard-Clip", "Erwartet min_x,min_y,max_x,max_y"),
            ("OS;", "Statusbyte", "Bitmaske für Plotterzustand"),
            ("OE;", "Fehlerstatus (HP-GL)", "0 = Kein Fehler"),
            ("OA;", "Aktuelle Position & Stift", "X,Y,Stiftstatus"),
            ("OT;", "Stiftkarussell-Status", "Stiftbelegung"),
            ("OO;", "Optionen", "Hardware-Optionen"),
            ("\x1b.A", "ESC.A (Erweiterte ID)", "Modellspezifisch"),
            ("\x1b.L", "ESC.L (Puffergröße)", "Puffergröße in Bytes (1000 oder 1MB)"),
            ("\x1b.B", "ESC.B (Freier Puffer)", "Verfügbarer Puffer"),
            ("\x1b.O", "ESC.O (Erweiterter Status)", "Mutoh Status"),
            ("\x1b.E", "ESC.E (Erweiterter Fehler)", "0 = Kein Fehler"),
        ]

        results = {}
        for cmd, name, hint in queries:
            cmd_repr = cmd.replace("\x1b", "ESC")
            resp = send_query(conn, cmd.encode("ascii"), timeout=timeout, is_tcp=is_tcp)
            results[cmd] = resp
            status_symbol = "✓" if resp else "—"
            print(f"{cmd_repr:<8} | {name:<30} | {resp or '(keine Antwort)'}")

        print("-" * 65)
        print("\nAuswertung:")

        # 1. Modell
        oi = results.get("OI;", "")
        print(f"• Modell:        {oi or 'Unbekannt'}")

        # 2. Units / Auflösung
        of = results.get("OF;", "")
        units_mm = 40.0
        if of:
            m = re.match(r"^(\d+)[, ](\d+)", of)
            if m:
                units_mm = float(m.group(1))
                step_size = 1.0 / units_mm
                print(f"• Auflösung:     {units_mm} Units/mm (Schrittweite: {step_size:.4f} mm)")

        # 3. Hard-Clip & Papierformat
        oh = results.get("OH;", "")
        if oh:
            tokens = [int(t) for t in re.findall(r"-?\d+", oh)]
            if len(tokens) >= 4:
                xmin, ymin, xmax, ymax = tokens[:4]
                w_mm = abs(xmax - xmin) / units_mm
                h_mm = abs(ymax - ymin) / units_mm
                fmt = "Unbekannt"
                larger = max(w_mm, h_mm)
                for f_name, (f_min, f_max) in FORMAT_RANGES.items():
                    if f_min <= larger <= f_max:
                        fmt = f_name
                        break
                print(f"• Hard-Clip:     X: [{xmin}, {xmax}], Y: [{ymin}, {ymax}] Units")
                print(f"• Abmessungen:   {w_mm:.1f} × {h_mm:.1f} mm (Plottbarer Bereich)")
                print(f"• Erkanntes Blatt: DIN {fmt}")

        # 4. Puffer
        esc_l = results.get("\x1b.L", "")
        esc_b = results.get("\x1b.B", "")
        if esc_l or esc_b:
            print(f"• Puffer:        Gesamt: {esc_l or '?'} Bytes, Frei: {esc_b or '?'} Bytes")

        print("=" * 65)

    except Exception as e:
        print(f"\n❌ FEHLER: {e}", file=sys.stderr)
    finally:
        if conn:
            if not is_tcp:
                try:
                    conn.reset_output_buffer()
                except Exception:
                    pass
            conn.close()


def main():
    parser = argparse.ArgumentParser(description="Mutoh XP-500 Hardware Inquiry & Diagnostics (AP0)")
    parser.add_argument("port", nargs="?", help="Serieller Port (z.B. /dev/ttyUSB0) oder TCP (tcp://127.0.0.1:9999)")
    parser.add_argument("--baud", type=int, default=19200, help="Baudrate (Standard: 19200)")
    parser.add_argument("--timeout", type=float, default=0.6, help="Timeout in Sekunden (Standard: 0.6)")
    parser.add_argument("--raw", type=str, help="Beliebigen Rohbefehl senden und Antwort anzeigen")
    parser.add_argument("--list-ports", action="store_true", help="Alle erkannten Schnittstellen auflisten")

    args = parser.parse_args()

    if args.list_ports or not args.port:
        available = list_serial_ports()
        print("Gefundene Schnittstellen:")
        for i, p in enumerate(available, 1):
            print(f"  [{i}] {p}")
        if not args.port:
            if available:
                args.port = available[0]
                print(f"\nKein Port angegeben. Verwende Standard: {args.port}")
            else:
                print("\nKeine seriellen Schnittstellen gefunden.", file=sys.stderr)
                sys.exit(1)

    run_diagnostics(args.port, baudrate=args.baud, timeout=args.timeout, raw_cmd=args.raw)


if __name__ == "__main__":
    main()
