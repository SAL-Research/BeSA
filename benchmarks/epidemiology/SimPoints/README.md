# SimPoint Pipeline Validation for BioDynaMo — Summary

## What this is

A record of the work done to validate a **SimPoint-based benchmark reduction pipeline**
for BioDynaMo, on the `biodynamo-benchmark-suite` GCP VM. 

Two runs are documented here:
1. A **small, single-threaded smoke test** (100 agents, 20 iterations) — used to validate that every step of the pipeline works correctly before committing to a full-scale run.
2. The **real, full-scale target run** (200 million agents, 1,300 iterations, single-threaded) — the actual deliverable.
**Status: both the smoke test and the 200M-agent run have completed the BBV → SimPoint stages successfully.** gem5 Full-System Simulation is the remaining stage, not yet executed.

---

## The pipeline, in order

### 1. Confirmed BioDynaMo runs on the VM
- Core BioDynaMo (v1.05.153) was already installed via the official installer.
- The `~/biodynamo-fork` repo holds the epidemiology demo source and a custom `measles.json`
- Built binary: `~/biodynamo-fork/demo/epidemiology/build/epidemiology`.

### 2. Understood BioDynaMo's threading structure (read biodynamo-synchronization-structure md file for more info)
- One simulation timestep = one call to `Scheduler::Execute()`.
- By default (`execution_order = kForEachAgentForEachOp`, confirmed as the actual default in `param.h`), all agent operations for a timestep run inside **one single parallel region** per timestep, not one per operation. 
- This doesn't affect the current single-threaded smoke test, but is documented for when multi-threaded runs are tackled.

### 3. Installed and validated instrumentation tools
Two tools were tried, in order:

- **Intel Pin (4.2)** — installed, confirmed working on a trivial program (`/bin/ls`), then
  confirmed working on the actual BioDynaMo binary (instruction-counting only, not full BBV
  generation — Pin's PinPoints tool is not bundled with modern Pin kits, and the actively
  maintained replacement, Intel's `pinplay-tools`/`GlobalLoopPoint`, requires a separate
  Intel SDE install and has incomplete documentation for the single-threaded case — deferred
  to future work).
  - Required fix: `sudo sysctl -w kernel.yama.ptrace_scope=0` — BioDynaMo's MPI-linked
    dependencies were tripping Pin's process-attach mechanism.
- **Valgrind's `exp-bbv` tool (Valgrind 3.18.1)** — this is the tool actually used to
  generate real data. It's purpose-built for SimPoint, produces SimPoint's exact expected
  file format, and was already available via `apt install valgrind`.

### 4. Generated real Basic Block Vector (BBV) data
**Smoke test** (100 agents, 20 iterations):
```bash
OMP_NUM_THREADS=1 valgrind --tool=exp-bbv --interval-size=10000000 \
  --bb-out-file=bbv.out --pc-out-file=pc.out \
  ./build/epidemiology --config measles.json \
  --inline-config '{"bdm::SimParam":{"initial_population_infected":10,"initial_population_susceptible":90,"number_of_iterations":20,"repeat":1}}'
```
- Produced `bbv.out`: 3,992 intervals (10M instructions each) from a ~39.9 billion
  instruction run. Format validated directly.
**Full-scale run** (200 million agents, 1,300 iterations):
```bash
OMP_NUM_THREADS=1 valgrind --tool=exp-bbv --interval-size=100000000 \
  --bb-out-file=bbv_200m.out --pc-out-file=pc_200m.out \
  ./build/epidemiology --config measles.json \
  --inline-config '{"bdm::SimParam":{"initial_population_infected":10000000,"initial_population_susceptible":190000000,"number_of_iterations":1300,"repeat":1}}'
```

- Interval size increased to 100M instructions (vs. 10M for the smoke test) — deliberately, since interval size determines the eventual per-simulation-point cost in gem5, not just BBV file/interval count. At this scale, a 10M interval size would have produced tens of millions of intervals with each simulation point still needing a feasible detailed-simulation size.
- Launched in a `tmux` session (`bbv_200m`) for resilience against SSH disconnection.
- Peak memory usage during the run reached **~57GB RSS (92%+ of the VM's 58GB total)**, with zero swap configured.

### 5. Ran SimPoint itself — first real clustering result
Tool: `~/SimPoint/bin/simpoint` 
```bash
./bin/simpoint -loadFVFile ~/biodynamo-fork/demo/epidemiology/bbv.out \
  -maxK 30 -numInitSeeds 5 \
  -saveSimpoints output/biodynamo/simpoints.out \
  -saveSimpointWeights output/biodynamo/weights.out
```

**Result: k=20 clustering chosen (best BIC score among 7 candidates tried via binary
search).** 20 simulation points found, each with an associated weight (proportion of total
execution that cluster represents). Weights are well-distributed and sum to 1.0 — one
cluster (interval 2160) dominates at 28.5% of total execution; the smallest is 0.25%.

---

### 6. Ran SimPoint — full-scale (200M-agent) result
 
```bash
./bin/simpoint -loadFVFile ~/biodynamo-fork/demo/epidemiology/bbv_200m.out \
  -maxK 30 -numInitSeeds 5 -sampleSize 50000 \
  -saveSimpoints output/biodynamo_200m/simpoints.out \
  -saveSimpointWeights output/biodynamo_200m/weights.out
```
- `-sampleSize 50000` used because the full BBV file contained several million intervals (100M-instruction intervals over a ~3.4×10¹⁴-instruction run). This sub-sampling is SimPoint's intended mechanism for exactly this situation (Hamerly et al. 2005); the un-sampled intervals are assigned to their nearest cluster afterward.
- **Result: k=12 clustering chosen** (BIC-threshold best clustering, post-processing run 7).
  12 simulation points, weights summing to 1.0 (verified: 0.03252 + 0.10598 + 0.01698 + 0.01378
  + 0.13504 + 0.0632 + 0.09426 + 0.0186 + 0.00208 + 0.01334 + 0.00002 + 0.5042 = 1.00000).
  - **One cluster (interval 1,874,595) represents 50.42% of the entire run's execution** —
    a single simulation point standing in for over half the total behavior. 
    
- Full simulation points (interval index, cluster ID):
```
  87111 0      3233691 1     381406 2     252160 3
  738251 4     417709 5      2190207 6    183953 7
  9575 8       309860 9      2976 10      1874595 11
```
- Full weights (weight, cluster ID):
```
  0.03252 0    0.10598 1     0.01698 2    0.01378 3
  0.13504 4    0.0632 5      0.09426 6    0.0186 7
  0.00208 8    0.01334 9     2e-05 10     0.5042 11
```
 
---

## Tools installed and their locations

| Tool | Location | Purpose |
|---|---|---|
| BioDynaMo core | `~/biodynamo-v1.05.153/` | The simulation framework itself |
| BioDynaMo fork (demo + config) | `~/biodynamo-fork/` | Epidemiology demo source, `measles.json`, built binary |
| Intel Pin 4.2 | `~/pin-external-4.2-99776-g21d818fa2-gcc-linux/` | Instrumentation (validated but not used for final BBV generation) |
| Valgrind 3.18.1 (`exp-bbv`) | system package (`apt`) | BBV generation — the tool actually used |
| SimPoint (GCC-9 fork) | `~/SimPoint/` | Clustering / simulation point selection |
| gem5 | `~/gem5/` | Not yet used — planned for the checkpoint/detailed-simulation stage, after simulation points are finalized on the real-scale run |

---