"""
Figure for the front-back "redistribution" finding: obstacle presence makes
force redistribution between front and back much stronger and more
consistent than density alone does.

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/plot_redistribution.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "trial_features.csv"
FIG_DIR = REPO_ROOT / "analysis" / "figures"


def main():
    f = pd.read_csv(DATA_PATH)
    f["has_obstacle"] = f["obstacle_shape"] != "none"

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    # Left: obstacle vs no-obstacle box comparison
    groups = [f.loc[~f.has_obstacle, "front_back_redistribution"],
              f.loc[f.has_obstacle, "front_back_redistribution"]]
    bp = axes[0].boxplot(groups, tick_labels=["no obstacle\n(V1-V12)", "obstacle present\n(V13-V48)"],
                          patch_artist=True, widths=0.5)
    for patch, color in zip(bp["boxes"], ["#9aa5b1", "#2b6cb0"]):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    axes[0].axhline(0, color="#c0392b", linestyle="--", linewidth=1, label="no coupling")
    axes[0].set_ylabel("front-back correlation (whole trial)")
    axes[0].set_title("Obstacles create strong, consistent\nfront-back force redistribution")
    axes[0].legend(frameon=False, fontsize=8, loc="lower right")

    # Right: no-obstacle density sweep
    noob = f[~f.has_obstacle].sort_values("packing_fraction")
    axes[1].scatter(noob["packing_fraction"], noob["front_back_redistribution"].abs(),
                     s=22, alpha=0.6, color="#2b6cb0", edgecolor="none")
    axes[1].set_xlabel("packing fraction (density)")
    axes[1].set_ylabel("|front-back correlation|")
    axes[1].set_title("No-obstacle density sweep:\nredistribution strength vs. density")

    fig.tight_layout()
    out = FIG_DIR / "07_front_back_redistribution.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
