"""
Generates a formal .docx report summarizing the entire analysis: what data
was used, what was done at each step, and the resulting output metrics --
including the honest corrections/reconciliations made along the way.

Run from the repo root:
    source .venv/bin/activate
    python analysis/scripts/generate_report_docx.py
"""

from pathlib import Path

import pandas as pd
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

REPO_ROOT = Path(__file__).resolve().parents[2]
FIG_DIR = REPO_ROOT / "analysis" / "figures"
RESULTS_DIR = REPO_ROOT / "analysis" / "results"
OUT_PATH = REPO_ROOT / "Crowd_Pressure_Waves_Analysis_Report.docx"

HEADING_COLOR = RGBColor(0x1F, 0x3A, 0x5F)


def add_title_page(doc: Document):
    title = doc.add_heading("Crowd Pressure Waves and Real-Time Measurement of", level=0)
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_heading("Stampede Dynamics Using a Low-Cost Sensing System", level=0)
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p = doc.add_paragraph("Data Analysis Report")
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.runs[0].font.size = Pt(18)
    p.runs[0].font.bold = True
    p2 = doc.add_paragraph("Project 2 (Omotec) — Krishiv Kedia")
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p2.runs[0].font.size = Pt(13)
    doc.add_page_break()


def add_df_table(doc: Document, df: pd.DataFrame, col_widths=None):
    table = doc.add_table(rows=1, cols=len(df.columns))
    table.style = "Light Grid Accent 1"
    hdr = table.rows[0].cells
    for i, col in enumerate(df.columns):
        hdr[i].text = str(col)
        for p in hdr[i].paragraphs:
            for r in p.runs:
                r.font.bold = True
    for _, row in df.iterrows():
        cells = table.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = f"{val:.4g}" if isinstance(val, float) else str(val)
    return table


def add_figure(doc: Document, filename: str, caption: str, width_in: float = 6.0):
    doc.add_picture(str(FIG_DIR / filename), width=Inches(width_in))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph(caption)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].font.italic = True
    cap.runs[0].font.size = Pt(9)


