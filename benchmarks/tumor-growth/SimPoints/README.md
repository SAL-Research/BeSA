# SimPoint Pipeline Validation for BioDynaMo — Tumor Growth Summary

## What this is

A record of the work done to run the **SimPoint-based benchmark reduction pipeline**
on BioDynaMo's `tumor_concept` demo, on the `biodynamo-benchmark-suite` GCP VM —
the second workload in the ABM benchmark suite, alongside `epidemiology`.

Unlike epidemiology (a **static-population** model — agents transition state but total
count never changes), `tumor_concept` is a **dynamic-population** model: only the
*initial* population is set; from there, a division rule drives population as an
emergent function of runtime. 

---

## The pipeline, in order

### 1. Parameterized the demo

The original `tumor_concept.h`/`tumor_concept.cc` hardcode population (2,400) and
step count (500) as C++ literals — no `--config` support at all. Mirrored
epidemiology's own `SimParam`/`measles.json` convention so scale points can be swept
without recompiling:

| File | Change |
|---|---|
| `src/sim-param.h` | New `SimParam : public ParamGroup` — `initial_static_population`, `number_of_iterations`, cell diameters, growth rate, division probability, seed position, `progress_report_interval` |
| `src/tumor_concept.h` | Reads from `SimParam`; adds a population `TimeSeries` collector; adds `ProgressReportOp` (see §4) |
| `src/tumor_concept.cc` | Registers `SimParam` once in `main()` |
| `generate_scale_configs.py` | Generates population-sweep configs with domain size scaled to hold density constant (`L = L_baseline · (N/N_baseline)^(1/3)`) |

### 2. Calibrated cost before committing to a full-scale run

Built `calibrate_tumor_bbv.sh` / `parse_calibration.py`: runs `OMP_NUM_THREADS=1
exp-bbv` at `iterations=0` and `iterations=3` across several population points, fits
`instructions ≈ a·N + b` separately for one-time init cost and per-iteration cost.

### 3. Key finding: `tumor_concept` has no natural population throttle

The original target was 1,300 iterations, matching epidemiology's 200M-agent run, for a
direct comparison point. **This is not achievable, and the reason is a specific,
quantifiable property of the model:**

`Growth::Run`'s division branch is a fixed 80% probability (`division_probability`),
with **zero coupling to local crowding** — no contact inhibition. This is a
Galton–Watson branching process with expected offspring `2p = 1.6` per division cycle —
supercritical (the critical threshold is `p = 0.5`), so population growth is unbounded
in expectation by construction, not by accident of parameter choice.

Measured consequence, native single-threaded trajectory (`random_seed=4357`):

| iter | agents | note |
|---|---|---|
| 300 | 2,533 | lag phase |
| 500 | 5,159 | |
| 700 | 41,892 | |
| 800 | 137,558 | |
| 950 | 1,213,955 | |

Segment cost (wall-clock per 50 iterations) grew by a consistent **~3–4× multiplier**
per segment once past iteration ~700. The domain (100×100×100, diameter-8 cells) has a
physical packing ceiling of **~3,730 cells at 100% density** — population already
exceeds this around iteration ~500–550. Projected cost of continuing toward 1,300
iterations: **days per remaining 50-iteration segment**, confirmed by one live attempt
killed after 12 CPU-days, still short of 1,000 iterations.

**Decision:** abandoned the 1,300-iteration target. Used the actual measured trajectory
to choose **800 iterations** as the cutoff — captures the full lag → exponential →
onset-of-overcrowding arc without entering the computationally intractable tail.

Also found: BDM seeds RNG per-thread (`prng[tid].SetSeed(random_seed*(tid+1))`), so the
16-thread native reference trajectory above **differs** from the actual
`OMP_NUM_THREADS=1` trajectory used for BBV generation (the single-threaded run
compounds faster). The 800-iteration cutoff was re-validated against the single-threaded
trajectory directly before the real BBV run, not just the native reference.


### 4. Generated real BBV data

```bash
OMP_NUM_THREADS=1 valgrind --tool=exp-bbv --interval-size=100000000 \
  --bb-out-file=tumor_bbv_800.bb --pc-out-file=tumor_bbv_800.pc \
  ./tumor_concept --config tumor_bbv_800.json
```
(`tumor_bbv_800.json`: `initial_static_population=2400`, `number_of_iterations=800`)

