#!/usr/bin/env python3
import os
import sys
import time
import signal
import pathlib
import argparse
from datetime import datetime

THERMAL_BASE  = pathlib.Path("/sys/class/thermal")
CPUFREQ_BASE  = pathlib.Path("/sys/devices/system/cpu/cpufreq")
XPU_FREQ_PATH = pathlib.Path("/sys/class/devfreq")

ZONE_TO_FREQ_FILE = {
    "littlecore-thermal": CPUFREQ_BASE / "policy0" / "cpuinfo_cur_freq",
    "bigcore0-thermal":   CPUFREQ_BASE / "policy4" / "cpuinfo_cur_freq",
    "bigcore1-thermal":   CPUFREQ_BASE / "policy6" / "cpuinfo_cur_freq",
    "gpu-thermal":        XPU_FREQ_PATH / "fb000000.gpu" / "cur_freq",
    "npu-thermal":        XPU_FREQ_PATH / "fdab0000.npu" / "cur_freq",
}

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


def build_clock_source(zone):
    if zone in ZONE_TO_FREQ_FILE:
        freq_file = ZONE_TO_FREQ_FILE[zone]
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


def open_csv(output_dir, zone):
    """Open (or create) the CSV for a zone, write header if new."""
    fname = pathlib.Path(output_dir) / f"{zone}.csv"
    fh = open(fname, "w", buffering=1)   # line-buffered
    fh.write("timestamp_ms,temp_celsius,clock_hz\n")
    return fh

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interval", type=float, default=0.1)
    parser.add_argument("-o", "--output-dir", default="./data")
    args = parser.parse_args()

    output_dir = pathlib.Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    zones = discover_thermal_zones()
    if not zones:
        print("ERROR: No thermal zones found", file=sys.stderr)
        sys.exit(1)

    print(f"Discovered {len(zones)} thermal zone(s):")

    # Build per-zone state: (temp_fd, clock_fd, csv_fh)
    zone_state = []
    for zdir, zone in zones:
        temp_fd  = open(zdir / "temp", "r")
        clock_fd = build_clock_source(zone)
        csv_fh   = open_csv(output_dir, zone)
        zone_state.append((zone, temp_fd, clock_fd, csv_fh))

        clock_info = "no clock mapped"
        if clock_fd is not None:
            clock_info = f"{clock_fd.name}"
        print(f"  {zone:<30}  {clock_info}")

    print(f"\nLogging every {args.interval}s  |  Ctrl-C to stop\n")

    # Graceful shutdown
    running = True
    def _stop(sig, frame):
        global running
        running = False
    signal.signal(signal.SIGINT,  _stop)
    signal.signal(signal.SIGTERM, _stop)

    next_tick    = time.monotonic()

    while running:
        now       = time.time()
        ts_ms     = int(now * 1000)

        for ztype, temp_fd, clock_fd, csv_fh in zone_state:
            temp   = read_temp_celsius(temp_fd)
            clk_hz = safe_read_fd(clock_fd)
            csv_fh.write(f"{ts_ms},{temp},{clk_hz}\n")

        # Sleep until next tick (drift-compensated)
        next_tick += args.interval
        sleep_for  = next_tick - time.monotonic()
        if sleep_for > 0:
            time.sleep(sleep_for)

    # Cleanup
    for _, temp_fd, clock_fd, csv_fh in zone_state:
        temp_fd.close()
        if clock_fd:
            clock_fd.close()
        csv_fh.close()

    print(f"\nDone. Results written to: {output_dir.resolve()}/")

