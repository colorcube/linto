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
        "--baudrate",
        type=int,
        default=None,
        help="Simulated serial baud rate for data transfer throttling (e.g. 300, 1200, 9600, 19200; default: unlimited)",
    )
    parser.add_argument(
        "--svg-output",
        type=str,
        default="./emulator_output.svg",
        help="File path to save drawn paths as SVG on exit (default: ./emulator_output.svg)",
    )

    args = parser.parse_args()

    buf_size = 1000 if args.buffer == "small" else 1048576

    out_svg_path = Path(args.svg_output).resolve()
    last_saved_count = [0]

    def on_plotter_event(event_type: str, data: dict):
        timestamp = time.strftime("%H:%M:%S")
        if event_type == "inquiry":
            cmd = data.get("cmd", "")
            resp = data.get("response", "")
            if cmd == "OI":
                print(f"[{timestamp}] 🔍 Inquiry 'OI' -> {resp} (Modellkennung)")
            elif cmd == "OF":
                print(f"[{timestamp}] 🔍 Inquiry 'OF' -> {resp} (40 Units/mm)")
            elif cmd == "OH":
                print(f"[{timestamp}] 🔍 Inquiry 'OH' -> {resp} (Hard-Clip)")
            else:
                print(f"[{timestamp}] 🔍 Inquiry '{cmd}' -> {resp}")

        elif event_type == "init":
            print(f"[{timestamp}] 🔄 Initialisierung (IN) empfangen – Plotter bereit")

        elif event_type == "pen_change":
            pen = data.get("pen", 0)
            if pen == 0:
                print(f"[{timestamp}] 🅿️  Stift 0 (Stift abgelegt)")
            else:
                speed = plotter.pen_speed.get(pen, plotter.default_speed_cm_s)
                force = plotter.pen_force.get(pen, 2)
                print(f"[{timestamp}] 🖊️  Stift {pen} gewählt (Geschwindigkeit: {speed:.0f} cm/s, Anpressdruck: {force})")

        elif event_type == "speed_change":
            speed = data.get("speed_cm_s", 0)
            print(f"[{timestamp}] ⚡ Geschwindigkeit gesetzt: {speed:.0f} cm/s")

        elif event_type == "polyline_drawn":
            pts = data.get("points", 0)
            dist = data.get("dist_mm", 0.0)
            pen = data.get("pen", 1)
            tot = data.get("total_polylines", len(plotter.recorded_polylines))
            print(f"[{timestamp}] ✏️  Pfad {tot} gezeichnet: {pts} Stützpunkte, {dist:.1f} mm (Stift {pen})")

        elif event_type == "job_finished":
            polys = data.get("polylines", 0)
            d_m = data.get("draw_m", 0.0)
            t_m = data.get("travel_m", 0.0)
            print(f"[{timestamp}] ✅ Plot-Auftrag abgeschlossen!")
            print(f"           Pfade: {polys} | Zeichenweg: {d_m:.2f} m | Leerweg: {t_m:.2f} m")
            export_plotter_svg(plotter, out_svg_path)
            last_saved_count[0] = len(plotter.recorded_polylines)
            print(f"           📁 Ergebnis-Vektoren gespeichert: {out_svg_path}\n")

        elif event_type == "abort":
            print(f"[{timestamp}] ⏹ Abbruch-Signal (ESC.K) empfangen! Puffer geleert, Stift angehoben.")

        sys.stdout.flush()

    plotter = VirtualPlotter(
        paper=args.paper,
        margin_profile=args.margin,
        buffer_size=buf_size,
        resolution_mm=args.unit,
        realtime=args.realtime,
        speedup=args.speedup,
        baudrate=args.baudrate,
        on_event=on_plotter_event,
    )

    if args.tcp:
        server = TcpServer(plotter, port=args.tcp, baudrate=args.baudrate)
        conn_str = server.start()
    else:
        server = PtyServer(plotter, symlink_path=args.symlink, baudrate=args.baudrate)
        conn_str = server.start()

    print("=" * 64)
    print(" 🖋️  Mutoh XP-500 Plotter Emulator (HP-7585B Simulation)")
    print("=" * 64)
    print(f" Format:           {plotter.paper} ({plotter.sheet_width_mm:.0f} x {plotter.sheet_height_mm:.0f} mm)")
    print(f" Ränder (Profil):  {args.margin} ({plotter.plottable_width_mm:.1f} x {plotter.plottable_height_mm:.1f} mm Hard-Clip)")
    print(f" Auflösung:        {args.unit} mm/Unit ({plotter.units_per_mm:.0f} Units/mm)")
    print(f" Puffer:           {args.buffer.upper()} ({plotter.buffer_size:,} Bytes)")
    if args.baudrate:
        bps = args.baudrate / 10.0
        print(f" Baudrate:         {args.baudrate} Baud (~{bps:.0f} Bytes/s, 8N1)")
    else:
        print(f" Baudrate:         Unbegrenzt (Memory Speed)")
    print(f" Verbindung:       {conn_str}")
    if args.realtime:
        print(f" Mechanik:         Echtzeit-Simulation ({args.speedup:.1f}x Speedup)")
    else:
        print(f" Mechanik:         Sofortige Abarbeitung (Fast-Mode)")
    print(f" Ausgabe-SVG:      {out_svg_path}")
    print("=" * 64)
    print("Warte auf Befehle... (Drücke Strg+C zum Beenden)\n")
    sys.stdout.flush()

    def handle_exit(signum, frame):
        print("\nBeende Emulator...")
        server.stop()
        if plotter.recorded_polylines:
            export_plotter_svg(plotter, out_svg_path)
            print(f"📁 Plot-Ergebnis gespeichert als: {out_svg_path}")
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

    last_check_polys = 0
    idle_cycles = 0

    try:
        while True:
            time.sleep(0.5)
            # Auto-save if new polylines were drawn and no new commands arrived for 1 second
            current_polys = len(plotter.recorded_polylines)
            if current_polys > last_saved_count[0]:
                if current_polys == last_check_polys:
                    idle_cycles += 1
                    if idle_cycles >= 2:  # 1 second idle after drawing
                        export_plotter_svg(plotter, out_svg_path)
                        last_saved_count[0] = current_polys
                        idle_cycles = 0
                        timestamp = time.strftime("%H:%M:%S")
                        print(f"[{timestamp}] 📁 {current_polys} Pfade empfangen -> SVG aktualisiert: {out_svg_path}")
                        sys.stdout.flush()
                else:
                    last_check_polys = current_polys
                    idle_cycles = 0
    except KeyboardInterrupt:
        handle_exit(None, None)

    return 0


if __name__ == "__main__":
    sys.exit(main())