- **24,974 total intervals** (100M-instruction intervals)
- **2,497,449,563,436 total instructions** (~2.50 trillion)
- 67,794 unique basic-block reps (single thread)

### 5. Measured and trimmed ROOT/cling JIT startup contamination

`exp-bbv` has no ROI markers, so the fixed ROOT/cling JIT + program-startup cost — present
identically in every run regardless of workload — lands in the trace's first intervals.
Measured via a `population=0, iterations=0` baseline config (`tumor_jit_baseline.json`,
`measure_jit_startup.sh`):

- **Fixed startup cost: 15,964,465,143 instructions** → **160 intervals** to skip at
  `--interval-size=100000000`
- Trimmed via `trim_bbv_startup.sh tumor_bbv_800.bb 160` → 24,823 intervals remaining
  (offset recorded: simpoint interval *i* in the trimmed file = original interval
  *i + 160*)

### 6. Ran SimPoint — result

```bash
~/SimPoint/bin/simpoint -loadFVFile tumor_bbv_800_clean.bb \
  -maxK 30 -numInitSeeds 5 -dim 15 \
  -saveSimpoints tumor_800.simpts -saveSimpointWeights tumor_800.weights \
  -saveLabels tumor_800.labels -saveVectorWeights tumor_800.vecweights
```

**Result: k=10 clustering chosen** (BIC-threshold best clustering, post-processing run
7) — deliberately **not** reusing epidemiology's k=12; BIC was left to search
independently given the two workloads are structurally different classes of ABM. Weights
verified summing to 1.00000063 (floating-point rounding).

Full simulation points (interval index in the trimmed file, cluster ID — add 160 for
original-file interval number):
```
2428 0    11604 1   90 2      1233 3    22711 4
11998 5   297 6     36 7      319 8     5115 9
```
Full weights (weight, cluster ID):
```
0.00342549 0   0.00205529 1   0.00237769 2   0.0671798 3
0.257597 4     0.425284 5     0.0141855 6    0.00241799 7
0.00656887 8   0.218909 9
```
**One cluster (interval 11,998, cluster 5) represents 42.5% of the run's execution**;
the top 3 clusters (5, 4, 9) together cover **90.2%**.

**Comparison to epidemiology's own result:** both workloads independently converge on
the same qualitative shape — one dominant cluster near 50% plus a long tail of small
clusters (epidemiology: 50.4% dominant, top-4 = 84%; tumor: 42.5% dominant, top-3 =
90.2%) — despite being structurally different ABM classes. Note: SimPoint intervals are
fixed-instruction-count chunks, so interval position is instruction-fraction, not
iteration-fraction. For epidemiology (roughly steady per-iteration cost) these track
closely; for `tumor_concept`, given the extreme cost nonlinearity in §3, a
mid-instruction-space cluster (e.g. interval 11,998 ≈ 48% of instructions) very likely
corresponds to a late-iteration-space moment (deep in the 700s), not the run's midpoint
in simulated time.

---

## Tools and file locations

| Tool / file | Location | Purpose |
|---|---|---|
| BioDynaMo core | `~/biodynamo-v1.05.153/` | The simulation framework itself |
| BioDynaMo fork (demo + patch) | `~/biodynamo-fork/demo/tumor_concept/` | `tumor_concept` source, `SimParam` patch, built binary |
| Calibration scripts | `~/biodynamo-fork/demo/tumor_concept/calibration/` | `calibrate_tumor_bbv.sh`, `parse_calibration.py`, `measure_jit_startup.sh`, `tumor_jit_baseline.json` |
| Valgrind 3.18.1 (`exp-bbv`) | system package (`apt`) | BBV generation |
| SimPoint (GCC-9 fork) | `~/SimPoint/` | Clustering — **requires `ulimit -s unlimited`** for this workload, see §8 |
| `trim_bbv_startup.sh` | `~/biodynamo-fork/demo/tumor_concept/build/` | Strips JIT-startup intervals from a `.bb` file before `-loadFVFile` |
| gem5 | `~/gem5/` | Not yet used — planned checkpoint/detailed-simulation stage, after Axis A results are also in hand |
