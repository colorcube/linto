"""CLI entry point for Mutoh XP-500 Software Emulator.

Usage:
    python -m plotter_studio.emulator
    python -m plotter_studio.emulator --paper A2 --buffer small --symlink ./virtual_plotter
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

from .virtual_plotter import VirtualPlotter
from .server import PtyServer, TcpServer
from .svg_recorder import export_plotter_svg


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mutoh XP-500 Plotter Emulator (HP-7585B RS-232 / PTY Simulation)"
    )
    parser.add_argument(
        "--paper",
        choices=["A4", "A3", "A2", "A1", "A0"],
        default="A3",
        help="Simulated paper format (default: A3)",
    )
    parser.add_argument(
        "--margin",
        choices=["EXP", "NORM", "TYPE1", "TYPE3"],
        default="EXP",
        help="Hard-clip margin profile according to Fig. 7.3 (default: EXP)",
    )
    parser.add_argument(
        "--buffer",
        choices=["small", "large"],
        default="small",
        help="Input buffer size: small (1000 chars) or large (1 MB) (default: small)",
    )
    parser.add_argument(
        "--unit",
        type=float,
        default=0.025,
        help="Unit resolution in mm: 0.025 (40 units/mm) or 0.010 (100 units/mm) (default: 0.025)",
    )
    parser.add_argument(
        "--symlink",
        type=str,
        default="./virtual_plotter",
        help="Symlink path pointing to the slave PTY device (default: ./virtual_plotter)",
    )
    parser.add_argument(
        "--tcp",
        type=int,
        default=None,
        help="Run as TCP server on given port instead of PTY (e.g. 9999)",
    )
    parser.add_argument(
        "--realtime",
        action="store_true",
        help="Simulate realistic mechanical pen motion delay",
    )
    parser.add_argument(
        "--speedup",
        type=float,
        default=5.0,
        help="Realtime motion speedup multiplier (default: 5.0)",
    )
    parser.add_argument(
        "--svg-output",
        type=str,
        default="./emulator_output.svg",
        help="File path to save drawn paths as SVG on exit (default: ./emulator_output.svg)",
    )

    args = parser.parse_args()

    buf_size = 1000 if args.buffer == "small" else 1048576

    plotter = VirtualPlotter(
        paper=args.paper,
        margin_profile=args.margin,
        buffer_size=buf_size,
        resolution_mm=args.unit,
        realtime=args.realtime,
        speedup=args.speedup,
    )

    if args.tcp:
        server = TcpServer(plotter, port=args.tcp)
        conn_str = server.start()
    else:
        server = PtyServer(plotter, symlink_path=args.symlink)
        conn_str = server.start()

    print("=" * 64)
    print(" 🖋️  Mutoh XP-500 Plotter Emulator (HP-7585B Simulation)")
    print("=" * 64)
    print(f" Format:           {plotter.paper} ({plotter.sheet_width_mm:.0f} x {plotter.sheet_height_mm:.0f} mm)")
    print(f" Ränder (Profil):  {args.margin} ({plotter.plottable_width_mm:.1f} x {plotter.plottable_height_mm:.1f} mm Hard-Clip)")
    print(f" Auflösung:        {args.unit} mm/Unit ({plotter.units_per_mm:.0f} Units/mm)")
    print(f" Puffer:           {args.buffer.upper()} ({plotter.buffer_size:,} Bytes)")
    print(f" Verbindung:       {conn_str}")
    if args.realtime:
        print(f" Mechanik:         Echtzeit-Simulation ({args.speedup:.1f}x Speedup)")
    else:
        print(f" Mechanik:         Sofortige Abarbeitung (Fast-Mode)")
    print("=" * 64)
    print("Warte auf Befehle... (Drücke Strg+C zum Beenden)\n")

    def handle_exit(signum, frame):
        print("\nBeende Emulator...")
        server.stop()
        if plotter.recorded_polylines:
            out_svg = Path(args.svg_output)
            export_plotter_svg(plotter, out_svg)
            print(f"📁 Plot-Ergebnis gespeichert als: {out_svg.resolve()}")
        print(f"Statistik:")
        print(f"  Empfangen:     {plotter.stats.bytes_received:,} Bytes")
        print(f"  Gesendet:      {plotter.stats.bytes_sent:,} Bytes")
        print(f"  Befehle:       {plotter.stats.commands_executed:,}")
        print(f"  Zeichenweg:    {plotter.stats.drawn_distance_mm / 1000.0:.2f} m")
        print(f"  Leerweg:       {plotter.stats.travel_distance_mm / 1000.0:.2f} m")
        print(f"  Stiftwechsel:  {plotter.stats.pen_changes}")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)

    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        handle_exit(None, None)

    return 0


if __name__ == "__main__":
    sys.exit(main())
