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

parser.add_argument("-p", "--path")
parser.add_argument("-o", "--out-path")
parser.add_argument("-s", "--start", default=0, type=int)
parser.add_argument("-e", "--end", default=math.inf, type=int)

args = parser.parse_args()
in_path = Path(args.path)
out_path = Path(args.out_path) if args.out_path else None
start_s = args.start
end_s = args.end

df = pd.read_csv(in_path)

fig, ax = plt.subplots()

df["timestamp_s"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
df["smooth_temp_celsius"] = df["temp_celsius"].ewm(span=10, adjust=True).mean()
df = df[df["timestamp_s"].between(start_s, end_s)]

ax.plot(df["timestamp_s"], df["smooth_temp_celsius"]) 
ax.axvline(x=start_s, color='r', linestyle='--')
ax.axvline(x=end_s, color='r', linestyle='--')

ax.set_ylabel("Temperature (°C)")
ax.set_xlabel("Elapsed time (s)")

fig.suptitle("Temp & Freq over time")
plt.tight_layout()
plt.savefig("fig.png", dpi=150)

if out_path is not None:
    print(f"trimmed csv written to {out_path}")
    df.to_csv(out_path)
