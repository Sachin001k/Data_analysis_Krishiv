# Data Analysis Plan — Crowd Pressure Waves (Project 2)

This file is the working plan for analyzing Krishiv's experimental data. Read this
first in any new session before touching the data. It describes the project, the
dataset, and a step-by-step analysis roadmap aimed at two outputs: a research paper
and a competition submission (ISEF-style).

## 1. Project context

Source: `Omotec Project - Krishiv Kedia.pdf`, "Project 2" (pages 2, 4-6).

**Title:** Crowd Pressure Waves and Real-Time Measurement of Stampede Dynamics Using
a Low-Cost Sensing System

**Research question:** How can we model and measure pressure waves in dense crowds
to understand and predict when conditions become dangerous?

**Core idea:** Above a critical density (~5-6 people/m²), a crowd stops behaving as
independent individuals and starts behaving like a compressible medium (fluid /
packed-granular system). Small disturbances no longer stay local — they propagate as
pressure waves and can produce forces large enough to injure people who are simply
standing still. The project uses a **physical analogue**: densely packed plastic
balls of two sizes (10 mm and 13 mm) standing in for people, with disturbances
introduced via obstacles, and force measured with a 6-sensor rig (ESP32 + force
sensors) standing in for the "low-cost sensing system" described in the proposal.

**Research objectives (from the proposal — use these to structure the paper):**
1. Understand how crowd density affects the build-up of pressure between people.
2. Develop a mathematical model explaining how pressure waves form and move through
   a crowd (density/velocity continuum model, nonlinear pressure-density relation
   with a critical threshold).
3. Build a low-cost sensor device to measure pressure changes and detect wave-like
   behaviour. (Already built — this is what generated `data_logging_final/`.)
4. Test the model using experiments and compare results with real sensor data.
5. Identify the conditions under which crowd pressure becomes dangerous and can lead
   to stampedes.

Every analysis step below should trace back to one of these five objectives so the
final write-up can cite exactly which figure/result answers which objective.

## 2. The dataset

Location: `data_logging_final/` (481 files: `INDEX.csv` + 480 trial CSVs).

### 2.1 `INDEX.csv` — experiment design table (one row per configuration "version")

| Column | Meaning |
|---|---|
| `version` | V1–V48, the experimental configuration ID |
| `total_balls` | 300 / 400 / 500 / 600 — proxy for crowd size/density |
| `ratio_10mm_13mm` | `equal`, `1:3`, `3:1` — mix of small/large "people" |
| `n_10mm`, `n_13mm` | ball counts by size |
| `packing_fraction`, `phi_after_compression` | density proxies (φ) — the key independent variable for the density→pressure model |
| `single_layer` | whether balls stayed in one layer or started forming a 2nd layer (`yes` / `NO_partial_2nd_layer`) — a physical regime marker |
| `ball_mass_kg` | total mass, for converting force to expected static load |
| `expected_total_N` | theoretical static weight (sanity-check baseline for `Total_N`) |
| `obstacle_shape` | `none`, `straight`, `s` — disturbance geometry |
| `obstacle_size_cm` | e.g. `7.5x2`, `6.0x2`, `9.0x2` |
| `obstacle_angle_deg` | 45 / 60 / 75 |
| `obstacle_position` | `none`, `middle`, `middle_back` |
| `trials` | number of repeated trials for that version (10 for all versions) |

Structure of the design:
- **V1–V12**: no obstacle. Pure density/composition sweep (4 ball counts × 3 size
  ratios). This block answers **objective 1** (density → pressure) cleanly.
- **V13–V48**: fixed density (600 balls, equal ratio, the densest single-layer-ish
  case) with a full factorial sweep of obstacle shape (2) × size (3) × angle (3) ×
  position (2) = 36 versions. This block answers **objectives 2, 3, 5** (what
  triggers/shapes a pressure wave and when it becomes dangerous).

### 2.2 Trial files `v{V}t{T}.csv`

Each file = one trial (T = 1..10) of version V. Confirmed structure:
- Columns: `time_ms, Back_L_N, Back_R_N, Middle_L_N, Middle_R_N, Front_L_N, Front_R_N, Total_N`
- 241 rows (240 samples + header), `time_ms` = 0..29875 in steps of 125 ms →
  **8 Hz sampling, 30-second trials**, consistent across every file checked.