def main():
    doc = Document()
    for style_name in ["Normal"]:
        doc.styles[style_name].font.size = Pt(11)

    add_title_page(doc)

    # ---------------------------------------------------------------
    doc.add_heading("1. Project Overview", level=1)
    doc.add_paragraph(
        "This project uses a physical analogue — hundreds of packed plastic balls "
        "(10 mm and 13 mm sizes) standing in for a densely packed crowd — to safely "
        "study how force builds up and redistributes in dense crowds, and what role "
        "obstacles play in triggering dangerous conditions. A 6-sensor force rig "
        "(Back/Middle/Front rows, Left/Right) measures force at 8 Hz under the packed "
        "balls, for 48 different experimental configurations, each repeated 10 times."
    )
    doc.add_paragraph("Research objectives (from the original proposal):")
    for obj in [
        "Understand how crowd density affects the build-up of pressure between people.",
        "Develop a mathematical model explaining how pressure waves form and move through a crowd.",
        "Build a low-cost sensor device to measure pressure changes and detect wave-like behaviour.",
        "Test the model using experiments and compare results with real sensor data.",
        "Identify the conditions under which crowd pressure becomes dangerous and can lead to stampedes.",
    ]:
        doc.add_paragraph(obj, style="List Number")

    # ---------------------------------------------------------------
    doc.add_heading("2. Data Used", level=1)
    doc.add_paragraph(
        "All data lives in data_logging_final/: an INDEX.csv design table describing "
        "48 experimental setups ('versions', V1-V48), and 480 trial recordings "
        "(v{version}t{trial}.csv, 10 trials per version)."
    )
    summary_rows = pd.DataFrame({
        "Property": [
            "Total trials", "Sensors per trial", "Sampling rate", "Trial duration",
            "Samples per trial", "No-obstacle versions", "Obstacle versions",
            "Obstacle design",
        ],
        "Value": [
            "480 (48 versions x 10 trials)", "6 (Back/Middle/Front, each Left/Right) + Total",
            "8 Hz (125 ms)", "30 seconds", "240",
            "V1-V12: sweep total_balls (300-600) x ball-size ratio (equal/1:3/3:1)",
            "V13-V48: fixed density, full factorial obstacle_shape(2) x size(3) x angle(3) x position(2)",
            "36 configurations x 10 trials = 360 trials",
        ],
    })
    add_df_table(doc, summary_rows)

    # ---------------------------------------------------------------
    doc.add_heading("3. Methodology — Steps Performed", level=1)
    steps = [
        ("Step 0 — Environment setup", "Python virtual environment; pandas, numpy, scipy, "
         "matplotlib, seaborn, pyarrow, statsmodels."),
        ("Step 1 — Load & validate", "Merged all 480 trial files with INDEX.csv metadata. "
         "Verified Total_N exactly equals the sum of the 6 sensors (0.0000 N max deviation), "
         "and that resting force matches theoretical expected weight almost perfectly "
         "(measured = 0.999 x expected, R^2 = 0.9998)."),
        ("Step 2 — Investigate an unexpected universal drift", "Every one of the 480 trials "
         "showed a consistent downward drift in total force. Tested and ruled out: random "
         "noise (100% of trials negative, not chance), simple settling-to-equilibrium "
         "(drift ACCELERATES rather than flattens, confirmed via early-vs-late slope "
         "paired t-test and via degenerate exponential-fit tau values), and a session/"
         "instrument warm-up artifact (no correlation with within-version trial order, "
         "p=0.56). Best-supported explanation: continued physical rearrangement of the "
         "packing, stronger in denser/obstacle-disturbed setups."),
        ("Step 3 — Feature engineering", "Converted each 240-sample trial into ~30 summary "
         "features (baseline force, drift rate, detrended fluctuation, L-R asymmetry, "
         "front-back gradient). An initial 'wave lag' cross-correlation method (searching "
         "for a delayed-copy relationship between sensor rows) was rigorously tested and "
         "found to never reliably detect anything, even in obstacle trials. This was "
         "replaced with a 'redistribution strength' feature (plain correlation between raw "
         "row signals), which detected a strong, real anti-phase relationship: force shifts "
         "from one row to another as the packing settles, rather than a pulse arriving late."),
        ("Step 4 — Density -> pressure relationship (V1-V12)", "Tested whether density alone "
         "(without an obstacle) destabilizes the packing. See Results section 4.4 for the "
         "full, reconciled account of this step, which included an initial exploratory pass "
         "and a more rigorous per-trial statistical follow-up."),
        ("Step 5 — Obstacle factor analysis (V13-V48)", "Factorial ANOVA across obstacle "
         "shape/size/angle/position on three candidate 'danger' outcomes."),
        ("Step 6 — Model validation", "Power spectral density check for a literal "
         "oscillating wave; exponential relaxation model fit per sensor row."),
        ("Step 7 — Statistical rigor pass", "Bootstrap confidence intervals on headline "
         "claims; Tukey HSD (multiple-comparison corrected) post-hoc tests on obstacle "
         "angle and on all 36 individual versions."),
    ]
    for name, desc in steps:
        h = doc.add_paragraph()
        h.add_run(name).bold = True
        doc.add_paragraph(desc)

    # ---------------------------------------------------------------
    doc.add_heading("4. Results", level=1)

    doc.add_heading("4.1 Data Quality & Calibration", level=2)
    doc.add_paragraph(
        "The sensor rig is well calibrated and trustworthy: across all 480 trials, "
        "measured resting force = 0.9991 x expected theoretical weight + 0.02 N "
        "(R^2 = 0.99976, mean error -0.034% +/- 0.252%)."
    )
    add_figure(doc, "02_baseline_calibration.png", "Figure 1. Measured vs. expected static weight, all 480 trials.")

    doc.add_heading("4.2 The Universal Drift Finding", level=2)
    doc.add_paragraph(
        "100% of all 480 trials show a negative drift in total force (mean "
        "~-0.029 N/s). Early-window vs. late-window slope comparison (paired t-test, "
        "n=480) showed the drift significantly ACCELERATES rather than flattens "
        "(t=19.30, p=7.8e-62) -- ruling out simple settling-to-equilibrium. Drift "
        "magnitude correlates weakly with version number (r=-0.168, R^2=0.028) but "
        "not at all with within-version trial order (r=-0.027, p=0.56), pointing to a "
        "physical rather than session-timing cause."
    )
    add_figure(doc, "03_trial_repeatability.png", "Figure 2. Ten repeated trials of one setup, overlaid.")
    add_figure(doc, "05_early_vs_late_slope.png", "Figure 3. Early vs. late drift rate across all 480 trials.")

    doc.add_heading("4.3 Feature Engineering & the Redistribution Discovery", level=2)
    doc.add_paragraph(
        "The originally planned 'wave lag' detection method was invalidated (peak "
        "cross-correlation stayed ~0.11-0.16 everywhere, below any reliable threshold, "
        "even in obstacle trials). In its place, a 'redistribution strength' feature "
        "(plain whole-trial correlation between raw sensor rows) revealed a strong, "
        "validated effect: obstacle trials show much stronger and more consistent "
        "front-back anti-correlation (mean r=-0.81, std 0.11) than no-obstacle trials "
        "(mean r=-0.40, std 0.31). Using all three rows, Middle's own dynamics are "
        "essentially unaffected by obstacle position (middle vs. middle_back), while "
        "Front and Back shift oppositely -- Front consistently gains force, Middle and "
        "Back (which move together, r~+0.47) consistently lose it, in every obstacle "
        "trial and, more weakly, even at baseline."
    )
    add_figure(doc, "07_front_back_redistribution.png",
               "Figure 4. Left: obstacle vs. no-obstacle redistribution strength. Right: vs. density.")

    doc.add_heading("4.4 Density -> Pressure Relationship (V1-V12)", level=2)
    doc.add_paragraph(
        "An initial exploratory pass (version-level averages, n=12 points) fit both a "
        "linear and a threshold/'hinge' model to mean force and fluctuation vs. packing "
        "fraction, finding high R^2 for both (e.g. fluctuation_std_N: linear R^2=0.948, "
        "hinge R^2=0.949, threshold at phi=0.61) — but a threshold model barely improved "
        "on a straight line, and fitting only 12 averaged points is vulnerable to "
        "overstating how strong a relationship really is. The same pass found the ball-"
        "size ratio (10mm:13mm mix) has a very large, significant effect on force and "
        "fluctuation at matched ball counts (e.g. F-statistics in the hundreds, "
        "p < 1e-13) — though part of this may reflect that different ratios pack to "
        "different densities and different total masses, rather than composition alone; "
        "this comparison was not normalized for that."
    )
    doc.add_paragraph(
        "A more rigorous follow-up tested the same question at the individual-trial "
        "level (n=480, not 12 averages), normalizing fluctuation by mean force "
        "(coefficient of variation) to remove the trivial effect of larger absolute "
        "force producing larger absolute noise. This found NO robust relationship: "
        "correlation(packing_fraction, fluctuation CV) = 0.154, with a bootstrap 95% CI "
        "of [-0.040, +0.332] — crossing zero. Likewise, measured-vs-expected weight "
        "deviation showed no density trend (r=-0.067, p=0.466)."
    )
    doc.add_paragraph(
        "CONCLUSION (the trial-level, bootstrap-validated result supersedes the "
        "exploratory version-level fit): density alone, without a disturbance, does "
        "not measurably destabilize this packing across the tested range "
        "(packing fraction 0.345-0.894). Danger requires density combined with a "
        "disturbance, not density alone."
    )
    add_figure(doc, "08_density_pressure_relationship.png",
               "Figure 5. Calibration deviation and fluctuation CV vs. packing fraction (no obstacle).")

    doc.add_heading("4.5 Obstacle Factor Analysis (V13-V48)", level=2)
    doc.add_paragraph(
        "A factorial ANOVA (obstacle shape x size x angle x position, plus all 2-way "
        "interactions) was run on three candidate danger metrics. Redistribution "
        "strength was by far the best explained (71% of variance, 29% residual):"
    )
    anova_r = pd.read_csv(RESULTS_DIR / "anova_redistribution_strength.csv").rename(
        columns={"Unnamed: 0": "Term"}
    ).head(6)
    add_df_table(doc, anova_r[["Term", "sum_sq", "F", "PR(>F)", "pct_variance_explained"]])
    doc.add_paragraph(
        "By contrast, raw fluctuation magnitude (93.6% residual) and peak-force spike "
        "(92.7% residual) were mostly unexplained noise — obstacle geometry does not "
        "meaningfully predict those two, only the redistribution pattern."
    )
    add_figure(doc, "09_obstacle_angle_effect.png",
               "Figure 6. Redistribution strength by obstacle angle and shape.")
    doc.add_paragraph(
        "Tukey HSD (multiple-comparison corrected) confirmed all three angles differ "
        "significantly from each other, refining the danger ordering to "
        "45 deg > 75 deg > 60 deg (a non-monotonic 'sweet spot' at 60 deg, not simply "
        "'higher angle = safer'). IMPORTANT CORRECTION: a Tukey HSD across all 36 "
        "individual versions found only 264/630 (42%) pairwise comparisons remain "
        "significant after correction, and the single top-ranked 'most dangerous' "
        "version (V16) is only significantly different from 14/35 (40%) of the "
        "others. The angle/shape-interaction factor effect is the robust, reportable "
        "finding — an individual version-level danger ranking is not statistically "
        "well-supported at only 10 trials per version."
    )

    doc.add_heading("4.6 Model Validation", level=2)
    doc.add_paragraph(
        "Two theoretical framings were tested against the data. (1) A literal "
        "oscillating/traveling wave: power spectral density analysis found no "
        "consistent peak frequency (checked across 30 random trials, peak location "
        "scattered randomly, std=1.3 Hz across a 0-4 Hz range) — confirming, via an "
        "independent standard method, that there is no periodic wave in this data. "
        "(2) Exponential relaxation toward equilibrium: fits degenerated to unphysical "
        "time constants (hundreds of thousands of seconds), meaning the redistribution "
        "process is still actively developing throughout the full 30-second window and "
        "never reaches equilibrium in that time — consistent with the accelerating (not "
        "flattening) drift found in section 4.2."
    )
    add_figure(doc, "10_power_spectrum.png", "Figure 7. Power spectrum of detrended Total_N (no dominant peak).")

    # ---------------------------------------------------------------
    doc.add_heading("5. Summary of Key Output Metrics", level=1)
    metrics = pd.DataFrame({
        "Metric": [
            "Sensor calibration (measured vs. expected)",
            "Universal drift (all 480 trials)",
            "Redistribution strength, obstacle vs. no-obstacle",
            "Density vs. fluctuation CV (no-obstacle, per-trial)",
            "Obstacle angle effect on redistribution strength",
            "Obstacle angle danger ordering (Tukey HSD)",
            "Individual version ranking robustness",
            "Literal oscillating wave",
        ],
        "Result": [
            "R^2 = 0.9998, slope 0.999",
            "100% negative, accelerating (p=7.8e-62)",
            "-0.81 (std 0.11) vs. -0.40 (std 0.31); 95% CI [+0.345, +0.453]",
            "r=0.154, 95% CI [-0.040, +0.332] -- not significant",
            "32% of ANOVA variance, p<0.0001",
            "45 deg > 75 deg > 60 deg (all pairs significant)",
            "Only 42% of 630 pairwise version comparisons significant",
            "Not detected (peak frequency scatters randomly, std=1.3 Hz)",
        ],
    })
    add_df_table(doc, metrics)

    # ---------------------------------------------------------------
    doc.add_heading("6. Limitations & Open Items", level=1)
    for item in [
        "The universal front-loading tendency (Front gains, Middle+Back lose) persists "
        "even in no-obstacle baseline trials and is NOT explained by tray tilt (confirmed "
        "level) -- the underlying cause remains open.",
        "Obstacle-to-sensor orientation (exact physical placement for 'middle' vs. "
        "'middle_back') is only partially inferred from data patterns; true confirmation "
        "requires a physical measurement or direct confirmation from the experimenter.",
        "The ratio_10mm_13mm effect on fluctuation at matched ball count was not "
        "normalized for total force magnitude (CV) -- part of the effect may be a "
        "trivial mass-scaling artifact rather than a genuine composition effect.",
        "Individual obstacle-version danger rankings should not be over-interpreted; "
        "only the factor-level (angle, shape x angle) effects are statistically robust.",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.add_heading("7. Remaining Work", level=1)
    for item in [
        "Write the paper-facing narrative mapping results to the proposal's 5 objectives.",
        "Curate a final, polished figure set for the paper/poster.",
        "Commit accumulated analysis code, figures, and results to git.",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    # ---------------------------------------------------------------
    doc.add_page_break()
    doc.add_heading("Appendix A: Glossary of Terms & Abbreviations", level=1)
    doc.add_paragraph(
        "Every statistical/technical term used in this report, in full, with what it "
        "measures and why it was used here."
    )
    glossary = [
        ("N (Newton)", "The physics unit of force. All sensor readings in this project "
         "are in Newtons — how hard the balls press down on a sensor."),
        ("Hz (Hertz)", "Unit of frequency: cycles (or, for sampling, measurements) per "
         "second. Our sensors record at 8 Hz = 8 readings every second."),
        ("Packing fraction (phi)", "The fraction of a container's volume actually filled "
         "with material (here, balls) rather than empty gaps. Our main measure of "
         "'how crowded/dense' a setup is."),
        ("Mean / Average", "Sum of all values divided by how many there are."),
        ("Standard deviation (std)", "How spread out a set of numbers is around its "
         "average. A small std means the numbers are consistent; a large std means "
         "they vary a lot."),
        ("Coefficient of Variation (CV)", "Standard deviation divided by the mean. Lets "
         "you compare 'how noisy' two signals are even when their average sizes are very "
         "different — used so that a naturally larger force reading doesn't automatically "
         "look 'more unstable' just because its absolute wobble is bigger."),
        ("Correlation coefficient (r)", "A number from -1 to +1 describing how two "
         "quantities move together. +1 = always move together; -1 = always move "
         "oppositely (called anti-correlation); 0 = no relationship. Central to this "
         "report's 'redistribution strength' feature, which is exactly this correlation "
         "computed between sensor rows."),
        ("R-squared (R^2)", "Coefficient of determination. A number from 0 to 1 showing "
         "how well a mathematical model or line fits real data: 1 = the model explains "
         "all the variation in the data, 0 = it explains none. Used to judge how good our "
         "calibration fit and curve fits were."),
        ("RMSE (Root Mean Square Error)", "A measure of the typical size of a model's "
         "prediction errors, in the same units as the data (Newtons, here). Smaller = "
         "better fit. Reported alongside R^2 for the density-pressure curve fits."),
        ("p-value", "In a statistical test, the probability of seeing a result at least "
         "this extreme purely by random chance, if there were actually no real effect. "
         "Conventionally, p < 0.05 is called 'statistically significant' -- unlikely to be "
         "chance. Used throughout this report to judge whether a pattern is real."),
        ("95% Confidence Interval (CI)", "A range calculated so that, if the experiment "
         "were repeated many times, the true value would fall inside that range about 95% "
         "of the time. If a 95% CI crosses zero, we cannot confidently claim the effect is "
         "positive OR negative -- it might genuinely be nothing."),
        ("Bootstrap / bootstrapping", "A way of estimating how uncertain a statistic is "
         "(like a mean or a correlation) WITHOUT assuming a specific mathematical formula "
         "for it: randomly resample the data you already have, with replacement, thousands "
         "of times (we used 5000), recompute the statistic each time, and look at how much "
         "it varies. Used here to build the 95% confidence intervals."),
        ("t-test / t-statistic", "A statistical test that compares the averages of two "
         "groups and produces a 't' value; a larger |t| (further from 0) means a bigger, "
         "more reliable difference between the groups. Always reported with a p-value."),
        ("ANOVA (Analysis of Variance)", "A statistical method that takes several possible "
         "'suspects' (here: obstacle shape, size, angle, position) and tells you how much "
         "each one actually explains about an outcome, with a confidence level for each. "
         "Used to find which obstacle property matters most."),
        ("F-statistic", "The test statistic ANOVA produces for each factor: how much "
         "variation that factor explains relative to random leftover noise. Larger F = "
         "stronger evidence that factor genuinely matters."),
        ("df (degrees of freedom)", "Roughly, how many independent pieces of information "
         "went into a calculation (e.g. a factor with 3 levels has 2 degrees of freedom). "
         "Needed alongside the F-statistic to determine its p-value, but not something you "
         "need to interpret directly."),
        ("Sum of squares (sum_sq)", "In an ANOVA table, a measure of how much total "
         "variability in the outcome is attributable to one particular factor. Dividing a "
         "factor's sum_sq by the total gives '% variance explained' -- the single most "
         "useful number in our obstacle analysis for ranking which factor matters most."),
        ("PR(>F)", "The p-value associated with an ANOVA factor's F-statistic (the column "
         "header statsmodels, our statistics software, uses by default)."),
        ("Tukey HSD (Honestly Significant Difference)", "A follow-up test run after ANOVA "
         "that compares every pair of groups individually while correcting for the fact "
         "that testing many pairs at once increases the chance of a false alarm (this "
         "correction is called a 'multiple comparison correction'). Used to confirm which "
         "specific obstacle angles differ from each other, and to properly (and more "
         "cautiously) test the 36 individual obstacle configurations against each other."),
        ("Power Spectral Density (PSD)", "A technique that breaks a signal down by "
         "frequency, showing how much of its variation happens at each oscillation speed. "
         "A real repeating wave shows up as a sharp peak; plain noise shows up as a flat, "
         "jagged spread across all frequencies with no consistent peak. Used to formally "
         "test for a literal traveling/oscillating pressure wave."),
        ("Detrending", "Mathematically subtracting a straight-line trend from a signal so "
         "that smaller fluctuations underneath become easier to see and measure, without "
         "the steady drift swamping them."),
        ("Exponential relaxation model / tau", "A mathematical curve shape (F_inf + "
         "(F0-F_inf)*e^(-t/tau)) representing something approaching a stable resting value "
         "over time, fast at first and flattening out later. 'Tau' is the time constant: "
         "roughly, how many seconds it takes to get most of the way to that resting value. "
         "A very large fitted tau (as found here) signals the process has NOT started "
         "flattening out within the time we recorded."),
        ("Linear regression / slope / intercept", "Fitting the simplest possible straight "
         "line (y = slope*x + intercept) through data points -- the most basic model "
         "against which more complex models (like the hinge/threshold model) are judged."),
        ("Hinge / threshold / piecewise model", "A model allowing a relationship to change "
         "slope at some critical point (here, a critical packing fraction), rather than "
         "staying a single straight line the whole way -- the mathematical form of the "
         "proposal's 'pressure rises rapidly beyond a critical density' hypothesis."),
    ]
    table = doc.add_table(rows=1, cols=2)
    table.style = "Light Grid Accent 1"
    table.rows[0].cells[0].text = "Term"
    table.rows[0].cells[1].text = "Full meaning & relevance to this analysis"
    for term, meaning in glossary:
        row = table.add_row().cells
        row[0].text = term
        row[0].paragraphs[0].runs[0].font.bold = True
        row[1].text = meaning

    doc.save(OUT_PATH)
    print(f"Saved report to {OUT_PATH}")


if __name__ == "__main__":
    main()
