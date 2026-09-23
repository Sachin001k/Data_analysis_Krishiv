"""
Phase 4a: density -> pressure relationship, using V1-V12 (no obstacle).

Important framing note: plotting raw Total_N vs packing_fraction mostly just
reproduces F = m*g (more balls -> more weight on a scale), which the
calibration check already confirmed holds almost perfectly overall
(measured = 0.999*expected, R^2=0.9998). That is NOT the "pressure builds up
nonlinearly with density" claim from the proposal -- that claim is about
internal structural effects (arching, wall friction shielding some of the
weight, force-chain formation) causing the force AT THE SENSOR to deviate
from simple total weight as packing gets denser. So this script tests two
things that actually isolate that effect instead of just re-deriving gravity:

  1. % deviation of measured baseline force from the theoretical expected
     weight, AS A FUNCTION OF packing fraction -- if arching/shielding
     effects exist and grow with density, this deviation should trend
     systematically (not just be scattered around 0).
  2. Coefficient of variation of the force signal (fluctuation_std_N /
     mean_total_N) vs packing fraction -- this is a normalized "how unstable
     / bouncy is the packing" measure, independent of the trivial
     more-balls-more-weight effect, and is the more direct read on the
     proposal's "conditions become dangerous" framing.

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/density_pressure_analysis.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "trial_features.csv"
FIG_DIR = REPO_ROOT / "analysis" / "figures"

RATIO_COLORS = {"equal": "#2b6cb0", "1:3": "#c0392b", "3:1": "#27883b"}


def main():
    f = pd.read_csv(DATA_PATH)
    noob = f[f["obstacle_shape"] == "none"].copy()
    noob["pct_error"] = (
        (noob["baseline_total_N"] - noob["expected_total_N"]) / noob["expected_total_N"] * 100
    )
    noob["cv_fluctuation"] = noob["fluctuation_std_N"] / noob["mean_total_N"]

    # ---- per-version summary across the 10 trials ----
    summary = (
        noob.groupby("version_num")
        .agg(
            packing_fraction=("packing_fraction", "first"),
            ratio=("ratio_10mm_13mm", "first"),
            pct_error_mean=("pct_error", "mean"),
            pct_error_std=("pct_error", "std"),
            cv_mean=("cv_fluctuation", "mean"),
            cv_std=("cv_fluctuation", "std"),
        )
        .reset_index()
        .sort_values("packing_fraction")
    )
    print("=== Per-version summary (V1-V12, no obstacle) ===")
    print(summary.to_string(index=False))
    print()

    # Does % error trend with density overall?
    r_err, p_err = stats.pearsonr(noob["packing_fraction"], noob["pct_error"])
    print(f"correlation(packing_fraction, % error vs expected weight) = {r_err:.3f}  (p={p_err:.3f})")

    # Does fluctuation CV trend with density overall?
    r_cv, p_cv = stats.pearsonr(noob["packing_fraction"], noob["cv_fluctuation"])
    print(f"correlation(packing_fraction, fluctuation CV) = {r_cv:.3f}  (p={p_cv:.3f})")
    print()

    # ---- figure ----
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))

    for ratio, group in summary.groupby("ratio"):
        axes[0].errorbar(
            group["packing_fraction"], group["pct_error_mean"], yerr=group["pct_error_std"],
            fmt="o", label=ratio, color=RATIO_COLORS.get(ratio, "gray"), capsize=3,
        )
    axes[0].axhline(0, color="black", linestyle="--", linewidth=1, label="no deviation")
    axes[0].set_xlabel("packing fraction (density)")
    axes[0].set_ylabel("% deviation: measured vs. expected static weight")
    axes[0].set_title("Does structure (arching/friction) start hiding\nweight from the sensor as density rises?")
    axes[0].legend(frameon=False, fontsize=8, title="ball size ratio")

    for ratio, group in summary.groupby("ratio"):
        axes[1].errorbar(
            group["packing_fraction"], group["cv_mean"], yerr=group["cv_std"],
            fmt="o", label=ratio, color=RATIO_COLORS.get(ratio, "gray"), capsize=3,
        )
    axes[1].set_xlabel("packing fraction (density)")
    axes[1].set_ylabel("coefficient of variation of force signal")
    axes[1].set_title("Does the packing get proportionally\nmore unstable/fluctuating as density rises?")
    axes[1].legend(frameon=False, fontsize=8, title="ball size ratio")

    fig.tight_layout()
    out = FIG_DIR / "08_density_pressure_relationship.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
