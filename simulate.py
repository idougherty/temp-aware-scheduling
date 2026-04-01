#!/usr/bin/env python3
import argparse
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.integrate import solve_ivp

# --- Task schedule: list of (t_start, t_end) in seconds ---
SCHEDULE = [
    (5, 3605),
]

SCHEDULE = [
    (5, 10), (20, 30), (40, 55), (65, 85), (95, 120), (130, 160)
]

COOLDOWN = 40  # seconds to simulate after last period


def build_Q_signal(t, schedule, Q):
    """Return power at time t given the schedule."""
    for t0, t1 in schedule:
        if t0 <= t <= t1:
            return Q
    return 0.0


def simulate(schedule, Q, R_total, tau1, tau2, beta, T_amb, dt=1):
    t_end = max(t1 for _, t1 in schedule) + COOLDOWN

    # force solver to land exactly on task boundaries
    breakpoints = sorted(set(
        [0.0] + [t for pair in schedule for t in pair] + [t_end]
    ))

    t_eval = np.unique(np.concatenate([
        np.arange(t0, t1, dt) for t0, t1 in zip(breakpoints, breakpoints[1:])
    ] + [np.array(breakpoints)]))

    R12 = beta * R_total
    R3  = (1 - beta) * R_total
    C1  = tau1 / R12
    C2  = tau2 / R3

    def odes(t, y):
        T_cpu, T_sink = y
        q = build_Q_signal(t, schedule, Q)
        dTcpu  = (q - (T_cpu - T_sink) / R12) / C1
        dTsink = ((T_cpu - T_sink) / R12 - (T_sink - T_amb) / R3) / C2
        return [dTcpu, dTsink]

    #sol = solve_ivp(odes, (0, t_end), [T_amb, T_amb], t_eval=t_eval, method="RK45")
    sol = solve_ivp(odes, (0, t_end), [T_amb, T_amb],
                    t_eval=t_eval, method="RK45",
                    max_step=dt)

    return sol.t, sol.y[0], sol.y[1]


def plot(t, T_cpu, T_sink, schedule, T_amb, benchmark_data):

    fig, ax = plt.subplots(figsize=(12, 5))
    
    df = pd.read_csv(benchmark_data)
    df["timestamp_s"] = (df["timestamp_ms"] - df["timestamp_ms"].iloc[0]) / 1000.0
    df["smooth_temp_celsius"] = df["temp_celsius"].ewm(span=10, adjust=True).mean()
    ax.plot(df["timestamp_s"], df["smooth_temp_celsius"], label="real workload") 

    # shade active periods
    for t0, t1 in schedule:
        ax.axvspan(t0, t1, alpha=0.12, color="red", label="_nolegend_")

    ax.plot(t, T_cpu,  label="T_cpu",  linewidth=2)
    ax.plot(t, T_sink, label="T_sink (latent)", linewidth=1.5, linestyle="--")
    ax.axhline(T_amb, color="gray", linewidth=1, linestyle=":", label=f"T_amb ({T_amb}°C)")

    # annotate shaded regions once
    ax.axvspan(0, 0, alpha=0.12, color="red", label="task active")

    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Temperature (°C)")
    ax.set_title("Two-Node Thermal Model Prediction")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("fig.png")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict CPU temperature from a task schedule.")
    parser.add_argument("--Q",       type=float, required=True, help="Task power in watts")
    parser.add_argument("--R_total", type=float, required=True, help="Total thermal resistance (C/W)")
    parser.add_argument("--tau1",    type=float, required=True, help="CPU time constant (s)")
    parser.add_argument("--tau2",    type=float, required=True, help="Heat sink time constant (s)")
    parser.add_argument("--beta",    type=float, required=True, help="Resistance split (0-1)")
    parser.add_argument("--T_amb",   type=float, default=22.0,  help="Ambient temperature (C), default 22")
    parser.add_argument("--benchmark-data")
    args = parser.parse_args()

    t, T_cpu, T_sink = simulate(
        schedule = SCHEDULE,
        Q        = args.Q,
        R_total  = args.R_total,
        tau1     = args.tau1,
        tau2     = args.tau2,
        beta     = args.beta,
        T_amb    = args.T_amb,
    )

    plot(t, T_cpu, T_sink, SCHEDULE, args.T_amb, args.benchmark_data)
