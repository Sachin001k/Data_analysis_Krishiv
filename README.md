# Crowd Pressure Waves — Data Analysis, Explained from Scratch

This document explains, in plain language, everything we did in this project —
from raw sensor files to final results — so that anyone (even without a data
science or physics background) can follow along. If you want the short
technical planning version instead, see [CLAUDE.md](CLAUDE.md). This file is
the "how and why," written for a first-time reader.

---

## 1. What is this project actually about?

In a real crowd — at a stadium, a religious gathering, a concert — when too
many people are packed too closely together, sometimes a small push from one
side can travel through the crowd and crush people somewhere else, even if
nobody is running or panicking. This has caused real, fatal stampedes.

Studying that directly with real people would be dangerous and unethical. So
this project uses a **physical stand-in (an "analogue")**: hundreds of small
plastic balls (two sizes, 10 mm and 13 mm) packed together on a tray, standing
in for densely packed people. A sensor rig underneath measures the force being
pushed down onto 6 points on the tray. By changing how many balls are used,
how the two ball sizes are mixed, and by inserting obstacles into the packed
balls at different shapes/sizes/angles/positions, we can safely study:

- Does packing things more densely make the system less stable?
- Does an obstacle (like a person or a barrier the crowd has to move around)
  cause force to build up and move around in dangerous ways?
- Can we measure and predict when a "crowd" (of balls) becomes dangerous?

The full research proposal (written before data collection) is in
`Omotec Project - Krishiv Kedia.pdf`, under "Project 2."

---

## 2. The raw data we started with

Folder: [data_logging_final/](data_logging_final/)

### 2.1 The experiment design table — `INDEX.csv`

This file describes **48 different experimental setups**, called "versions"
(`V1` through `V48`). Each row tells us things like:

- `total_balls` — how many balls were used (300–600). More balls packed into
  the same tray = a denser "crowd."
- `ratio_10mm_13mm` — how the two ball sizes were mixed (`equal`, `1:3`, or
  `3:1`). Real crowds are a mix of body sizes too, so this tests whether that
  matters.
- `packing_fraction` — a number between 0 and 1 saying what fraction of the
  tray's volume is actually filled with ball material rather than empty gaps.
  Higher = more tightly packed = denser. This is our main "how crowded is it"
  number.
- `expected_total_N` — the theoretical weight (in Newtons, the physics unit
  for force) of all the balls combined, calculated from their known mass. This
  is what a perfect, frictionless scale *should* read.
- `obstacle_shape`, `obstacle_size_cm`, `obstacle_angle_deg`,
  `obstacle_position` — for versions `V13`–`V48` only, these describe a solid
  obstacle placed inside the packed balls: its shape (a straight bar or an
  "S" curve), its size, the angle it's tilted at (45°, 60°, or 75°), and
  where it sits (`middle` or `middle_back`).
