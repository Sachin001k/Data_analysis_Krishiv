"""
Is the drift found in validate_cleaning.py "settling" (decelerating, curved,
flattening out) or "instrument drift" (constant-rate, straight-line the whole way)?

Method
------
1. Per-trial slope comparison: fit a straight line (np.polyfit, degree 1) to
   Total_N separately in the FIRST 10s and LAST 10s of each 30s trial.
     - If the process is settling/compacting, it should be losing force fastest
       at the start and flattening out later -> |early slope| > |late slope|.
     - If it's a constant-rate instrument drift, early and late slopes should
       be about equal -> |early slope| ~= |late slope|.
   We test this with a paired t-test across all 480 trials (same trial's own
   early vs late slope, so trial-to-trial noise cancels out).

2. Curve-shape comparison on a clean averaged signal: average the 10 trials of
   one version together (cancels random sensor noise, keeps the shared trend),
   then fit two competing models to that mean curve:
     - linear:      F(t) = a*t + b                (constant-rate drift)
     - exponential decay: F(t) = F_inf + (F0 - F_inf) * exp(-t / tau)
                                                    (settling toward equilibrium)
   Compare R^2 of each fit. Settling processes are exponential-shaped
   (fast then flattening); pure drift is linear-shaped equally well by both,
   but if exponential fits meaningfully better, that's evidence for settling.

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/check_drift_shape.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "clean_trials.parquet"
FIG_DIR = REPO_ROOT / "analysis" / "figures"

EARLY_WINDOW_S = (0, 10)     # first 10 seconds of each 30s trial
LATE_WINDOW_S = (20, 30)     # last 10 seconds of each 30s trial
EXAMPLE_VERSION = 10         # same version used in figure 3, for continuity


def slope_in_window(trial: pd.DataFrame, t0_s: float, t1_s: float) -> float:
    t_s = trial["time_ms"] / 1000
    mask = (t_s >= t0_s) & (t_s < t1_s)
    m, _b = np.polyfit(t_s[mask], trial["Total_N"][mask], 1)
    return m


def part1_early_vs_late(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (v, t), trial in df.groupby(["version_num", "trial"]):
        trial = trial.sort_values("time_ms")
        rows.append({
            "version_num": v,
            "trial": t,
            "early_slope": slope_in_window(trial, *EARLY_WINDOW_S),
            "late_slope": slope_in_window(trial, *LATE_WINDOW_S),
        })
    slopes = pd.DataFrame(rows)

    t_stat, p_value = stats.ttest_rel(slopes["early_slope"], slopes["late_slope"])
    print("=== Part 1: early-window slope vs late-window slope (paired, n=480) ===")
    print(f"mean early slope (0-10s):  {slopes['early_slope'].mean():+.5f} N/s")
    print(f"mean late slope (20-30s):  {slopes['late_slope'].mean():+.5f} N/s")
    print(f"paired t-test: t={t_stat:.2f}, p={p_value:.2e}")
    early_mag = abs(slopes["early_slope"].mean())
    late_mag = abs(slopes["late_slope"].mean())
    if p_value >= 0.05:
        print("-> early and late slopes are not significantly different: "
              "consistent with CONSTANT-RATE drift.")
    elif late_mag > early_mag:
        print("-> late slope is significantly MORE negative than early slope: "
              "drift is ACCELERATING over the trial. This rules out simple "
              "flattening/settling-to-equilibrium -- something is making force "
              "loss speed UP, not slow down.")
    else:
        print("-> early slope is significantly MORE negative than late slope: "
              "drift is DECELERATING (consistent with settling toward equilibrium).")
    print()

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.scatter(slopes["early_slope"], slopes["late_slope"], s=14, alpha=0.4,
               color="#2b6cb0", edgecolor="none")
    lims = [slopes[["early_slope", "late_slope"]].min().min() - 0.005,
            slopes[["early_slope", "late_slope"]].max().max() + 0.005]
    ax.plot(lims, lims, color="#c0392b", linestyle="--", linewidth=1.2,
            label="early = late (pure constant-rate drift)")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("slope, first 10s (N/s)")
    ax.set_ylabel("slope, last 10s (N/s)")
    ax.set_title("Early vs. late drift rate, all 480 trials\n"
                  "(below the line = decelerating = settling-like)")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    out = FIG_DIR / "05_early_vs_late_slope.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}\n")
    return slopes


def linear_model(t, a, b):
    return a * t + b


def exp_model(t, f_inf, f0, tau):
    return f_inf + (f0 - f_inf) * np.exp(-t / tau)


def part2_shape_fit(df: pd.DataFrame, version: int = EXAMPLE_VERSION):
    subset = df[df.version_num == version]
    mean_curve = subset.groupby("time_ms")["Total_N"].mean().sort_index()
    t_s = mean_curve.index.to_numpy() / 1000
    f = mean_curve.to_numpy()

    lin_params, _ = curve_fit(linear_model, t_s, f)
    lin_pred = linear_model(t_s, *lin_params)
    lin_r2 = 1 - np.sum((f - lin_pred) ** 2) / np.sum((f - f.mean()) ** 2)

    exp_params, _ = curve_fit(exp_model, t_s, f, p0=[f[-1], f[0], 5.0], maxfev=10000)
    exp_pred = exp_model(t_s, *exp_params)
    exp_r2 = 1 - np.sum((f - exp_pred) ** 2) / np.sum((f - f.mean()) ** 2)

    print(f"=== Part 2: curve shape on version V{version}'s 10-trial mean curve ===")
    print(f"linear fit:      R^2 = {lin_r2:.5f}   (a={lin_params[0]:.5f} N/s, b={lin_params[1]:.3f} N)")
    print(f"exponential fit: R^2 = {exp_r2:.5f}   "
          f"(F_inf={exp_params[0]:.3f} N, F0={exp_params[1]:.3f} N, tau={exp_params[2]:.2f} s)")
    if exp_r2 - lin_r2 > 0.01:
        print("-> exponential fits meaningfully better: shape is consistent with SETTLING "
              "(fast initial loss, flattening toward an equilibrium force).")
    else:
        print("-> linear and exponential fit about equally well: no strong evidence of "
              "flattening within 30s -- can't rule out simple constant drift from this alone.")
    print()

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(t_s, f, color="#9aa5b1", linewidth=1.5, label="mean of 10 trials (raw)")
    ax.plot(t_s, lin_pred, color="#c0392b", linewidth=1.8, linestyle="--",
            label=f"linear fit (R²={lin_r2:.4f})")
    ax.plot(t_s, exp_pred, color="#2b6cb0", linewidth=1.8,
            label=f"exponential decay fit (R²={exp_r2:.4f})")
    ax.set_xlabel("time (s)")
    ax.set_ylabel("Total force (N)")
    ax.set_title(f"Which shape fits the drift better? V{version} mean curve")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out = FIG_DIR / "06_drift_shape_fit.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


def main():
    df = pd.read_parquet(DATA_PATH)
    part1_early_vs_late(df)
    part2_shape_fit(df)


if __name__ == "__main__":
    main()
