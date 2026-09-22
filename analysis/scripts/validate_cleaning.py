"""
Numerically validate what figures 01-03 showed visually:
  - is the calibration actually y=x, or just "close by eye"?
  - is the downward drift seen in V10 (fig 3) a one-off, or present everywhere?

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/validate_cleaning.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "clean_trials.parquet"
FIG_DIR = REPO_ROOT / "analysis" / "figures"


def check_calibration(df: pd.DataFrame):
    baseline = (
        df.groupby(["version_num", "trial"])
        .agg(baseline_total_N=("baseline_total_N", "first"),
             expected_total_N=("expected_total_N", "first"))
        .reset_index()
    )
    slope, intercept, r, p, se = stats.linregress(
        baseline["expected_total_N"], baseline["baseline_total_N"]
    )
    pct_err = (baseline["baseline_total_N"] - baseline["expected_total_N"]) / baseline["expected_total_N"] * 100

    print("=== Calibration check (measured baseline vs. expected static weight) ===")
    print(f"linear fit: measured = {slope:.4f} * expected + {intercept:.4f}   (R^2 = {r**2:.5f})")
    print(f"  perfect calibration would be slope=1.0, intercept=0.0")
    print(f"mean % error: {pct_err.mean():+.3f}%   std: {pct_err.std():.3f}%   "
          f"max |error|: {pct_err.abs().max():.3f}%")
    print()


def check_drift(df: pd.DataFrame):
    slopes = []
    for (v, t), trial in df.groupby(["version_num", "trial"]):
        trial = trial.sort_values("time_ms")
        m, b = np.polyfit(trial["time_ms"] / 1000, trial["Total_N"], 1)
        slopes.append({"version_num": v, "trial": t, "drift_N_per_s": m})
    drift_df = pd.DataFrame(slopes)

    frac_negative = (drift_df["drift_N_per_s"] < 0).mean() * 100
    print("=== Drift check (linear trend of Total_N over each 30s trial) ===")
    print(f"mean drift: {drift_df['drift_N_per_s'].mean():+.5f} N/s   "
          f"std: {drift_df['drift_N_per_s'].std():.5f} N/s")
    print(f"{frac_negative:.1f}% of all 480 trials show a NEGATIVE drift (force decreasing over time)")
    print(f"median drift: {drift_df['drift_N_per_s'].median():+.5f} N/s")

    # is drift bigger for higher-density / obstacle trials?
    merged = drift_df.merge(
        df[["version_num", "packing_fraction", "obstacle_shape"]].drop_duplicates("version_num"),
        on="version_num", how="left",
    )
    by_obstacle = merged.groupby(merged["obstacle_shape"] == "none")["drift_N_per_s"].mean()
    print("\nmean drift, no-obstacle trials (V1-V12) vs obstacle trials (V13-V48):")
    print(by_obstacle.rename({True: "no obstacle", False: "obstacle"}))

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.hist(drift_df["drift_N_per_s"], bins=40, color="#2b6cb0", alpha=0.85)
    ax.axvline(0, color="#c0392b", linestyle="--", linewidth=1.2, label="no drift")
    ax.set_xlabel("linear drift over trial (N/s)")
    ax.set_ylabel("number of trials")
    ax.set_title("Is the downward drift in V10 a one-off or universal?\n"
                  f"Distribution of drift across all 480 trials "
                  f"({frac_negative:.0f}% negative)")
    ax.legend(frameon=False)
    fig.tight_layout()
    out = FIG_DIR / "04_drift_distribution.png"
    fig.savefig(out, dpi=150)
    print(f"\nSaved {out}")

    return drift_df


def main():
    df = pd.read_parquet(DATA_PATH)
    check_calibration(df)
    check_drift(df)


if __name__ == "__main__":
    main()
