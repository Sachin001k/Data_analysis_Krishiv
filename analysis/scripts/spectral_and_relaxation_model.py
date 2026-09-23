"""
Phase 4d, part 1: formal model validation of the theoretical framing.

The proposal frames pressure dynamics as either (a) a traveling/oscillating
wave, or (b) a nonlinear density-pressure continuum model. We can't test a
full spatial PDE with only 3 sensor rows and no density field, but we CAN
formally test the two simplified hypotheses this data supports:

  1. Is there a dominant oscillation frequency in the signal (a "wave" in the
     literal periodic sense)? -> power spectral density (PSD). A real
     traveling/oscillating wave should show a peak at some characteristic
     frequency above the noise floor. This is a more rigorous, standard-method
     complement to the earlier cross-correlation null result (which only
     found no LAGGED-COPY relationship; this checks for periodicity
     directly, independently).

  2. Is each row's dynamics well described by simple exponential relaxation
     toward a new equilibrium (F(t) = F_inf + (F0-F_inf)*exp(-t/tau))? This
     is the appropriate "simplified redistribution" model given everything
     found so far (monotonic, not oscillatory, front gains while middle+back
     lose). Report tau (how fast) and R^2 (how well) per row, split by
     obstacle presence.

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/spectral_and_relaxation_model.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import curve_fit
from scipy.signal import welch

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "clean_trials.parquet"
FIG_DIR = REPO_ROOT / "analysis" / "figures"
RESULTS_DIR = REPO_ROOT / "analysis" / "results"
FS_HZ = 8.0


def part1_spectral_check(df: pd.DataFrame):
    print("=== Part 1: is there a dominant oscillation frequency (a literal wave)? ===")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, (v, t, label) in zip(
        axes, [(1, 1, "V1t1 - no obstacle"), (22, 1, "V22t1 - obstacle")]
    ):
        trial = df[(df.version_num == v) & (df.trial == t)].sort_values("time_ms")
        total = trial["Total_N"].to_numpy()
        detrended = total - np.polyval(np.polyfit(np.arange(len(total)), total, 1), np.arange(len(total)))
        freqs, psd = welch(detrended, fs=FS_HZ, nperseg=min(128, len(detrended)))
        ax.semilogy(freqs, psd, color="#2b6cb0")
        ax.set_xlabel("frequency (Hz)")
        ax.set_ylabel("power spectral density")
        ax.set_title(label)
        peak_freq = freqs[np.argmax(psd[1:]) + 1]  # skip DC bin
        print(f"{label}: peak (non-DC) frequency = {peak_freq:.3f} Hz, "
              f"peak/median power ratio = {psd[1:].max() / np.median(psd[1:]):.2f}")
    fig.suptitle("Power spectrum of detrended Total_N: a real wave would show a clear peak.\n"
                 "A flat/broadband spectrum means no dominant oscillation -- just noise.")
    fig.tight_layout(rect=[0, 0, 1, 0.88])
    out = FIG_DIR / "10_power_spectrum.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}\n")


def exp_model(t, f_inf, f0, tau):
    return f_inf + (f0 - f_inf) * np.exp(-t / tau)


def part2_relaxation_fits(df: pd.DataFrame):
    print("=== Part 2: does exponential relaxation describe each row's dynamics? ===")
    rows_map = {
        "Front": ["Front_L_N", "Front_R_N"],
        "Middle": ["Middle_L_N", "Middle_R_N"],
        "Back": ["Back_L_N", "Back_R_N"],
    }
    results = []
    for (v, t), trial in df.groupby(["version_num", "trial"]):
        trial = trial.sort_values("time_ms")
        t_s = (trial["time_ms"] / 1000).to_numpy()
        has_obstacle = trial["obstacle_shape"].iloc[0] != "none"
        for row_name, cols in rows_map.items():
            f_vals = (trial[cols[0]] + trial[cols[1]]).to_numpy()
            try:
                popt, _ = curve_fit(
                    exp_model, t_s, f_vals,
                    p0=[f_vals[-1], f_vals[0], 5.0], maxfev=5000,
                )
                pred = exp_model(t_s, *popt)
                r2 = 1 - np.sum((f_vals - pred) ** 2) / np.sum((f_vals - f_vals.mean()) ** 2)
                tau = popt[2]
            except RuntimeError:
                r2, tau = np.nan, np.nan
            results.append({
                "version_num": v, "trial": t, "row": row_name,
                "has_obstacle": has_obstacle, "tau_s": tau, "r2": r2,
            })

    res_df = pd.DataFrame(results)
    res_df.to_csv(RESULTS_DIR / "relaxation_model_fits.csv", index=False)

    summary = res_df.groupby(["row", "has_obstacle"])[["tau_s", "r2"]].agg(["mean", "median", "std"])
    print(summary.round(3).to_string())
    print(f"\nSaved per-trial fits to {RESULTS_DIR / 'relaxation_model_fits.csv'}")

    frac_good_fit = (res_df["r2"] > 0.7).mean() * 100
    print(f"\n% of (row, trial) fits with R^2 > 0.7: {frac_good_fit:.1f}%")


def main():
    df = pd.read_parquet(DATA_PATH)
    part1_spectral_check(df)
    part2_relaxation_fits(df)


if __name__ == "__main__":
    main()
