"""
Load every trial CSV in data_logging_final/, merge with INDEX.csv metadata,
run basic validation checks, and cache the result as a parquet file.

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/load_data.py
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "data_logging_final"
OUT_DIR = REPO_ROOT / "analysis" / "data" / "processed"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SENSOR_COLS = [
    "Back_L_N", "Back_R_N",
    "Middle_L_N", "Middle_R_N",
    "Front_L_N", "Front_R_N",
]

FNAME_RE = re.compile(r"^v(\d+)t(\d+)\.csv$")


def load_index() -> pd.DataFrame:
    index_df = pd.read_csv(RAW_DIR / "INDEX.csv")
    index_df["version_num"] = index_df["version"].str.replace("V", "", regex=False).astype(int)
    return index_df


def load_all_trials(index_df: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for csv_path in sorted(RAW_DIR.glob("v*t*.csv")):
        m = FNAME_RE.match(csv_path.name)
        if not m:
            continue
        version_num, trial_num = int(m.group(1)), int(m.group(2))

        df = pd.read_csv(csv_path)
        df["version_num"] = version_num
        df["trial"] = trial_num

        # Validation check #1: does Total_N match the sum of the 6 sensors?
        row_sum = df[SENSOR_COLS].sum(axis=1)
        df["total_check_diff"] = (df["Total_N"] - row_sum).abs()

        frames.append(df)

    trials_df = pd.concat(frames, ignore_index=True)
    merged = trials_df.merge(index_df, on="version_num", how="left")
    return merged


def add_baseline_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Flag trials whose resting (t < 1s) force is far from expected_total_N."""
    baseline = (
        df[df["time_ms"] < 1000]
        .groupby(["version_num", "trial"])["Total_N"]
        .mean()
        .rename("baseline_total_N")
        .reset_index()
    )
    df = df.merge(baseline, on=["version_num", "trial"], how="left")
    df["baseline_vs_expected_pct"] = (
        (df["baseline_total_N"] - df["expected_total_N"]) / df["expected_total_N"] * 100
    )
    return df


def main():
    index_df = load_index()
    df = load_all_trials(index_df)
    df = add_baseline_flags(df)

    n_trials = df.groupby(["version_num", "trial"]).ngroups
    max_sum_diff = df["total_check_diff"].max()
    print(f"Loaded {n_trials} trials, {len(df)} rows total.")
    print(f"Max |Total_N - sum(sensors)| across all rows: {max_sum_diff:.4f} N")

    baseline_check = (
        df.groupby(["version_num", "trial"])["baseline_vs_expected_pct"].first()
    )
    worst = baseline_check.abs().sort_values(ascending=False).head(10)
    print("\nTrials with largest |baseline - expected_total_N| %:")
    print(worst)

    out_path = OUT_DIR / "clean_trials.parquet"
    df.to_parquet(out_path, index=False)
    print(f"\nSaved merged dataset to {out_path} ({out_path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
