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
parser.add_argument("-rs", "--regression-start", type=int)
parser.add_argument("-re", "--regression-end", type=int)
parser.add_argument("-rt", "--regression-target")

args = parser.parse_args()
start_s = args.start
end_s = args.end
reg_start_s = args.regression_start or None
reg_end_s = args.regression_end or None
reg_target = args.regression_target or None
data_path = Path(args.path)

csvs = [str(p) for p in data_path.iterdir() if p.is_file()]
#csvs = [p for p in csvs if "soc" not in p and "center" not in p]
#csvs = [p for p in csvs if "soc" in p]
csvs.sort()

dfs = [pd.read_csv(csv) for csv in csvs]
names = [csv.replace(".csv", "").split("/")[-1].replace("-thermal", "") for csv in csvs]

#hz_dfs = [df for df in dfs if df["clock_hz"].any()]
#hz_names = [name for name, df in zip(names, dfs) if df["clock_hz"].any()]
hz_dfs = []
hz_names = []

fig, axes = plt.subplots(1 + len(hz_dfs), 1, figsize=(12, 6 + len(hz_dfs)),
                         gridspec_kw={"height_ratios": [2] + [1] * len(hz_dfs)}, sharex=True)
temp_plot = axes if len(hz_dfs) == 0 else axes[0]

for idx, (name, df) in enumerate(zip(names, dfs)):
    if reg_target is not None and name != reg_target:
        continue

    df["x"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df["smooth_temp_celsius"] = df["temp_celsius"].ewm(span=10, adjust=True).mean()
    df = df[df["x"].between(start_s, end_s)]
    temp_plot.plot(df["x"], df["smooth_temp_celsius"], label=name)

    if reg_target is None:
        continue

    reg_start_s = 0
    reg_end_s = 650

    df = df[df["x"].between(reg_start_s, reg_end_s)]
    T_init = 50
    T_ss = 37

    def two_exp(t, alpha, tau1, tau2):
        return T_ss + (T_init - T_ss) * (alpha * np.exp(-(t-reg_start_s)/tau1) + (1-alpha) * np.exp(-(t-reg_start_s)/tau2))

    (alpha, tau1, tau2), _ = curve_fit(two_exp, df['x'], df['smooth_temp_celsius'], p0=[0.5, 10, 100], bounds=([0, 0, 0], [1, np.inf, np.inf]))
    #(alpha, tau1, tau2), _ = curve_fit(two_exp, df['x'], df['smooth_temp_celsius'], p0=[0.5, 10, 100])
    x = np.linspace(reg_start_s, reg_end_s, (reg_end_s - reg_start_s)*10 + 1)
    y = two_exp(x, alpha, tau1, tau2)
    temp_plot.plot(x, y, '--', label=f"two-exp a={alpha:2f}, t1={tau1:2f}, t2={tau2:2f}")
    print(f"Parameters: T_0={T_init}, T_final={T_ss}, alpha={alpha}, tau1={tau1}, tau2={tau2}")
    #print(f"Regression fit: {r2_score(df['smooth_temp_celsius'], y)}")


for idx, (name, df) in enumerate(zip(hz_names, hz_dfs)):
    if reg_target is not None and name != reg_target:
        continue
    print(idx, name)
    df["x"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df = df[df["x"].between(start_s, end_s)]
    axes[idx + 1].plot(df["x"], df["clock_hz"], label=name)
    axes[idx + 1].plot(df["x"], df["req_clock_hz"], label=f"{name} requested", linestyle='--')
    axes[idx + 1].set_ylabel("Clock (hz)")
    axes[idx + 1].legend(loc="best")
    
temp_plot.set_ylabel("Temperature (°C)")
temp_plot.legend(loc="best")
temp_plot.set_xlabel("Elapsed time (s)")

fig.suptitle("Temp & Freq over time")
plt.tight_layout()
plt.savefig("fig.png", dpi=150)
