"""
Phase 4c: obstacle geometry effects, using V13-V48 (36 versions, all at the
same fixed density -- 600 balls, equal ratio -- varying only obstacle_shape
(2) x obstacle_size_cm (3) x obstacle_angle_deg (3) x obstacle_position (2),
a full factorial design, 10 trials each = 360 trials).

Outcomes tested (each captures a different notion of "how dangerous"):
  - redistribution_strength = |front_back_redistribution| : how strongly the
    obstacle forces a front<->back load shift (see Phase 3 notes in
    build_features.py for why this replaced a lag-based wave metric).
  - fluctuation_std_N : raw instability of the force signal.
  - spike_above_baseline_N = peak_total_N - baseline_total_N : how far above
    resting load the trial's worst moment reaches.

For each outcome: a factorial ANOVA (main effects + all 2-way interactions;
3-way+ interactions omitted since 10 reps/cell gives them very low power) to
rank which obstacle parameter matters most, plus a version-level "danger
ranking" table.

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/obstacle_factor_analysis.py
"""

from pathlib import Path

import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "trial_features.csv"
OUT_DIR = REPO_ROOT / "analysis" / "results"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FACTORS = ["obstacle_shape", "obstacle_size_cm", "obstacle_angle_deg", "obstacle_position"]
OUTCOMES = {
    "redistribution_strength": None,  # computed below
    "fluctuation_std_N": "fluctuation_std_N",
    "spike_above_baseline_N": None,   # computed below
}


def run_anova(df: pd.DataFrame, outcome: str) -> pd.DataFrame:
    formula = f"{outcome} ~ (C(obstacle_shape) + C(obstacle_size_cm) + C(obstacle_angle_deg) + C(obstacle_position))**2"
    model = smf.ols(formula, data=df).fit()
    table = sm.stats.anova_lm(model, typ=2)
    table["pct_variance_explained"] = table["sum_sq"] / table["sum_sq"].sum() * 100
    return table.sort_values("PR(>F)")


def danger_ranking(df: pd.DataFrame, outcome: str, top_n: int = 5) -> pd.DataFrame:
    agg = (
        df.groupby("version_num")
        .agg(
            mean_outcome=(outcome, "mean"),
            std_outcome=(outcome, "std"),
            obstacle_shape=("obstacle_shape", "first"),
            obstacle_size_cm=("obstacle_size_cm", "first"),
            obstacle_angle_deg=("obstacle_angle_deg", "first"),
            obstacle_position=("obstacle_position", "first"),
        )
        .reset_index()
        .sort_values("mean_outcome", ascending=False)
    )
    return agg


def main():
    f = pd.read_csv(DATA_PATH)
    obs = f[f["obstacle_shape"] != "none"].copy()
    print(f"Obstacle trials: {len(obs)} rows across {obs['version_num'].nunique()} versions "
          f"(expect 360 rows, 36 versions)\n")

    obs["redistribution_strength"] = obs["front_back_redistribution"].abs()
    obs["spike_above_baseline_N"] = obs["peak_total_N"] - obs["baseline_total_N"]

    for outcome in OUTCOMES:
        print(f"{'=' * 70}\nOUTCOME: {outcome}\n{'=' * 70}")

        anova_table = run_anova(obs, outcome)
        print("\nFactorial ANOVA (sorted by significance):")
        print(anova_table.round(4).to_string())
        anova_table.to_csv(OUT_DIR / f"anova_{outcome}.csv")

        print("\nTop 5 most dangerous configurations:")
        ranking = danger_ranking(obs, outcome)
        print(ranking.head(5)[[
            "version_num", "mean_outcome", "std_outcome", "obstacle_shape",
            "obstacle_size_cm", "obstacle_angle_deg", "obstacle_position",
        ]].to_string(index=False))

        print("\nBottom 5 (safest) configurations:")
        print(ranking.tail(5)[[
            "version_num", "mean_outcome", "std_outcome", "obstacle_shape",
            "obstacle_size_cm", "obstacle_angle_deg", "obstacle_position",
        ]].to_string(index=False))
        ranking.to_csv(OUT_DIR / f"ranking_{outcome}.csv", index=False)
        print()


if __name__ == "__main__":
    main()
