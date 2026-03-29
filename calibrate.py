#!/usr/bin/env python3
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit, minimize
from scipy.integrate import solve_ivp


def fit_steady_state(csv_low, csv_high, alpha, T_amb):
    """
    Fit Q_low and R_total from two steady state experiments.
    CSVs should be trimmed to just the steady state region — all samples are averaged.
    alpha = (f_high * V_high^2) / (f_low * V_low^2) from OPP table.
    """
    df_low  = pd.read_csv(csv_low)
    df_high = pd.read_csv(csv_high)
    T_ss_low  = df_low["temp_celsius"].mean()
    T_ss_high = df_high["temp_celsius"].mean()

    dT_low  = T_ss_low  - T_amb
    dT_high = T_ss_high - T_amb

    Q_low   = (dT_high - dT_low) / (alpha - 1)
    Q_high  = Q_low * alpha
    R_total = dT_low / Q_low

    print(f"T_ss_low = {T_ss_low:.4f} C  (mean of {len(df_low)} samples)")
    print(f"T_ss_high= {T_ss_high:.4f} C  (mean of {len(df_high)} samples)")
    print(f"Q_low    = {Q_low:.4f} W")
    print(f"Q_high   = {Q_high:.4f} W")
    print(f"R_total  = {R_total:.4f} C/W")
    return Q_low, Q_high, R_total


def fit_tau1(csv_pulse, Q, R_total, T_amb, p0=5.0):
    """
    Fit tau1 from the rise of a short pulse experiment.
    Pulse must be short enough that the heat sink stays near T_amb throughout.
    Fits the rise: T_cpu goes from T_amb up toward T_ss = T_amb + Q_low * R_total.
    """
    df = pd.read_csv(csv_pulse)
    t  = (df["timestamp_ms"].values - df["timestamp_ms"].iloc[0]) / 1000.0
    T  = df["temp_celsius"].values

    T_init     = T[0]
    T_ss_pulse = T_amb + Q * R_total

    def model(t, tau1):
        return T_ss_pulse + (T_init - T_ss_pulse) * np.exp(-t / tau1)

    (tau1,), _ = curve_fit(model, t, T, p0=[p0])
    print(f"tau1     = {tau1:.4f} s")
    return tau1


def fit_tau2(csv_cool, T_amb, p0=60.0):
    """
    Fit tau2 from the long cooling tail after a sustained load.
    CSV should be trimmed to start at the point where the CPU has already
    cooled and only the heat sink discharge remains (the slow tail).
    """
    df = pd.read_csv(csv_cool)
    t  = (df["timestamp_ms"].values - df["timestamp_ms"].iloc[0]) / 1000.0
    T  = df["temp_celsius"].values

    T_init_cool = T[0]

    def model(t, tau2):
        return T_amb + (T_init_cool - T_amb) * np.exp(-t / tau2)

    (tau2,), _ = curve_fit(model, t, T, p0=[p0])
    print(f"tau2     = {tau2:.4f} s")
    return tau2


def simulate(t_eval, T_cpu0, T_sink0, Q, R_total, tau1, tau2, beta, T_amb):
    """
    Integrate the two-node ODE forward given a constant Q.
    Returns T_cpu trajectory.
    """
    R12 = beta * R_total
    R3  = (1 - beta) * R_total
    C1  = tau1 / R12
    C2  = tau2 / R3

    def odes(t, y):
        T_cpu, T_sink = y
        dTcpu  = (Q - (T_cpu - T_sink) / R12) / C1
        dTsink = ((T_cpu - T_sink) / R12 - (T_sink - T_amb) / R3) / C2
        return [dTcpu, dTsink]

    sol = solve_ivp(odes, (t_eval[0], t_eval[-1]), [T_cpu0, T_sink0], t_eval=t_eval, method="RK45")
    return sol.y[0]


def fit_beta(benchmark_data, Q, R_total, tau1, tau2, T_amb, p0=0.3):
    """
    Fit beta (the R split between R12 and R3) by minimizing residuals of the
    full two-node ODE simulation against the pulse rise data.
    """
    df = pd.read_csv(benchmark_data)
    t  = (df["timestamp_ms"].values - df["timestamp_ms"].iloc[0]) / 1000.0
    T  = df["temp_celsius"].values

    def residuals(beta):
        T_pred = simulate(t, T[0], T_amb, Q, R_total, tau1, tau2, beta[0], T_amb)
        return np.sum((T_pred - T) ** 2)

    result = minimize(residuals, x0=[p0], bounds=[(0.01, 0.99)])
    beta = result.x[0]
    print(f"beta     = {beta:.4f}  (R12={beta*R_total:.4f} C/W, R3={(1-beta)*R_total:.4f} C/W)")
    return beta


