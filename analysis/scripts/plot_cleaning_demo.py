"""
Phase 1 cleaning/validation plots: run this once load_data.py has produced
analysis/data/processed/clean_trials.parquet.

Produces three figures in analysis/figures/:
  01_raw_vs_smoothed.png   - what "cleaning" (smoothing) does to one trial's signal
  02_baseline_calibration.png - measured resting force vs expected static weight,
                                 per version -> tells us how well-calibrated the rig is
  03_trial_repeatability.png  - all 10 raw trials of one version overlaid ->
                                 tells us how much trial-to-trial noise there is

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/plot_cleaning_demo.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "clean_trials.parquet"
FIG_DIR = REPO_ROOT / "analysis" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#444444",
    "axes.grid": True,
    "grid.color": "#e0e0e0",
    "grid.linewidth": 0.6,
    "font.size": 11,
})

RAW_COLOR = "#9aa5b1"      # muted grey-blue for raw signal
SMOOTH_COLOR = "#2b6cb0"   # stronger blue for cleaned signal
ACCENT = "#c0392b"


def fig_raw_vs_smoothed(df: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), sharey=False)

    examples = [
        (1, 1, "V1 t1 - low density, no obstacle"),
        (22, 1, "V22 t1 - obstacle present (S-shape)"),
    ]
    for ax, (v, t, title) in zip(axes, examples):
        trial = df[(df.version_num == v) & (df.trial == t)].sort_values("time_ms")
        smoothed = trial["Total_N"].rolling(window=5, center=True, min_periods=1).mean()

        ax.plot(trial["time_ms"] / 1000, trial["Total_N"], color=RAW_COLOR,
                linewidth=1, label="raw")
        ax.plot(trial["time_ms"] / 1000, smoothed, color=SMOOTH_COLOR,
                linewidth=1.8, label="smoothed (rolling mean, 5 samples)")
        ax.set_title(title, fontsize=11)
        ax.set_xlabel("time (s)")
        ax.set_ylabel("Total force (N)")
        ax.legend(frameon=False, fontsize=9, loc="upper right")

    fig.suptitle("Raw vs. smoothed signal - smoothing removes sensor jitter\n"
                  "without touching the underlying trend", fontsize=12)
    fig.tight_layout(rect=[0, 0, 1, 0.92])
    out = FIG_DIR / "01_raw_vs_smoothed.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


def fig_baseline_calibration(df: pd.DataFrame):
    baseline = (
        df.groupby(["version_num", "trial"])
        .agg(baseline_total_N=("baseline_total_N", "first"),
             expected_total_N=("expected_total_N", "first"))
        .reset_index()
    )

    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(baseline["expected_total_N"], baseline["baseline_total_N"],
               s=18, alpha=0.5, color=SMOOTH_COLOR, edgecolor="none")

    lims = [baseline[["expected_total_N", "baseline_total_N"]].min().min() - 1,
            baseline[["expected_total_N", "baseline_total_N"]].max().max() + 1]
    ax.plot(lims, lims, color=ACCENT, linewidth=1.2, linestyle="--",
            label="perfect calibration (y = x)")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("expected static weight, from INDEX.csv (N)")
    ax.set_ylabel("measured resting force, first 1s of trial (N)")
    ax.set_title("Sensor calibration check: measured vs. expected\n"
                  "(480 trials - points on the line = well-calibrated)")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out = FIG_DIR / "02_baseline_calibration.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


def fig_trial_repeatability(df: pd.DataFrame, version: int = 10):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    subset = df[df.version_num == version]
    for t, trial in subset.groupby("trial"):
        trial = trial.sort_values("time_ms")
        ax.plot(trial["time_ms"] / 1000, trial["Total_N"], linewidth=1, alpha=0.7)

    mean_curve = (
        subset.groupby("time_ms")["Total_N"].mean().sort_index()
    )
    ax.plot(mean_curve.index / 1000, mean_curve.values, color="black",
            linewidth=2.2, label="mean across 10 trials")

    ax.set_xlabel("time (s)")
    ax.set_ylabel("Total force (N)")
    ax.set_title(f"Trial-to-trial repeatability, version V{version}\n"
                 f"(10 overlaid raw trials + their mean)")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out = FIG_DIR / "03_trial_repeatability.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


def main():
    df = pd.read_parquet(DATA_PATH)
    fig_raw_vs_smoothed(df)
    fig_baseline_calibration(df)
    fig_trial_repeatability(df)


if __name__ == "__main__":
    main()