- 6 force sensors arranged in a 3×2 grid (Back/Middle/Front × Left/Right) under the
  ball mass — this is the spatial layout needed for wave-propagation analysis
  (front → middle → back, or reverse, depending on where the obstacle/disturbance is).
- `Total_N` ≈ sum of the 6 sensors (verify in cleaning step).
- No missing values, no NaNs/nulls found in a full-corpus grep. All 480 expected
  trial files are present (cross-checked against `INDEX.csv` trial counts).

## 3. Environment setup

```
data_logging_final/          # raw data, read-only — never edit in place
analysis/
  data/
    processed/               # cleaned parquet/csv outputs land here
  notebooks/                 # exploratory .ipynb work
  scripts/                   # reusable .py modules (loading, features, plotting)
  figures/                   # exported paper/competition-ready plots
  results/                   # tables, model fit summaries, stats output
requirements.txt
```

Suggested stack: `pandas`, `numpy`, `scipy` (curve_fit, signal.correlate, stats),
`statsmodels` (ANOVA/regression), `matplotlib` + `seaborn` (or the `dataviz` skill
guidance for anything presentation-facing). Keep raw data untouched; every
transformation goes through a script and writes to `analysis/data/processed/`.

## 4. Step-by-step analysis plan

### Phase 0 — Setup
- [ ] Create the `analysis/` folder structure above.
- [ ] Write `requirements.txt`, set up a virtualenv/conda env.
- [ ] Write a loader script (`scripts/load_data.py`) that reads `INDEX.csv`, parses
      `version`/`trial` out of each filename, loads every trial CSV, and returns one
      **long-format DataFrame** with columns `version, trial, time_ms, sensor, force_N`
      plus all INDEX metadata merged in. Cache it as a parquet file so later steps
      don't re-parse 480 CSVs every time.

### Phase 1 — Data cleaning & validation
- [ ] Verify `Total_N` == sum of the 6 sensor columns (row-wise) within a small
      tolerance; flag/investigate any trial where it doesn't hold.
- [ ] Baseline check: compare `Total_N` at rest (e.g. mean of first 1-2 seconds) to
      `expected_total_N` from `INDEX.csv`. Large deviations may indicate a mis-tared
      sensor or wrong ball count for that version — flag those trials.
- [ ] Outlier/spike detection: per-sensor per-trial, flag physically implausible
      jumps (e.g. > N standard deviations frame-to-frame) that suggest sensor glitches
      rather than real force events. Don't just delete — tag them so you can decide
      case by case (a real disturbance spike must not be thrown away).
- [ ] Noise handling: apply a light smoothing filter (rolling mean or
      Savitzky-Golay) as a *separate* smoothed column — keep the raw signal too,
      since wave-detection analysis needs the raw dynamics and only summary plots
      need smoothing.
- [ ] Trial-consistency check: confirm every trial for a version has the same length
      / sample rate; note any that don't for exclusion or resampling.
- [ ] Save the cleaned, merged long-format dataset to
      `analysis/data/processed/clean_trials.parquet`. This is the single source of
      truth for every analysis below.

### Phase 2 — Exploratory data analysis (get familiar before modeling)
- [ ] Plot raw time series of all 6 sensors + Total for a few representative trials:
      one low-density no-obstacle (e.g. V1), one high-density no-obstacle (V10), and
      a couple of obstacle trials (e.g. V13, V22). Look with your own eyes for
      wave-like ripples, spikes at obstacle-introduction, and drift.
  - [ ] Overlay all ~10 trials of the same version to eyeball trial-to-trial
      repeatability before trusting averages.
  - [ ] Distribution plots (histograms/violin) of `Total_N` per version.
  - [ ] A summary table: mean/std/min/max of `Total_N` per version, sorted by
      `packing_fraction`.

### Phase 3 — Feature engineering (per-trial summary features)
Build one row per trial (480 rows) with physics-motivated features, merged with
INDEX metadata — this "trial feature table" is what most statistical analysis and
plotting will run on instead of the raw 8 Hz series.
- [ ] Static/mean features: mean, std, min, max, and coefficient of variation of
      `Total_N` and of each sensor.
