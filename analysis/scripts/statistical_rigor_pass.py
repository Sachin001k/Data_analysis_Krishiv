"""
Phase 5: statistical rigor pass on the two headline claims so far.

1. Bootstrap confidence intervals (resampling trials with replacement, 5000
   times) for the two biggest point-estimate claims made so far:
     - redistribution_strength: obstacle vs. no-obstacle mean difference
     - correlation(packing_fraction, fluctuation CV) in the no-obstacle
       density sweep (a claim we already reported as "not quite significant"
       -- a CI shows exactly how uncertain it is, not just a single p-value)

2. A proper multiple-comparison-corrected post-hoc test (Tukey HSD) on
   obstacle_angle_deg, since the ANOVA only says "angle matters overall" --
   Tukey HSD tells us which SPECIFIC angle pairs (45 vs 60, 60 vs 75, 45 vs 75)
   are significantly different from each other, correcting for running
   multiple pairwise comparisons (avoids false positives from testing many
   pairs at once).

3. Tukey HSD across all 36 individual obstacle versions on
   redistribution_strength, to check whether the "top 5 most dangerous" /
   "bottom 5 safest" versions from the earlier ranking are actually
   statistically distinguishable from each other and from the middle of the
   pack, once we correct for comparing 36 groups at once (630 pairs).

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/statistical_rigor_pass.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.stats.multicomp import pairwise_tukeyhsd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "trial_features.csv"
RESULTS_DIR = REPO_ROOT / "analysis" / "results"
RNG = np.random.default_rng(42)
N_BOOT = 5000


def bootstrap_ci(values_a, values_b, statistic_fn, n_boot=N_BOOT):
    """Bootstrap CI for statistic_fn(a) - statistic_fn(b)."""
    diffs = np.empty(n_boot)
    for i in range(n_boot):
        sample_a = RNG.choice(values_a, size=len(values_a), replace=True)
        sample_b = RNG.choice(values_b, size=len(values_b), replace=True)
        diffs[i] = statistic_fn(sample_a) - statistic_fn(sample_b)
    return np.percentile(diffs, [2.5, 97.5]), diffs.mean()


def part1_bootstrap(f: pd.DataFrame):
    print("=== Part 1: bootstrap confidence intervals ===\n")

    f = f.copy()
    f["redistribution_strength"] = f["front_back_redistribution"].abs()
    obstacle_vals = f.loc[f.obstacle_shape != "none", "redistribution_strength"].to_numpy()
    no_obstacle_vals = f.loc[f.obstacle_shape == "none", "redistribution_strength"].to_numpy()

    ci, mean_diff = bootstrap_ci(obstacle_vals, no_obstacle_vals, np.mean)
    print(f"Redistribution strength, obstacle - no_obstacle:")
    print(f"  point estimate = {mean_diff:+.3f}")
    print(f"  95% bootstrap CI = [{ci[0]:+.3f}, {ci[1]:+.3f}]")
    print(f"  -> {'does NOT cross zero: robust effect' if ci[0] > 0 else 'crosses zero: NOT robust'}\n")

    noob = f[f.obstacle_shape == "none"].copy()
    noob["cv_fluctuation"] = noob["fluctuation_std_N"] / noob["mean_total_N"]

    def corr_stat(paired_idx, x=noob["packing_fraction"].to_numpy(), y=noob["cv_fluctuation"].to_numpy()):
        return np.corrcoef(x[paired_idx], y[paired_idx])[0, 1]

    n = len(noob)
    boot_corrs = np.empty(N_BOOT)
    for i in range(N_BOOT):
        idx = RNG.integers(0, n, size=n)
        boot_corrs[i] = corr_stat(idx)
    ci_corr = np.percentile(boot_corrs, [2.5, 97.5])
    print(f"correlation(packing_fraction, fluctuation CV), no-obstacle sweep:")
    print(f"  point estimate = {np.corrcoef(noob['packing_fraction'], noob['cv_fluctuation'])[0, 1]:.3f}")
    print(f"  95% bootstrap CI = [{ci_corr[0]:+.3f}, {ci_corr[1]:+.3f}]")
    print(f"  -> {'does NOT cross zero' if ci_corr[0] * ci_corr[1] > 0 else 'CROSSES zero: cannot claim a real trend'}\n")


def part2_tukey_angle(f: pd.DataFrame):
    print("=== Part 2: Tukey HSD on obstacle_angle_deg (corrected pairwise comparisons) ===\n")
    obs = f[f.obstacle_shape != "none"].copy()
    obs["redistribution_strength"] = obs["front_back_redistribution"].abs()
    result = pairwise_tukeyhsd(
        obs["redistribution_strength"], obs["obstacle_angle_deg"].astype(str), alpha=0.05
    )
    print(result)
    print()


def part3_tukey_versions(f: pd.DataFrame):
    print("=== Part 3: Tukey HSD across all 36 obstacle versions (630 corrected pairwise tests) ===\n")
    obs = f[f.obstacle_shape != "none"].copy()
    obs["redistribution_strength"] = obs["front_back_redistribution"].abs()
    result = pairwise_tukeyhsd(
        obs["redistribution_strength"], obs["version_num"].astype(str), alpha=0.05
    )
    table = pd.DataFrame(result.summary().data[1:], columns=result.summary().data[0])
    table.to_csv(RESULTS_DIR / "tukey_hsd_all_versions.csv", index=False)

    n_sig = table["reject"].sum()
    n_total = len(table)
    print(f"{n_sig} / {n_total} pairwise version comparisons remain significant after correction.")

    # Specifically check: is the #1 ranked version (V16, most dangerous) actually
    # significantly different from the versions ranked just below it?
    v16_rows = table[
        ((table["group1"] == "16") | (table["group2"] == "16"))
    ]
    print(f"\nOf V16's (top-ranked 'most dangerous') 35 pairwise comparisons, "
          f"{v16_rows['reject'].sum()} are statistically significant after correction.")
    print(f"Saved full table to {RESULTS_DIR / 'tukey_hsd_all_versions.csv'}")


def main():
    f = pd.read_csv(DATA_PATH)
    part1_bootstrap(f)
    part2_tukey_angle(f)
    part3_tukey_versions(f)


if __name__ == "__main__":
    main()
