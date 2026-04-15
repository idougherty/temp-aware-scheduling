#!/usr/bin/env python3
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
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

args = parser.parse_args()
start_s = args.start
end_s = args.end
data_path = Path(args.path)
smooth_plot = not args.no_smooth
plot_freq = args.plot_freq

csvs = [str(p) for p in data_path.iterdir() if p.is_file()]
#csvs = [p for p in csvs if "soc" not in p and "center" not in p]
#csvs = [p for p in csvs if "soc" in p]
csvs.sort()

dfs = [pd.read_csv(csv) for csv in csvs]
names = [csv.replace(".csv", "").split("/")[-1].replace("-thermal", "") for csv in csvs]

hz_dfs = []
hz_names = []
if plot_freq:
    hz_dfs = [df for df in dfs if df["clock_hz"].any()]
    hz_names = [name for name, df in zip(names, dfs) if df["clock_hz"].any()]

fig, axes = plt.subplots(1 + len(hz_dfs), 1, figsize=(12, 6 + len(hz_dfs)),
                         gridspec_kw={"height_ratios": [2] + [1] * len(hz_dfs)}, sharex=True)
temp_plot = axes if len(hz_dfs) == 0 else axes[0]

for idx, (name, df) in enumerate(zip(names, dfs)):
    df["x"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df["smooth_temp_celsius"] = df["temp_celsius"].ewm(span=10, adjust=True).mean()
    df = df[df["x"].between(start_s, end_s)]

    if smooth_plot:
        temp_plot.plot(df["x"], df["smooth_temp_celsius"], label=name)
    else:
        temp_plot.plot(df["x"], df["temp_celsius"], label=name)

    #print(f"{name} avg temp: {df["temp_celsius"].mean()}C")

for idx, (name, df) in enumerate(zip(hz_names, hz_dfs)):
    df["x"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df = df[df["x"].between(start_s, end_s)]
    axes[idx + 1].plot(df["x"], df["clock_hz"], label=name)
    axes[idx + 1].set_ylabel("Clock (hz)")
    axes[idx + 1].legend(loc="best")
    
temp_plot.set_ylabel("Temperature (°C)")
temp_plot.legend(loc="best")
temp_plot.set_xlabel("Elapsed time (s)")

fig.suptitle("Temp & Freq over time")
plt.tight_layout()
plt.savefig("fig.png", dpi=150)
