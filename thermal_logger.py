#!/usr/bin/env python3
"""
Orange Pi 5 (RK3588S) Thermal Zone Logger
Logs timestamp, temperature, and associated clock speed for each thermal zone
into separate CSVs named after the zone type.

CSV columns:
  timestamp_ms  - Unix time in milliseconds
  datetime      - Human-readable ISO 8601 datetime
  temp_celsius  - Temperature in °C
  clock_hz      - Associated clock frequency in Hz (or '' if not applicable)
  clock_mhz     - Same, in MHz (for readability)
"""

import os
import sys
import time
import signal
import pathlib
import argparse
from datetime import datetime

# ── Configuration ────────────────────────────────────────────────────────────

THERMAL_BASE  = pathlib.Path("/sys/class/thermal")
CPUFREQ_BASE  = pathlib.Path("/sys/devices/system/cpu/cpufreq")
GPU_FREQ_PATH = pathlib.Path("/sys/class/devfreq")          # Mali GPU devfreq
NPU_FREQ_PATH = pathlib.Path("/sys/class/devfreq")          # NPU devfreq

# RK3588S: map thermal zone type → cpufreq policy directory (best effort)
# Zones not in this map will attempt GPU/NPU devfreq, then record '' if absent.
ZONE_TO_CPUPOLICY = {
    "littlecore-thermal": "policy0",   # A55 cores 0-3
    "bigcore0-thermal":   "policy4",   # A76 cores 4-5
    "bigcore1-thermal":   "policy6",   # A76 cores 6-7
}

DEFAULT_INTERVAL = 0.1   # seconds between samples
DEFAULT_OUTPUT   = "./data"   # directory for CSV files

# ── Helpers ──────────────────────────────────────────────────────────────────

def discover_thermal_zones():
    """Return list of (zone_path, zone_type) sorted by zone index."""
    zones = []
    for zdir in sorted(THERMAL_BASE.glob("thermal_zone*"),
                       key=lambda p: int(p.name.replace("thermal_zone", ""))):
        type_file = zdir / "type"
        temp_file = zdir / "temp"
        if type_file.exists() and temp_file.exists():
            zone_type = type_file.read_text().strip()
            zones.append((zdir, zone_type))
    return zones


def build_clock_source(zone_type, metric):
    """
    Return an open file-like object (or None) for the clock frequency
    associated with this thermal zone.
    Priority: cpufreq policy → devfreq → None
    """
    if zone_type in ZONE_TO_CPUPOLICY:
        policy_dir = CPUFREQ_BASE / ZONE_TO_CPUPOLICY[zone_type]
        freq_file  = policy_dir / metric
        if freq_file.exists():
            return open(freq_file, "r")

    return None


def safe_read_fd(fd):
    """Read an open file descriptor, seeking to start. Returns '' on error."""
    if fd is None:
        return ""
    try:
        fd.seek(0)
        return fd.read().strip()
    except Exception:
        return ""


def read_temp_celsius(temp_fd):
    """Read millidegree value and convert to °C string."""
    raw = safe_read_fd(temp_fd)
    if raw:
        return f"{int(raw) / 1000:.3f}"
    return ""


def sanitise_filename(zone_type):
    """Make zone type safe for use as a filename."""
    return zone_type.replace("/", "_").replace(" ", "_")


def open_csv(output_dir, zone_type):
    """Open (or create) the CSV for a zone, write header if new."""
    fname = pathlib.Path(output_dir) / f"{sanitise_filename(zone_type)}.csv"
    fh = open(fname, "w", buffering=1)   # line-buffered
    fh.write("timestamp_ms,temp_celsius,clock_hz,req_clock_hz\n")
    return fh


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Log Orange Pi 5 thermal zones to per-zone CSV files."
    )
    parser.add_argument(
        "-i", "--interval", type=float, default=DEFAULT_INTERVAL,
        help=f"Sampling interval in seconds (default: {DEFAULT_INTERVAL})"
    )
    parser.add_argument(
        "-o", "--output-dir", default=DEFAULT_OUTPUT,
        help=f"Directory to write CSV files (default: current directory)"
    )
    parser.add_argument(
        "-n", "--count", type=int, default=0,
        help="Number of samples to collect (0 = run forever)"
    )
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    zones = discover_thermal_zones()
    if not zones:
        print("ERROR: No thermal zones found under /sys/class/thermal/", file=sys.stderr)
        sys.exit(1)

    print(f"Discovered {len(zones)} thermal zone(s):")

    # Build per-zone state: (temp_fd, clock_fd, csv_fh)
    zone_state = []
    for zdir, ztype in zones:
        temp_fd  = open(zdir / "temp", "r")
        clock_fd = build_clock_source(ztype, "cpuinfo_cur_freq")
        req_clock_fd = build_clock_source(ztype, "scaling_cur_freq")
        csv_fh   = open_csv(output_dir, ztype)
        zone_state.append((ztype, temp_fd, clock_fd, req_clock_fd, csv_fh))

        clock_info = "no clock mapped"
        if clock_fd is not None:
            clock_info = f"clock → {clock_fd.name}"
        print(f"  {ztype:<30}  {clock_info}")
        print(f"    → {output_dir / (sanitise_filename(ztype) + '.csv')}")

    print(f"\nLogging every {args.interval}s  |  Ctrl-C to stop\n")

    # Graceful shutdown
    running = True
    def _stop(sig, frame):
        nonlocal running
        running = False
    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    sample_count = 0
    next_tick    = time.monotonic()

    while running:
        now       = time.time()
        ts_ms     = int(now * 1000)

        for ztype, temp_fd, clock_fd, req_clock_fd, csv_fh in zone_state:
            temp   = read_temp_celsius(temp_fd)
            clk_hz = safe_read_fd(clock_fd)
            req_clk_hz = safe_read_fd(req_clock_fd)
            csv_fh.write(f"{ts_ms},{temp},{clk_hz},{req_clk_hz}\n")

        sample_count += 1
        if args.count and sample_count >= args.count:
            break

        # Sleep until next tick (drift-compensated)
        next_tick += args.interval
        sleep_for  = next_tick - time.monotonic()
        if sleep_for > 0:
            time.sleep(sleep_for)

    # Cleanup
    for _, temp_fd, clock_fd, req_clock_fd, csv_fh in zone_state:
        temp_fd.close()
        if clock_fd:
            clock_fd.close()
        if req_clock_fd:
            req_clock_fd.close()
        csv_fh.close()

    print(f"\nDone. {sample_count} sample(s) written to: {output_dir.resolve()}/")


if __name__ == "__main__":
    main()
