"""
Figure for the standout Phase 4c result: obstacle angle (and its interaction
with obstacle shape) dominates the ANOVA for redistribution_strength
(32% + 15% of variance respectively, p<0.0001), far more than size or
position. This plots that effect directly.

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/plot_obstacle_angle_effect.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = REPO_ROOT / "analysis" / "data" / "processed" / "trial_features.csv"
FIG_DIR = REPO_ROOT / "analysis" / "figures"

SHAPE_COLORS = {"straight": "#2b6cb0", "s": "#c0392b"}


def main():
    f = pd.read_csv(DATA_PATH)
    obs = f[f["obstacle_shape"] != "none"].copy()
    obs["redistribution_strength"] = obs["front_back_redistribution"].abs()

    angles = sorted(obs["obstacle_angle_deg"].unique())
    shapes = sorted(obs["obstacle_shape"].unique())

    fig, ax = plt.subplots(figsize=(7.5, 5))
    width = 0.35
    positions = range(len(angles))

    for i, shape in enumerate(shapes):
        data = [
            obs.loc[(obs.obstacle_angle_deg == a) & (obs.obstacle_shape == shape),
                    "redistribution_strength"]
            for a in angles
        ]
        offset = (i - 0.5) * width
        bp = ax.boxplot(
            data, positions=[p + offset for p in positions], widths=width * 0.9,
            patch_artist=True,
        )
        for patch in bp["boxes"]:
            patch.set_facecolor(SHAPE_COLORS[shape])
            patch.set_alpha(0.75)
        ax.plot([], [], color=SHAPE_COLORS[shape], linewidth=8, alpha=0.75, label=f"{shape} obstacle")

    ax.set_xticks(list(positions))
    ax.set_xticklabels([f"{a}°" for a in angles])
    ax.set_xlabel("obstacle angle")
    ax.set_ylabel("redistribution strength  |corr(front, back)|")
    ax.set_title("Obstacle angle is the dominant factor controlling\n"
                  "front-back load redistribution (ANOVA: 32% + 15% of variance, p<0.0001)")
    ax.legend(frameon=False, fontsize=9)
    fig.tight_layout()
    out = FIG_DIR / "09_obstacle_angle_effect.png"
    fig.savefig(out, dpi=150)
    print(f"Saved {out}")


if __name__ == "__main__":
    main()
