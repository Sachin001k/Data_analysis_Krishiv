"""
Phase 3: build one row per trial (480 rows) of physics-motivated features,
merged with INDEX.csv metadata. This is the table Phase 4 analyses run on.

Drift policy (see CLAUDE.md / session discussion):
  - baseline_total_N: mean of first 1s -> already-validated calibration reference,
    used for any "static/resting force" comparison across versions.
  - drift_slope_N_per_s: linear trend over the WHOLE trial -> kept as a feature
    in its own right (settling rate), not just discarded as nuisance.
  - fluctuation/wave features are computed on DETRENDED residuals (raw signal
    minus its own linear fit) so the systematic decay doesn't get counted as
    "wave energy".

Wave-lag method note (important):
  The original design cross-correlated detrended residuals to find a "lag of
  peak correlation" between sensor rows, assuming a fast disturbance arrives
  at one row and shows up slightly later at another. Validated against all
  480 trials: this NEVER reliably fires (peak correlation stays ~0.11-0.16
  everywhere, below any sane threshold, even in obstacle trials) -- there is
  no fast delayed-copy relationship in this data at 8 Hz.
  What actually carries signal is the RAW (non-detrended) whole-trial
  correlation between rows: front and back force move in anti-phase as the
  packing settles (correlation ~ -0.4 to -0.99), i.e. force redistributes
  from one row to another rather than arriving late. This anti-correlation
  is stronger and far more consistent with an obstacle present (mean -0.81,
  std 0.11) than without one (mean -0.40, std 0.31), and moderately tracks
  packing fraction in the no-obstacle density sweep (r=0.50 with |corr|).
  Both feature families are kept below: `*_redistribution` (the validated,
  meaningful one) and `lag_*` / `corr_*_residual` (kept for completeness /
  transparency, but treat as unreliable per-trial noise).

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/build_features.py
"""

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import correlate

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "clean_trials.parquet"
OUT_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "trial_features.csv"

SAMPLE_DT_S = 0.125  # 8 Hz

# A physical bound on how far to search for the peak correlation. This rig is
# small (front/middle/back rows a few cm apart); a real stress wave should
# cross it in well under a second, not minutes. Searching the full +/-30s
# range picks up noise peaks (verified: peak correlation strength was ~equal
# for "found" lags of 500ms and 15000ms, which is only possible if the peak
# is noise, not signal). 3s is a generous margin above what's physically
# plausible while still ruling out the spurious far-out peaks.
MAX_LAG_S = 3.0

# Below this normalized peak-correlation value, treat the "detected lag" as
# unreliable (no coherent propagating signal, just uncorrelated sensor noise)
# and report NaN rather than a specific but meaningless number.
MIN_RELIABLE_CORR = 0.3


def detrend(t_s: np.ndarray, y: np.ndarray) -> np.ndarray:
    a, b = np.polyfit(t_s, y, 1)
    return y - (a * t_s + b), a


def lag_of_peak_correlation(a: np.ndarray, b: np.ndarray) -> tuple[float, float]:
    """Cross-correlate two detrended signals within +/-MAX_LAG_S; return
    (lag in ms, peak normalized corr). Positive lag means `b` lags behind `a`
    (a's pattern appears first). Lag is NaN if the peak correlation doesn't
    clear MIN_RELIABLE_CORR (i.e. no coherent wave, just noise)."""
    a = a - a.mean()
    b = b - b.mean()
    corr = correlate(b, a, mode="full")
    lags = np.arange(-len(a) + 1, len(a))

    max_lag_samples = int(round(MAX_LAG_S / SAMPLE_DT_S))
    window = np.abs(lags) <= max_lag_samples
    lags, corr = lags[window], corr[window]

    norm = np.sqrt(np.sum(a**2) * np.sum(b**2))
    corr_norm = corr / norm if norm > 0 else corr
    peak_idx = np.argmax(corr_norm)
    peak_corr = corr_norm[peak_idx]
    lag_ms = lags[peak_idx] * SAMPLE_DT_S * 1000
    return (lag_ms if peak_corr >= MIN_RELIABLE_CORR else np.nan), peak_corr