def simulate2(schedule, Q, R_total, tau1, tau2, beta, T_amb, sim_length, dt=1):

    def build_Q_signal(t, schedule, Q):
        for t0, t1 in schedule:
            if t0 <= t <= t1:
                return Q
        return 0.0

    # force solver to land exactly on task boundaries
    breakpoints = sorted(set(
        [0.0] + [t for pair in schedule for t in pair] + [sim_length]
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

    sol = solve_ivp(odes, (0, sim_length), [T_amb, T_amb],
                    t_eval=t_eval, method="RK45",
                    max_step=dt)

    return sol.t, sol.y[0], sol.y[1]


def fit_all(benchmarks, schedules, T_amb):
    dfs = [pd.read_csv(path) for path in benchmarks]

    for df in dfs:
        df["timestamp_s"] = (df["timestamp_ms"].values - df["timestamp_ms"].iloc[0]) / 1000.0

    def residuals(params):
        Q, R, tau1, tau2, beta = params

        print(f"=== Optimization Parameters ===")
        print(f"Q={Q:.3f}W, R={R:.3f}C/W, tau1={tau1:.3f}s, tau2={tau2:.3f}s, beta={beta:.3f}")
        error = 0
        
        for df, schedule in zip(dfs, schedules):
            T  = df["temp_celsius"].values
            t  = df["timestamp_s"].values
            sim_length = int(df["timestamp_s"].iloc[-1])
            T_x, T_pred, _ = simulate2(schedule, Q, R, tau1, tau2, beta, T_amb, sim_length)
            x = np.linspace(0, sim_length, num=len(df["timestamp_s"]), endpoint=True)
            T_pred_interp = np.interp(x, T_x, T_pred)

            error += np.sum((T_pred_interp - T) ** 2)

        print(f"Error:{error}")
        return error

    x0 = np.array([50, 1, 10, 100, 0.3])
    bounds = [
        (0.01, 100),       # Q
        (0.01, 100),       # R
        (0.001, 1000),     # tau1
        (0.01, 10000),     # tau2
        (0.01, 0.99),      # beta
    ]

    results = minimize(residuals, x0=x0, bounds=bounds, method='trust-constr')

    print(results)
    
    Q, R, tau1, tau2, beta = results.x

    return Q, R, tau1, tau2, beta


# --- Run calibration ---
T_amb = 34        # <-- replace with your measured ambient temperature
alpha = 5         # <-- replace with f_high*V_high^2 / (f_low*V_low^2) from OPP table
# 6.59 or 3.42

bench_dir = "data-calibration-clean/"
steady_state_low    = bench_dir + "408mhz-steady-state.csv"
steady_state_high   = bench_dir + "1800mhz-steady-state.csv"
cooling_tail        = bench_dir + "1800mhz-long-cool.csv"
short_pulse         = bench_dir + "1800mhz-pulse-rise.csv"
multi_pulse         = bench_dir + "1800mhz-multi-pulse.csv"
rise_fall           = bench_dir + "1800mhz-sustained.csv"

# Q_low, Q_high, R_total = fit_steady_state(steady_state_low, steady_state_high, alpha, T_amb)
#tau1            = fit_tau1(short_pulse, Q_high, R_total, T_amb)
#tau2            = fit_tau2(cooling_tail, T_amb)
#beta            = fit_beta(short_pulse, Q_high, R_total, tau1, tau2, T_amb)

benchmarks_to_fit = [rise_fall]
schedules = [[(5, 3605)]]
benchmarks_to_fit = [multi_pulse]
schedules = [[
    (5, 10), (20, 30), (40, 55), (65, 85), (95, 120), (130, 160)
]]
Q, R, tau1, tau2, beta = fit_all(benchmarks_to_fit, schedules, T_amb)

print("\nCalibration complete.")
print(f"  Q={Q:.3f}, R={R:.3f} C/W, tau1={tau1:.3f} s, tau2={tau2:.3f} s, beta={beta:.3f}")
