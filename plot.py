#!/usr/bin/env python3
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path
import math
from scipy.optimize import curve_fit
from sklearn.metrics import r2_score
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("-s", "--start", default=0, type=int)
parser.add_argument("-e", "--end", default=math.inf, type=int)
parser.add_argument("-p", "--path", default="./data")
parser.add_argument("--no-smooth", action="store_true")
parser.add_argument("--plot-freq", action="store_true")
parser.add_argument("--schedule", default=None)
args = parser.parse_args()

start_s       = args.start
end_s         = args.end
data_path     = Path(args.path)
smooth_plot   = not args.no_smooth
plot_freq     = args.plot_freq
schedule_path = args.schedule

# Load thermal / frequency data 
csvs = [str(p) for p in data_path.iterdir() if p.is_file()]
csvs = [p for p in csvs if "soc" in p]
csvs.sort()
dfs   = [pd.read_csv(csv) for csv in csvs]
names = [csv.replace(".csv", "").split("/")[-1].replace("-thermal", "") for csv in csvs]

hz_dfs   = []
hz_names = []
if plot_freq:
    hz_dfs   = [df   for df, name in zip(dfs, names) if df["clock_hz"].any()]
    hz_names = [name for name, df  in zip(names, dfs) if df["clock_hz"].any()]

# Load schedule (optional) 
schedule_df = None
if schedule_path:
    schedule_df = pd.read_csv(schedule_path,
                              names=["cpu_id", "request_arrival", "task_length"],
                              comment="#")
    # coerce in case the CSV has a text header row
    schedule_df = schedule_df[pd.to_numeric(schedule_df["cpu_id"], errors="coerce").notna()]
    schedule_df = schedule_df.astype({"cpu_id": int,
                                      "request_arrival": float,
                                      "task_length": float})

# Build subplot grid 
n_extra       = len(hz_dfs)
has_gantt     = schedule_df is not None
n_rows        = (1 if has_gantt else 0) + 1 + n_extra   # gantt? + temp + freq(s)

height_ratios = []
if has_gantt:
    height_ratios.append(1)          # Gantt — compact
height_ratios.append(3)              # temperature
height_ratios += [1] * n_extra       # frequency panels

fig, axes = plt.subplots(
    n_rows, 1,
    figsize=(10, 5),
    gridspec_kw={"height_ratios": height_ratios},
    sharex=True,
)

# Normalise axes to a list regardless of n_rows
if n_rows == 1:
    axes = [axes]

ax_idx    = 0
gantt_ax  = None
if has_gantt:
    gantt_ax = axes[ax_idx]
    ax_idx  += 1

temp_plot = axes[ax_idx]
ax_idx   += 1
freq_axes = axes[ax_idx:] if n_extra else []
warmup_time = 5

# Gantt chart 
if has_gantt and gantt_ax is not None:
    n_cores     = 1
    core_ids    = sorted(schedule_df["cpu_id"].unique())
    all_cores   = list(range(n_cores))

    for idx, row in schedule_df.iterrows():
        cid     = int(row["cpu_id"])
        arrival = float(row["request_arrival"]) + warmup_time
        length  = float(row["task_length"])
        cmap        = plt.get_cmap("Set1", 10)
        task_colors = {t: cmap(t) for t in range(5)}
        # y position = core id; bar height slightly < 1 for a gap between lanes

        if arrival < start_s or arrival + length > end_s:
            continue

        if cid < 0:
            color = task_colors[idx % 5]
            for ncid in all_cores:
                gantt_ax.barh(
                    y=ncid,
                    width=length,
                    left=arrival-start_s,
                    color=color,
                    height=0.6,
                    edgecolor="black",
                    alpha=0.5,
                )
        else:
            gantt_ax.barh(
                y=cid,
                width=length,
                left=arrival-start_s,
                height=0.6,
                edgecolor="black",
                linewidth=0.5,
                alpha=0.85,
            )

    gantt_ax.set_yticks(all_cores)
    gantt_ax.set_yticklabels([f"" for c in all_cores])
    gantt_ax.set_ylabel("Schedule")
    gantt_ax.set_ylim(-0.5, n_cores - 0.5)
    gantt_ax.invert_yaxis()
    gantt_ax.grid(axis="x", linestyle="--", alpha=0.4)
    gantt_ax.spines[["top", "right"]].set_visible(False)

# Temperature plot 
for idx, (name, df) in enumerate(zip(names, dfs)):
    df["x"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df["smooth_temp_celsius"] = df["temp_celsius"].ewm(span=10, adjust=True).mean()
    df = df[df["x"].between(start_s, end_s)]
    df.loc[:, "x"] = df["x"] - start_s

    if smooth_plot:
        temp_plot.plot(df["x"], df["smooth_temp_celsius"], label=name, lw=2)
    else:
        temp_plot.plot(df["x"], df["temp_celsius"], label=name)

#    mean_temp = df["temp_celsius"].mean()
#    plt.axhline(mean_temp, color="orange", linestyle='--', label=f"mean-temp={mean_temp:0.1f}°C")
#    print(f"{name} avg temp: {mean_temp}C")

# Frequency subplots 
for idx, (name, df) in enumerate(zip(hz_names, hz_dfs)):
    df["x"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df = df[df["x"].between(start_s, end_s)]
    axes[idx + 1].plot(df["x"], df["clock_hz"], label=name)
    axes[idx + 1].set_ylabel("Clock (hz)")
    axes[idx + 1].legend(loc="best")
    
temp_plot.set_ylabel("Temperature (°C)")
temp_plot.set_xlabel("Time (s)")
#temp_plot.set_ylim(55, 73)
temp_plot.grid(linestyle="--", alpha=0.4)
temp_plot.spines[["top", "right"]].set_visible(False)
temp_plot.legend()

# Shared x-axis label & layout 
axes[0].set_title(f'', fontsize=14, fontweight='bold')
axes[-1].set_xlabel("Time (s)")
fig.tight_layout()
plt.savefig("fig.png", dpi=150)
