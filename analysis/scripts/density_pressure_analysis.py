"""
Phase 4a: density -> pressure relationship (Objective 1).

Uses only the no-obstacle block (V1-V12: 4 ball counts x 3 size ratios,
120 trials) from analysis/data/processed/trial_features.csv. Answers:

  - How does packing density (phi_after_compression) relate to static load
    (mean_total_N) and to "pressure wave energy" (fluctuation_std_N)?
  - Is the relationship better described as linear (just more balls -> more
    weight) or as a threshold/hinge model (flat, then rising sharply past a
    critical density), as the proposal predicts?
  - Does the single_layer -> NO_partial_2nd_layer transition (V10, V11) line
    up with that critical density?
  - Does particle-size mix (ratio_10mm_13mm) change the force response at
    matched total_balls?

Outputs:
  analysis/results/density_pressure_summary.csv   - per-version mean/std/95% CI
  analysis/results/density_pressure_fits.csv       - linear vs hinge fit params + R2/RMSE
  analysis/results/density_pressure_stats.csv      - single-layer t-test + per-count ratio ANOVA
  analysis/figures/08_density_pressure.png         - Fig 3: force & fluctuation vs phi, with fit

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/density_pressure_analysis.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).resolve().parents[2]
FEATURES_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "trial_features.csv"
RESULTS_DIR = REPO_ROOT / "analysis" / "results"
FIG_DIR = REPO_ROOT / "analysis" / "figures"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

DENSITY_COL = "phi_after_compression"

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": "#444444",
    "axes.grid": True,
    "grid.color": "#e1e0d9",
    "grid.linewidth": 0.6,
    "font.size": 11,
})

BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"
ACCENT = "#c0392b"
MUTED = "#898781"

RATIO_COLORS = {"equal": BLUE, "1:3": ORANGE, "3:1": AQUA}


def hinge_model(phi, a, b, c, phi_c):
    """Piecewise-linear "threshold" model: flat-ish slope b below phi_c,
    slope b + c above it. Continuous at phi_c by construction."""
    return a + b * phi + c * np.clip(phi - phi_c, 0, None)


def fit_linear_and_hinge(phi, y):
    lin_coef = np.polyfit(phi, y, 1)
    lin_pred = np.polyval(lin_coef, phi)
    lin_r2 = 1 - np.sum((y - lin_pred) ** 2) / np.sum((y - y.mean()) ** 2)
    lin_rmse = np.sqrt(np.mean((y - lin_pred) ** 2))

    phi_c0 = np.median(phi)
    p0 = [y.min(), 0.0, (y.max() - y.min()) / max(phi.max() - phi_c0, 1e-6), phi_c0]
    bounds = (
        [-np.inf, -np.inf, -np.inf, phi.min()],
        [np.inf, np.inf, np.inf, phi.max()],
    )
    try:
        popt, _ = curve_fit(hinge_model, phi, y, p0=p0, bounds=bounds, maxfev=20000)
        hinge_pred = hinge_model(phi, *popt)
        hinge_r2 = 1 - np.sum((y - hinge_pred) ** 2) / np.sum((y - y.mean()) ** 2)
        hinge_rmse = np.sqrt(np.mean((y - hinge_pred) ** 2))
    except RuntimeError:
        popt, hinge_r2, hinge_rmse = [np.nan] * 4, np.nan, np.nan

    return {
        "linear_slope": lin_coef[0], "linear_intercept": lin_coef[1],
        "linear_r2": lin_r2, "linear_rmse": lin_rmse,
        "hinge_a": popt[0], "hinge_b_below": popt[1], "hinge_c_extra_above": popt[2],
        "hinge_phi_c": popt[3], "hinge_r2": hinge_r2, "hinge_rmse": hinge_rmse,
    }


def summarize_by_version(df: pd.DataFrame) -> pd.DataFrame:
    metrics = ["mean_total_N", "fluctuation_std_N", "frame_to_frame_rms_N", "peak_total_N"]
    rows = []
    for version, g in df.groupby("version", sort=False):
        row = {
            "version": version,
            "total_balls": g["total_balls"].iloc[0],
            "ratio_10mm_13mm": g["ratio_10mm_13mm"].iloc[0],
            "packing_fraction": g["packing_fraction"].iloc[0],
            "phi_after_compression": g[DENSITY_COL].iloc[0],
            "single_layer": g["single_layer"].iloc[0],
            "n_trials": len(g),
        }
        for m in metrics:
            vals = g[m].dropna()
            se = vals.std(ddof=1) / np.sqrt(len(vals))
            ci95 = 1.96 * se
            row[f"{m}_mean"] = vals.mean()
            row[f"{m}_std"] = vals.std(ddof=1)
            row[f"{m}_ci95"] = ci95
        rows.append(row)
    out = pd.DataFrame(rows).sort_values("phi_after_compression").reset_index(drop=True)
    return out


def run_fits(df: pd.DataFrame) -> pd.DataFrame:
    phi = df[DENSITY_COL].to_numpy()
    fits = []
    for metric in ["mean_total_N", "fluctuation_std_N", "frame_to_frame_rms_N"]:
        y = df[metric].to_numpy()
        res = fit_linear_and_hinge(phi, y)
        res["metric"] = metric
        fits.append(res)
    return pd.DataFrame(fits)[[
        "metric", "linear_slope", "linear_intercept", "linear_r2", "linear_rmse",
        "hinge_a", "hinge_b_below", "hinge_c_extra_above", "hinge_phi_c",
        "hinge_r2", "hinge_rmse",
    ]]


def single_layer_comparison(df: pd.DataFrame) -> list[dict]:
    yes = df[df["single_layer"] == "yes"]
    no = df[df["single_layer"] == "NO_partial_2nd_layer"]
    rows = []
    for metric in ["mean_total_N", "fluctuation_std_N", "frame_to_frame_rms_N", "peak_total_N"]:
        t, p = stats.ttest_ind(no[metric], yes[metric], equal_var=False)
        rows.append({
            "comparison": "single_layer",
            "metric": metric,
            "group_a": "NO_partial_2nd_layer", "group_a_mean": no[metric].mean(), "group_a_n": len(no),
            "group_b": "yes", "group_b_mean": yes[metric].mean(), "group_b_n": len(yes),
            "welch_t": t, "p_value": p,
        })
    return rows


def ratio_comparison(df: pd.DataFrame) -> list[dict]:
    rows = []
    for metric in ["mean_total_N", "fluctuation_std_N", "frame_to_frame_rms_N"]:
        for balls, g in df.groupby("total_balls"):
            groups = [grp[metric].to_numpy() for _, grp in g.groupby("ratio_10mm_13mm")]
            f, p = stats.f_oneway(*groups)
            rows.append({
                "comparison": "ratio_at_matched_total_balls",
                "metric": metric,
                "total_balls": balls,
                "f_stat": f, "p_value": p,
                "n_per_group": [len(x) for x in groups],
            })
    return rows


def fig_density_pressure(trial_df: pd.DataFrame, version_summary: pd.DataFrame, fits: pd.DataFrame):
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    panels = [
        (axes[0], "mean_total_N", "Mean total force (N)"),
        (axes[1], "fluctuation_std_N", "Fluctuation std, detrended (N) -\n'pressure wave energy'"),
    ]

    phi_grid = np.linspace(trial_df[DENSITY_COL].min(), trial_df[DENSITY_COL].max(), 200)

    for ax, metric, ylabel in panels:
        for ratio in ["equal", "1:3", "3:1"]:
            g = trial_df[trial_df["ratio_10mm_13mm"] == ratio]
            ax.scatter(g[DENSITY_COL], g[metric], s=14, alpha=0.35,
                       color=RATIO_COLORS[ratio], edgecolor="none", label=f"ratio {ratio}")

        vs = version_summary
        ax.errorbar(vs[DENSITY_COL], vs[f"{metric}_mean"], yerr=vs[f"{metric}_ci95"],
                    fmt="o", color="#0b0b0b", ecolor="#0b0b0b", elinewidth=1.2,
                    capsize=3, markersize=5, label="version mean (95% CI)", zorder=5)

        row = fits[fits["metric"] == metric].iloc[0]
        hinge_pred = hinge_model(phi_grid, row["hinge_a"], row["hinge_b_below"],
                                  row["hinge_c_extra_above"], row["hinge_phi_c"])
        ax.plot(phi_grid, hinge_pred, color=ACCENT, linewidth=1.8,
                label=f"hinge fit (R²={row['hinge_r2']:.2f})")
        ax.axvline(row["hinge_phi_c"], color=ACCENT, linewidth=1, linestyle="--", alpha=0.6)
        ax.text(row["hinge_phi_c"], ax.get_ylim()[1], f"  φ_c={row['hinge_phi_c']:.2f}",
                color=ACCENT, fontsize=9, va="top")

        no_layer_phi = trial_df.loc[trial_df["single_layer"] == "NO_partial_2nd_layer", DENSITY_COL].min()
        ax.axvline(no_layer_phi, color=MUTED, linewidth=1, linestyle=":", alpha=0.8)

        ax.set_xlabel("packing fraction after compression, φ")
        ax.set_ylabel(ylabel)
        ax.legend(frameon=False, fontsize=8, loc="upper left")

    fig.suptitle(
        "Density → pressure (V1–V12, no obstacle, 120 trials)\n"
        "dotted grey line = onset of partial 2nd layer (V10/V11)",
        fontsize=12,
    )
    fig.tight_layout(rect=[0, 0, 1, 0.90])
    out = FIG_DIR / "08_density_pressure.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


def main():
    df = pd.read_csv(FEATURES_PATH)
    df = df[df["obstacle_shape"] == "none"].copy()
    assert df["version"].nunique() == 12 and len(df) == 120, \
        f"expected 12 versions / 120 trials, got {df['version'].nunique()} / {len(df)}"

    version_summary = summarize_by_version(df)
    version_summary.to_csv(RESULTS_DIR / "density_pressure_summary.csv", index=False)

    fits = run_fits(df)
    fits.to_csv(RESULTS_DIR / "density_pressure_fits.csv", index=False)

    stat_rows = single_layer_comparison(df) + ratio_comparison(df)
    pd.DataFrame(stat_rows).to_csv(RESULTS_DIR / "density_pressure_stats.csv", index=False)

    fig_density_pressure(df, version_summary, fits)

    print("\n=== Per-version summary (sorted by phi_after_compression) ===")
    print(version_summary[[
        "version", "total_balls", "ratio_10mm_13mm", "phi_after_compression",
        "single_layer", "mean_total_N_mean", "fluctuation_std_N_mean",
    ]].to_string(index=False))

    print("\n=== Linear vs hinge (threshold) fits ===")
    print(fits.to_string(index=False))

    print("\n=== Single-layer group comparison (Welch t-test) ===")
    for r in single_layer_comparison(df):
        print(f"{r['metric']:>22}: NO_2nd_layer mean={r['group_a_mean']:.3f} (n={r['group_a_n']}) "
              f"vs yes mean={r['group_b_mean']:.3f} (n={r['group_b_n']}) "
              f"t={r['welch_t']:.2f} p={r['p_value']:.4g}")

    print("\n=== Ratio comparison at matched total_balls (one-way ANOVA) ===")
    for r in ratio_comparison(df):
        print(f"{r['metric']:>22} | total_balls={r['total_balls']}: F={r['f_stat']:.2f} p={r['p_value']:.4g}")


if __name__ == "__main__":
    main()