- `trials` — how many times each setup was repeated (10 times, to make sure
  results aren't just a fluke).

`V1`–`V12` change only density and ball-size mix, with **no obstacle** — this
half of the data answers "does crowding alone cause danger?"

`V13`–`V48` all use the *same* fixed density, but sweep every combination of
obstacle shape × size × angle × position (2×3×3×2 = 36 setups) — this half
answers "what about an obstacle makes things dangerous?"

### 2.2 The sensor recordings — `v{version}t{trial}.csv`

Each of the 480 files (e.g. `v6t9.csv` = version 6, trial 9) is one 30-second
recording from the sensor rig, looking like this:

```
time_ms, Back_L_N, Back_R_N, Middle_L_N, Middle_R_N, Front_L_N, Front_R_N, Total_N
0,       3.458,    3.459,    3.312,      3.43,       3.458,     3.492,     20.609
125,     3.357,    3.427,    3.392,      3.382,      3.316,     3.527,     20.401
...
```

- The rig has **6 force sensors** arranged in a 3×2 grid under the tray: Back,
  Middle, and Front rows, each with a Left and Right sensor. This spatial
  layout is what lets us study *where* force builds up, not just how much.
- Readings are taken every **125 milliseconds**, i.e. **8 times per second**
  (called the "sampling rate," 8 Hz), for **30 seconds** — 240 readings per
  trial.
- `Total_N` is just all 6 sensors added together — the total downward force
  the whole crowd of balls is exerting at that instant.

---

## 3. Concepts you need to understand the rest of this document

You don't need to be an expert — just know what these words mean:

| Term | Plain-language meaning |
|---|---|
| **Force (Newton, N)** | A push or pull. Here, it's how hard the balls press down on a sensor. |
| **Density / packing fraction** | How tightly packed something is. A packed subway car has higher "density" than an empty one. |
| **Mean / average** | Add up all the numbers, divide by how many there are. |
| **Standard deviation (std)** | How spread out the numbers are around the average. Small std = very consistent; big std = jumps around a lot. |
| **Coefficient of variation (CV)** | Standard deviation divided by the mean — lets you compare "how noisy" two signals are even if they have very different average sizes. |
| **Correlation** | A number from -1 to +1 saying how two things move together. +1 = they always go up and down together. -1 = when one goes up, the other always goes down (this is called **anti-correlation**). 0 = no relationship at all. |
| **Trend / drift** | A slow, steady change over time (e.g. a signal that keeps decreasing minute after minute), as opposed to random up-and-down noise. |
| **Detrending** | Mathematically removing a slow trend from a signal so you can see the smaller wiggles underneath more clearly. |
| **R² ("R-squared")** | A number from 0 to 1 saying how well a mathematical model/line fits real data. 1 = perfect fit, 0 = the model explains nothing. |
| **p-value** | A number from statistics that answers "could this result just be random chance?" Small p (usually below 0.05) means "probably not chance — this is a real effect." |
| **ANOVA (Analysis of Variance)** | A statistical method for testing several possible causes at once and figuring out which one(s) actually matter, and how much each one contributes. |
| **Cross-correlation / lag** | A technique for checking if one signal is basically a delayed copy of another (e.g. "sensor B sees the same pattern as sensor A, just 2 seconds later"). |

---

## 4. Step-by-step: what we actually did

### Step 0 — Set up the tools

We installed Python (a programming language good at handling data) and a
"virtual environment" (`.venv/` — an isolated toolbox just for this project so
it doesn't interfere with anything else on the computer), plus these
libraries:

- **pandas** — for loading and organizing data tables (like a programmable
  Excel).
- **numpy** — for fast math on lists of numbers.
- **scipy** — for statistics and curve-fitting.
- **matplotlib** / **seaborn** — for making plots.
- **pyarrow** — for saving/loading data quickly in a compressed format
  (`.parquet`) instead of re-reading slow text CSVs every time.
- **statsmodels** — for the ANOVA statistical tests.

All the code lives in [analysis/scripts/](analysis/scripts/), one script per
step, so anything below can be re-run and checked.

### Step 1 — Load everything into one table and sanity-check it

Script: [analysis/scripts/load_data.py](analysis/scripts/load_data.py)

We read all 480 sensor files plus `INDEX.csv` and merged them into one big
table (saved as `analysis/data/processed/clean_trials.parquet`), then ran two
basic trust checks that any real experiment needs before you believe its
results:

1. **Does `Total_N` really equal the sum of the 6 individual sensors?**
   Yes — exactly, in every single row. Good, the data isn't corrupted.
2. **Does the sensor's resting reading match the known theoretical weight of
   the balls?** We compared the average force in the first second of each
   trial (before anything happens) against `expected_total_N` from
   `INDEX.csv`. They matched almost perfectly (within about a quarter of one
   percent, on average).

**Plot: [analysis/figures/02_baseline_calibration.png](analysis/figures/02_baseline_calibration.png)**
— every one of the 480 trials plotted as measured-force vs. expected-force. If
the sensors were badly calibrated, points would scatter away from the diagonal
line. They don't — they sit right on it. This tells us **we can trust the
sensor readings.**

### Step 2 — Look at what a single trial actually looks like

**Plot: [analysis/figures/01_raw_vs_smoothed.png](analysis/figures/01_raw_vs_smoothed.png)**
— the raw signal jitters slightly frame to frame (normal sensor noise), and a
"smoothed" version (a rolling average of 5 neighboring points) shows the
underlying trend more clearly without changing what it's saying.

**Plot: [analysis/figures/03_trial_repeatability.png](analysis/figures/03_trial_repeatability.png)**
— each experimental setup was repeated 10 times. Overlaying all 10 repeats of
one setup shows: (a) they all follow roughly the same shape (the experiment is
repeatable, not random junk), and (b) there's a clear, slow downward slope
shared by all 10 — total force drops over the 30 seconds. That slope became
the next thing we investigated.

### Step 3 — Investigate the mystery downward drift

This is a good example of **not just accepting a weird pattern, but testing
what's causing it**, since it could either be a boring measurement problem or
a real physical effect worth reporting.

We tested three explanations:

1. **Is it random noise?** No — it happens in **100% of all 480 trials**,
   always downward. Random noise wouldn't be this consistent.
   (Plot: [analysis/figures/04_drift_distribution.png](analysis/figures/04_drift_distribution.png))
2. **Is it the balls "settling" into a stable resting position (fast at
   first, then leveling off, like a bouncy ball settling down)?** We checked
   by comparing the slope of the *first* 10 seconds of each trial to the
   *last* 10 seconds. If settling, the first 10 seconds should show a faster
   drop than the last 10. We found the **opposite** — the last 10 seconds
   actually drop *faster* than the first 10 (statistically confirmed, not
   just chance). So it is **not** simple settling.
   (Plots: [05](analysis/figures/05_early_vs_late_slope.png),
   [06](analysis/figures/06_drift_shape_fit.png))
3. **Is it the sensor "warming up" or drifting simply because trials were run
   one after another over a long session?** We checked whether the drift got
   worse for trials run later in a back-to-back sequence — it didn't
   (no meaningful correlation). But the drift *was* consistently stronger in
   physically denser/less-stable setups (versions where a second layer of
   balls was starting to form, and in versions with an obstacle). This points
   to a **real physical cause** (the ball packing continuing to rearrange
   itself throughout the trial) rather than a measurement artifact — though
   we note this isn't 100% proven, just the best-supported explanation.

**Decision made from this:** since the drift is real and gets worse over time,
we can't just average the whole 30 seconds and call it "the" force for a
trial. We use the first-second reading for "resting force" comparisons, and
we mathematically remove ("detrend") each trial's own slope before measuring
how much it randomly fluctuates, so the steady drift and the random wobble
don't get mixed up.

### Step 4 — Turn each 30-second recording into a handful of meaningful numbers

Script: [analysis/scripts/build_features.py](analysis/scripts/build_features.py)
→ [analysis/data/processed/trial_features.csv](analysis/data/processed/trial_features.csv)

A raw trial is 240 numbers per sensor — too much to compare 480 trials by eye.
So for every trial, we calculated a small set of descriptive numbers instead,
including:

- **Average force** and **how fast it drifted downward**.
- **How much it randomly fluctuated** (after removing the drift).
- **Left-right imbalance** at the front, middle, and back rows.
- **Front-to-back redistribution** — explained next, because this needed a
  correction along the way.

#### A method that didn't work, and what we learned from that

Our first idea for detecting a "pressure wave" was to check whether a
disturbance seen at the Front sensors shows up slightly *later* at the Back
sensors — like an echo. We tested this rigorously across all 480 trials, and
it **never reliably worked**, even for trials with an obstacle specifically
meant to create a disturbance. This was an important negative result: it told
us there's no fast, "traveling pulse" style wave in this particular setup and
sampling rate.

Instead, we tested a different idea: maybe the *slow* trend itself (not fast
wobbles) is the interesting signal — maybe force isn't traveling from front
to back with a delay, but instead **shifting** from one to the other, like a
seesaw. Testing this found a strong, real effect: as a trial progresses, force
at the front and force at the back very often move in **opposite directions**
(a strong negative correlation) — this is the "redistribution strength"
feature, and it turned out to be the single most useful number in the whole
project.

### Step 5 — Does density alone (no obstacle) make things dangerous?

Script: [analysis/scripts/density_pressure_analysis.py](analysis/scripts/density_pressure_analysis.py)
→ [analysis/figures/08_density_pressure_relationship.png](analysis/figures/08_density_pressure_relationship.png)

Using the no-obstacle setups (`V1`–`V12`, density ranging from loosely to
very tightly packed), we checked two things as density increased:

1. Does the sensor start reading *less* than the true theoretical weight
   (which would suggest the packed balls are starting to "arch" and support
   some of their own weight through friction against the walls, hiding it
   from the sensor — a known effect in silos and grain storage)? **No** —
   no meaningful trend.
2. Does the random fluctuation in the signal grow as density increases (i.e.
   does the packing get "twitchier" just from being denser)? **Only a weak,
   not-quite-statistically-significant hint of this.**

**Conclusion: on its own, just packing the balls more densely — without
poking, shaking, or obstructing them — does *not* make the system noticeably
more unstable, across the whole density range we tested.** This actually
matches real life: people can stand extremely close together safely for
hours at a concert. It's not density alone that's dangerous — it's density
*combined with* a disturbance.

### Step 6 — What about the disturbance (the obstacle)? Which of its properties matter most?

Script: [analysis/scripts/obstacle_factor_analysis.py](analysis/scripts/obstacle_factor_analysis.py)
→ [analysis/figures/09_obstacle_angle_effect.png](analysis/figures/09_obstacle_angle_effect.png)

Using the 36 obstacle setups (`V13`–`V48`, same density throughout, only the
obstacle's shape/size/angle/position changes), we ran an **ANOVA** — a
statistical technique that takes several possible "suspects" (here: shape,
size, angle, position) and tells you how much each one actually explains
about the outcome, with a p-value for how confident we can be it's not just
random luck.

**The headline finding:** the obstacle's **angle** explains by far the most
(about a third of all the variation we see, with extremely high statistical
confidence), and how the angle interacts with the obstacle's **shape**
explains a further big chunk. Obstacle size and position matter much less.

Concretely: **a 45° obstacle angle produces the strongest, most consistent
front-to-back force redistribution — the "most dangerous" angle we tested.
60° is generally the safest angle, especially when combined with the
S-shaped obstacle**, where redistribution drops sharply and becomes much more
variable (sometimes low, sometimes not).

We also tested two other possible "danger" measurements (raw fluctuation size,
and how big the biggest force spike gets) — for those two, obstacle geometry
barely mattered at all (mostly random trial-to-trial noise). This tells us
**"front-to-back redistribution" is the meaningful danger signal here, not
raw shakiness or peak force.**

---

## 5. Summary of results, in one paragraph each

1. **The sensor rig is trustworthy.** Its readings match the true physical
   weight of the balls almost perfectly, so we can believe what it tells us.
2. **Every trial shows a real, physical downward drift in force that speeds
   up over time** rather than settling down — most likely the ball packing
   continuing to rearrange itself, more so in denser and obstacle-disturbed
   setups. This had to be handled carefully so it didn't contaminate other
   measurements.
3. **Density alone doesn't create instability.** Across a 2.5× range of
   packing density with no obstacle, the system stayed calm. Danger requires
   a trigger, not just crowding.
4. **An obstacle creates a strong, measurable "redistribution" of force from
   front to back (or back to front)** — much stronger and more consistent
   than anything density alone produces.
5. **The obstacle's angle is the single most important design factor.** A
   shallow 45° angle is the most disruptive/dangerous; 60°, especially with
   a curved ("S") obstacle shape, is the safest combination we tested.

---

## 6. What each plot tells you, at a glance

| Figure | What it shows | What to take away |
|---|---|---|
| [01_raw_vs_smoothed.png](analysis/figures/01_raw_vs_smoothed.png) | Raw vs. smoothed force signal for two example trials | Sensor noise is small; smoothing reveals the true trend without distorting it |
| [02_baseline_calibration.png](analysis/figures/02_baseline_calibration.png) | Measured resting force vs. theoretical expected weight, for all 480 trials | Nearly perfect diagonal line = the sensors are well calibrated and trustworthy |
| [03_trial_repeatability.png](analysis/figures/03_trial_repeatability.png) | 10 repeated trials of the same setup, overlaid | Repeats agree with each other (real experiment) and all share the same downward drift |
| [04_drift_distribution.png](analysis/figures/04_drift_distribution.png) | Histogram of the drift rate across all 480 trials | The drift is universal (100% negative), not random chance |
| [05_early_vs_late_slope.png](analysis/figures/05_early_vs_late_slope.png) | Each trial's drift rate in its first 10s vs. last 10s | Most points fall above the diagonal = drift speeds up over time (not "settling") |
| [06_drift_shape_fit.png](analysis/figures/06_drift_shape_fit.png) | A straight-line fit vs. a "settling-shaped" curve fit to one setup's average trial | The two fits are basically identical = no flattening-out curve shape is present |
| [07_front_back_redistribution.png](analysis/figures/07_front_back_redistribution.png) | Left: obstacle vs. no-obstacle redistribution strength. Right: redistribution strength vs. density (no obstacle) | Obstacles create far stronger, more consistent redistribution than density alone does |
| [08_density_pressure_relationship.png](analysis/figures/08_density_pressure_relationship.png) | Left: sensor accuracy vs. density. Right: fluctuation level vs. density (no obstacle) | Both are flat — density alone doesn't destabilize the system |
| [09_obstacle_angle_effect.png](analysis/figures/09_obstacle_angle_effect.png) | Redistribution strength grouped by obstacle angle and shape | 45° is the most dangerous angle; 60°+S-shape is the safest combination |

---

## 7. Where else this exact procedure is used in real life

The specific physics question here (crowd stampedes) is niche, but the
**analysis method** — the sequence of steps we followed — is the same
recipe used across almost all real-world sensor-data science. Recognizing
this pattern is one of the most useful things to take away:

1. **Validate your sensors before you trust your results.** (Step 1) This is
   standard in any field with instruments: medical devices, self-driving car
   sensors, industrial monitoring, scientific labs. If the tool isn't
   trustworthy, nothing built on top of it matters.
2. **Look for and explain unexpected patterns instead of ignoring them.**
   (Step 3) The same detective work — is this noise, a real effect, or an
   artifact of how the experiment was run? — is exactly what engineers do
   when a bridge sensor drifts, a server's response time creeps up over a
   day, or a battery's voltage sags during use.
3. **Turn raw signals into meaningful summary features before analyzing
   them.** (Step 4) This is the backbone of almost every applied
   machine-learning or statistics project: raw audio becomes pitch/tempo
   features for music apps; raw heart-rate sensor data becomes
   "resting heart rate" and "recovery time" for fitness trackers; raw
   accelerometer data from a phone becomes "steps" and "fall detected."
4. **Test simple causes before complex ones, and be willing to report a null
   result.** (Step 5) A huge amount of real research (drug trials, A/B tests
   on websites, safety engineering) comes down to "did the thing we expected
   to matter actually matter, or not?" — and a well-supported "no" is just as
   valuable as a "yes."
5. **Use statistics (like ANOVA) to figure out which of several factors
   actually drives an outcome, with a number attached to how confident you
   are.** (Step 6) This exact technique is used in manufacturing (which
   machine setting most affects product quality?), agriculture (which of
   soil type/water/fertilizer most affects crop yield?), and medicine (which
   patient factors most predict a health outcome?).

More directly, the specific finding here — **that geometry/angle of an
obstacle controls how dangerous a disturbance becomes, more than density
does** — is directly relevant to:

- **Crowd safety engineering**: designing barriers, railings, and pinch
  points at stadiums, religious gatherings, and transit stations to avoid
  dangerous angles that concentrate and redirect crowd force.
- **Granular material handling**: silos, grain storage, and mining chutes
  face the exact same physics (packed particles, obstacles, force
  redistribution, unexpected "arching"/settling behavior) and use the same
  kind of sensor-based monitoring.
- **Structural health monitoring**: bridges and buildings instrumented with
  distributed force/strain sensors are analyzed with this same
  "calibrate → find real trends → engineer features → statistically compare
  factors" pipeline.