def build_trial_features(trial: pd.DataFrame) -> dict:
    trial = trial.sort_values("time_ms")
    t_s = (trial["time_ms"] / 1000).to_numpy()

    total = trial["Total_N"].to_numpy()
    resid_total, drift_slope = detrend(t_s, total)

    back = (trial["Back_L_N"] + trial["Back_R_N"]).to_numpy()
    middle = (trial["Middle_L_N"] + trial["Middle_R_N"]).to_numpy()
    front = (trial["Front_L_N"] + trial["Front_R_N"]).to_numpy()

    resid_back, _ = detrend(t_s, back)
    resid_middle, _ = detrend(t_s, middle)
    resid_front, _ = detrend(t_s, front)

    # Fast-fluctuation lag search (kept for completeness, but see docstring:
    # verified against ~0 reliable detections across all 480 trials -- there
    # is no fast delayed-copy relationship in the detrended residuals here).
    lag_fm, corr_fm = lag_of_peak_correlation(resid_front, resid_middle)
    lag_mb, corr_mb = lag_of_peak_correlation(resid_middle, resid_back)
    lag_fb, corr_fb = lag_of_peak_correlation(resid_front, resid_back)

    # Slow-trend coupling: plain whole-trial correlation between RAW (not
    # detrended) row signals. This is the feature that actually turned out to
    # carry signal -- verified across all 480 trials to be strongly negative
    # (front and back redistribute force in anti-phase as the packing
    # settles) and to get both stronger and less variable with density and
    # with obstacle presence. See build_features.py revision notes.
    front_back_redistribution = np.corrcoef(front, back)[0, 1]
    front_middle_redistribution = np.corrcoef(front, middle)[0, 1]
    middle_back_redistribution = np.corrcoef(middle, back)[0, 1]

    frame_diffs = np.diff(total)

    return {
        "baseline_total_N": trial.loc[trial["time_ms"] < 1000, "Total_N"].mean(),
        "mean_total_N": total.mean(),
        "drift_slope_N_per_s": drift_slope,
        "fluctuation_std_N": resid_total.std(),
        "frame_to_frame_rms_N": np.sqrt(np.mean(frame_diffs**2)),
        "peak_total_N": total.max(),
        "asymmetry_back": (trial["Back_L_N"].mean() - trial["Back_R_N"].mean())
        / (trial["Back_L_N"].mean() + trial["Back_R_N"].mean()),
        "asymmetry_middle": (trial["Middle_L_N"].mean() - trial["Middle_R_N"].mean())
        / (trial["Middle_L_N"].mean() + trial["Middle_R_N"].mean()),
        "asymmetry_front": (trial["Front_L_N"].mean() - trial["Front_R_N"].mean())
        / (trial["Front_L_N"].mean() + trial["Front_R_N"].mean()),
        "front_back_gradient_N": front.mean() - back.mean(),
        "lag_front_to_middle_ms": lag_fm,
        "corr_front_middle_residual": corr_fm,
        "lag_middle_to_back_ms": lag_mb,
        "corr_middle_back_residual": corr_mb,
        "lag_front_to_back_ms": lag_fb,
        "corr_front_back_residual": corr_fb,
        "front_back_redistribution": front_back_redistribution,
        "front_middle_redistribution": front_middle_redistribution,
        "middle_back_redistribution": middle_back_redistribution,
    }


def main():
    df = pd.read_parquet(DATA_PATH)
    meta_cols = [
        "version_num", "trial", "version", "total_balls", "ratio_10mm_13mm",
        "n_10mm", "n_13mm", "packing_fraction", "phi_after_compression",
        "single_layer", "ball_mass_kg", "expected_total_N", "obstacle_shape",
        "obstacle_size_cm", "obstacle_angle_deg", "obstacle_position",
    ]

    rows = []
    for (v, t), trial in df.groupby(["version_num", "trial"]):
        feats = build_trial_features(trial)
        feats["version_num"] = v
        feats["trial"] = t
        for col in meta_cols:
            if col not in feats:
                feats[col] = trial[col].iloc[0]
        rows.append(feats)

    features_df = pd.DataFrame(rows)
    features_df.to_csv(OUT_PATH, index=False)

    print(f"Built feature table: {features_df.shape[0]} trials x {features_df.shape[1]} columns")
    print(f"Saved to {OUT_PATH}\n")
    print("Preview:")
    print(features_df[[
        "version_num", "trial", "packing_fraction", "obstacle_shape",
        "mean_total_N", "drift_slope_N_per_s", "fluctuation_std_N",
        "front_back_redistribution",
    ]].head(8).to_string(index=False))

    print("\nSanity check - fluctuation_std_N should be small relative to mean_total_N:")
    ratio = (features_df["fluctuation_std_N"] / features_df["mean_total_N"]).describe()
    print(ratio)


if __name__ == "__main__":
    main()
