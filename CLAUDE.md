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

## 5. Open questions to resolve early (don't guess — check the data or ask)
- Which direction do obstacles introduce disturbance from — is Front the side
  nearer the obstacle in `middle` vs `middle_back` positions? This determines how to
  interpret propagation-lag sign in Phase 4b. Check any rig photos/notes if
  available; otherwise infer from which sensor row shows the earliest/largest
  response in obstacle trials vs V10 baseline.
- Is there a specific "disturbance event" logged in each trial (e.g. obstacle
  inserted at a known time), or is the disturbance just the obstacle's constant
  presence in the packed system? This affects whether wave analysis should look
  for a discrete event response or steady-state fluctuation statistics.