- [ ] Fluctuation/"pressure wave energy" features: variance of the detrended signal,
      RMS of frame-to-frame differences, spectral energy (FFT / power spectral
      density) — this operationalizes "pressure waves" as measurable fluctuation
      rather than just static load.
- [ ] Asymmetry features: left-right imbalance per row, e.g.
      `(L - R) / (L + R)` for Back/Middle/Front — useful for obstacle-position and
      obstacle-angle effects since those break L/R symmetry.
- [ ] Front-back gradient: `Front_N - Back_N` (or vice versa) as a proxy for
      directional force propagation.
- [ ] Wave propagation features: cross-correlate the Front/Middle/Back row signals
      pairwise (`scipy.signal.correlate`) to find the time lag of peak correlation.
      Convert lag (in samples × 125 ms) into an estimated propagation direction and
      speed across the rig. This is the most direct evidence of "wave" behaviour
      (objective 2/4) as opposed to just uniform pressure increase.
- [ ] Peak/event detection: find local force spikes above a threshold, log their
      magnitude and which sensor row they hit first — supports the "shock-like
      behaviour" claim from the proposal.
- [ ] Save as `analysis/data/processed/trial_features.csv`.

### Phase 4 — Core analyses (mapped to research objectives)

**4a. Density → pressure relationship (Objective 1)**
- [ ] Using V1–V12 (no obstacle) only, plot mean `Total_N` (and its fluctuation
      features) vs `packing_fraction` / `phi_after_compression`.
- [ ] Fit a nonlinear model (as motivated by the proposal's "pressure is a nonlinear
      function of density, low below threshold, rising rapidly beyond it") — try a
      piecewise/threshold model or a power-law/exponential fit via
      `scipy.optimize.curve_fit`; report fit parameters, R², and residuals.
- [ ] Compare `single_layer == yes` vs `NO_partial_2nd_layer` versions — does the
      transition to a second layer mark the critical density visually/statistically?
- [ ] Compare across `ratio_10mm_13mm` groups at matched `total_balls` to see if
      particle-size heterogeneity changes the packing/force relationship (this
      mirrors real crowds having a mix of body sizes).

**4b. Wave propagation & shock behaviour (Objective 2)**
- [ ] Using the cross-correlation lag features from Phase 3, quantify propagation
      speed across the rig and see how it changes with density (V1–V12) and with
      obstacle presence (V13–V48 vs the matching no-obstacle baseline V10).
- [ ] Time-align and average trials within a version to get a "canonical" waveform,
      then visualize how a disturbance introduced by the obstacle appears first at
      one sensor row and lags at others — a directly interpretable wave-propagation
      figure for the paper.

**4c. Obstacle geometry effects (Objectives 3 & 5)**
- [ ] Using V13–V48 (all same density, only obstacle parameters vary), analyze how
      `obstacle_shape` (straight vs s), `obstacle_size_cm`, `obstacle_angle_deg`, and
      `obstacle_position` (middle vs middle_back) affect: peak force, fluctuation
      energy, asymmetry, and propagation speed/lag.
- [ ] Run a factorial ANOVA (or multiple regression with categorical predictors) on
      the trial feature table with shape/size/angle/position as factors — identify
      which obstacle parameter has the largest effect size on "dangerous" force
      spikes. This is the "identify conditions under which pressure becomes
      dangerous" objective (5) — the ANOVA/effect-size table is the core deliverable.
- [ ] Rank the 36 obstacle configurations by peak/fluctuation force to identify the
      most dangerous combination(s) — a good headline result for both paper and
      competition pitch.

**4d. Model validation against theory (Objective 4)**
- [ ] Revisit the proposal's continuous conservation + nonlinear-pressure model.
      Even a simplified 1D version (mass/momentum balance along the rig's
      front-to-back axis) can be fit to the row-averaged sensor data.
- [ ] Compare model-predicted vs measured force profiles; report agreement
      (R², RMSE) and where the model breaks down (e.g. does it fail to predict wave
      speed at very high density, or near obstacles?). Discussing where theory and
      data diverge is valuable content for the paper's Discussion section, not a
      weakness to hide.

### Phase 5 — Statistical rigor
- [ ] For every headline comparison (density groups, obstacle groups), report
      mean ± std (or 95% CI) across the ~10 trials, not single-trial numbers.
- [ ] Use appropriate tests: t-test/ANOVA for group comparisons, correlation/
      regression for continuous relationships (density vs force), and correct for
      multiple comparisons if testing many obstacle configurations pairwise.
- [ ] Check trial-to-trial variance itself as a result — does variance increase near
      the critical density/dangerous obstacle configs? (Higher variance = less
      predictable = arguably more "dangerous," worth its own figure.)

### Phase 6 — Visualization gallery for the paper/poster
Use the `dataviz` skill for anything chart-shaped. Plan a minimal, non-redundant set:
- [ ] Fig 1: rig/sensor layout diagram (schematic, not data) — orients the reader.
- [ ] Fig 2: representative raw time-series (baseline vs obstacle trial).
- [ ] Fig 3: force vs packing fraction with nonlinear fit + threshold marker.
- [ ] Fig 4: wave-propagation figure (lagged sensor traces + estimated speed).
- [ ] Fig 5: obstacle factor effect-size plot (e.g. bar/forest plot from the ANOVA).
- [ ] Fig 6: "danger ranking" of obstacle configurations.
- [ ] Fig 7 (optional): model vs measured comparison.
Keep each figure tied to exactly one objective/claim in the text.

### Phase 7 — Writing it up
- [ ] Map Phase 4 results directly onto the proposal's 5 objectives — one
      results subsection per objective, in that order, mirrors the abstract and
      makes the paper's structure obviously complete.
- [ ] Methods section: describe the physical analogue rig, sensor layout, sampling
      rate (8 Hz / 30 s trials), and the full experimental design table (from
      `INDEX.csv`) as your Table 1.
- [ ] Discussion: connect back to real stampede safety — translate "dangerous
      obstacle configuration" findings into practical guidance (e.g. avoid narrow
      angled chokepoints at high density) since the proposal's broader-impact claim
      is about real crowd safety.
- [ ] For competition (ISEF-style): prepare a condensed poster narrative — problem →
      model → rig → 2-3 headline figures → practical implication. Have the
      density-threshold plot and the danger-ranking plot ready as the two must-show
      figures; judges respond well to a clear "here's the threshold, here's what's
      worse than expected" story.

### Phase 8 — Reproducibility
- [ ] Keep all cleaning/feature/analysis logic in versioned scripts under
      `analysis/scripts/`, not only in notebooks — notebooks call into the scripts.
- [ ] Commit `analysis/` (code, not large data) to git incrementally as each phase
      lands, so the analysis history itself is available if reviewers/judges ask
      about methodology.

## 6. Progress log (update this as work lands, so a new session can pick up fast)

- **Phase 0 (setup):** done. `.venv/` + `requirements.txt` (pandas, numpy, scipy,
  matplotlib, seaborn, pyarrow, statsmodels). `analysis/{data,scripts,figures,results}/`
  created.
- **Phase 1 (cleaning/validation):** done via `analysis/scripts/load_data.py` +
  `validate_cleaning.py` + `check_drift_shape.py`. Findings: `Total_N` exactly
  equals sum of 6 sensors (no reconstruction needed); calibration is excellent
  (measured = 0.999×expected, R²=0.9998); **every trial shows a universal,
  accelerating downward drift** (~-0.02 to -0.03 N/s, gets steeper not
  flatter — ruled out simple settling-to-equilibrium and ruled out a
  session/run-order artifact; most likely tied to the physical setup, since
  it's ~1.7x stronger in `NO_partial_2nd_layer` trials than clean
  `single_layer=yes` ones). Policy: use first-1s baseline for static
  comparisons, detrend before computing fluctuation features, keep drift
  slope itself as a feature.
- **Phase 3 (feature table):** done, `analysis/data/processed/trial_features.csv`
  (480 rows x 35 cols) via `build_features.py`. **Major correction along the
  way:** the originally-planned lag-cross-correlation "wave speed" method was
  validated as non-functional (never reliably detects anything, even on
  obstacle trials) and was replaced with `front_back_redistribution` /
  `front_middle_redistribution` / `middle_back_redistribution` (plain
  whole-trial correlation between raw row signals) — see §5.1 above for the
  full reasoning. This turned out to be the single most useful feature in
  the whole analysis.
- **Phase 4a (density -> pressure, V1-V12):** done via
  `density_pressure_analysis.py` (`analysis/figures/08_density_pressure_relationship.png`).
  Honest null result: neither measured-vs-expected weight deviation
  (r=-0.07, p=0.47) nor fluctuation coefficient-of-variation (r=0.15, p=0.09)
  trend meaningfully with packing fraction alone in the undisturbed baseline.
  **Density alone does not destabilize the packing in this range (0.35-0.89)
  — an external disturbance is required.** This sharpens (doesn't refute) the
  proposal's critical-density claim: state it as density+disturbance jointly
  mattering, not density alone.
- **Phase 4c (obstacle factors, V13-V48):** done via
  `obstacle_factor_analysis.py` (results in `analysis/results/anova_*.csv`,
  `ranking_*.csv`) + `plot_obstacle_angle_effect.py`
  (`analysis/figures/09_obstacle_angle_effect.png`). **Headline result:**
  `redistribution_strength` (|front-back correlation|) is very well explained
  by obstacle geometry (~71% of variance, residual only 29%), overwhelmingly
  driven by `obstacle_angle_deg` (32%) and its interaction with
  `obstacle_shape` (15%) — **45 degrees produces the strongest, most
  consistent redistribution regardless of shape; 60 degrees is generally
  safest, especially for the "s"-shaped obstacle** (drops to ~0.6-0.7 with
  wide spread, vs ~0.88 at 45 degrees). By contrast, `fluctuation_std_N` and
  `spike_above_baseline_N` are mostly noise (~93% residual each) — obstacle
  geometry barely predicts raw fluctuation/spike magnitude, only the
  redistribution pattern. Report `redistribution_strength` as the headline
  danger metric, not the other two.
- **Phase 4d (model validation):** done via `spectral_and_relaxation_model.py`
  (`analysis/figures/10_power_spectrum.png`,
  `analysis/results/relaxation_model_fits.csv`). Two negative/clarifying
  results, both honestly reported rather than dressed up: (1) power spectral
  density confirms — via an independent, standard method, not just the
  earlier cross-correlation check — there is no periodic/oscillating wave
  (peak frequency location was checked across 30 trials and scatters
  randomly, std=1.3 Hz, i.e. it's noise); (2) exponential relaxation fits
  degenerate to unphysical tau values (hundreds of thousands of seconds),
  meaning the redistribution process is still actively developing throughout
  the full 30s trial and never reaches equilibrium — consistent with, and a
  per-row confirmation of, the earlier "accelerating not decelerating drift"
  finding. Middle fits worst (R^2~0.24, little real trend to fit -- matches
  it being the "quiet anchor"); Back fits "best" (R^2 up to 0.89) but that
  just reflects a strong linear trend, not real relaxation curvature.
- **Phase 5 (statistical rigor pass):** done via `statistical_rigor_pass.py`
  (`analysis/results/tukey_hsd_all_versions.csv`). Bootstrap 95% CIs:
  obstacle-vs-no-obstacle redistribution difference is robust
  ([+0.345, +0.453], nowhere near zero); the density-vs-fluctuation-CV
  correlation from Phase 4a is now formally killed, not just borderline
  (95% CI [-0.040, +0.332], crosses zero -- do not state this trend in the
  paper). Tukey HSD (corrected) on obstacle_angle_deg: all three angles
  differ significantly from each other, refining the danger ordering to
  **45 deg > 75 deg > 60 deg** (a non-monotonic "sweet spot" at 60, not
  simply "higher angle = safer"). **Important correction to Phase 4c:**
  Tukey HSD across all 36 individual versions shows only 264/630 (42%)
  pairwise comparisons remain significant after correction, and the #1-ranked
  "most dangerous" version (V16) is only significantly different from 14/35
  (40%) of the others. **Do not report an individual "most dangerous
  version" ranking as precise/definitive in the paper -- report the
  angle/shape-interaction factor effect (which IS robust) as the headline
  claim instead.**
- **Not yet started:** Phase 4b write-up framing (redistribution, not wave
  speed — data and stats already computed, just needs to become prose),
  Phase 6 (final figure polish for paper/poster), Phase 7 (writing), Phase 8
  (git commit — substantial uncommitted work has accumulated, see `git status`).

## 5. Open questions to resolve early (don't guess — check the data or ask)
- **[PARTIALLY NARROWED FROM DATA, STILL NEEDS PHYSICAL CONFIRMATION]** Which
  direction do obstacles introduce disturbance from — is Front the side nearer
  the obstacle in `middle` vs `middle_back` positions? Using all 3 rows (not
  just Front/Back), the data shows: (a) Middle's own start-to-end change is
  essentially IDENTICAL between `middle` and `middle_back` (-0.283 vs -0.287 N,
  noise-level difference) -- moving the obstacle only rebalances the Front/Back
  split around Middle, it doesn't touch Middle itself; (b) Middle and Back move
  together (correlation ~+0.47) while Front moves opposite to both (Front-Middle
  ~-0.42, Front-Back ~-0.8 to -0.84) -- Front is consistently the "winner" that
  gains force, Middle+Back the "losers," in every obstacle trial and even
  (much more weakly) in the no-obstacle baseline (fb corr ~-0.40 at baseline vs
  ~-0.77/-0.84 with an obstacle). This means the front-loading tendency is
  likely partly a baseline characteristic of the rig itself (e.g. a slight
  tray tilt), which an obstacle then strongly amplifies rather than creates
  from nothing -- **worth checking physically whether the tray is level**.
  Still needs ground-truth physical confirmation (see below) before stating
  obstacle-to-sensor geometry as fact in the paper.
  **How to confirm physically:** (1) check if the tray is level/tilted --
  directly testable and would explain the baseline front-bias; (2) with the
  physical rig, press a finger directly on the obstacle's marked spot for each
  of `middle`/`middle_back` and see which sensor row (now checking all 3, not
  just 2) spikes hardest/first; (3) ask Krishiv directly to confirm tray
  levelness and where `middle_back` sits relative to Middle and Back rows.
- **[RESOLVED, see below]** ~~Is there a specific "disturbance event" logged in
  each trial, or is the disturbance just the obstacle's constant presence?~~

### 5.1 Resolved: there is no fast traveling wave in this data — there is slow redistribution instead

Phase 3 originally implemented "wave propagation" as a cross-correlation lag
search between detrended sensor-row residuals (looking for a fast disturbance
arriving late at a downstream row). Validated against all 480 trials: this
**never reliably fires** — peak correlation stayed ~0.11-0.16 everywhere
(below any reasonable significance threshold), identically for obstacle and
no-obstacle trials. Conclusion: there is no fast (sub-second, delayed-copy)
propagating pulse detectable in this 8 Hz data, with or without an obstacle.

Testing the alternative hypothesis instead — that the *slow settling trend*
itself is the signal, not a nuisance to remove — found a real, validated
effect: the plain whole-trial correlation between raw (non-detrended)
front-row and back-row force is strongly **negative** (front and back force
move in anti-phase as the packing settles, i.e. force redistributes from one
end to the other rather than a pulse arriving late). This is:
- much stronger and more consistent with an obstacle present
  (mean r = -0.81, std 0.11) than without one (mean r = -0.40, std 0.31,
  see `analysis/figures/07_front_back_redistribution.png`)
- moderately correlated with packing fraction in the no-obstacle density
  sweep (r = 0.50 between density and \|correlation\|)

**Implication for the plan:** Phase 4b ("wave propagation & shock behaviour")
should be reframed as **force redistribution / anti-phase coupling**, not
literal traveling-wave speed. The `front_back_redistribution`,
`front_middle_redistribution`, `middle_back_redistribution` columns in
`trial_features.csv` are the reliable features for this; the `lag_*_ms` and
`corr_*_residual` columns are kept for transparency but should be treated as
noise, not evidence of anything. This is itself a legitimate, citable result:
it still supports the core proposal claim that crowds/packings shift from
independent-particle behaviour to coupled, structure-wide force transmission
as density (and disturbance) increase — it's just a redistribution effect
rather than a fast shock wave, which is worth stating explicitly and
honestly in the paper rather than forcing the wave framing to fit.
