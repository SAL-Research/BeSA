# BeSA: Benchmarks for Simulating Agent-based Models in Architecture Research

BeSA is the first benchmark suite for studying agent-based model (ABM)
simulations from a computer architecture perspective. It pairs representative
BioDynaMo workloads with a SimPoint + gem5 pipeline that reduces trillion-
instruction simulations to a handful of cycle-accurate regions, enabling
roofline analysis and DAMOV-methodology characterization.

> Amina Sokoli, A. Giray Yaglıkçı — CISPA Helmholtz Center for Information Security

## Benchmarks

| Benchmark | Population | Iterations | Dyn. insts | Clusters | Reduction |
|-----------|-----------|-----------|-----------|---------|----------|
| **Epidemiology** (SIR model) | 200M (static) | 1,300 | ~3.4 × 10¹⁴ | k = 12 | ~283,000× |
| **Tumor growth** (branching) | 2,401 → 133k (dynamic) | 800 | ~2.5 × 10¹² | k = 10 | ~2,500× |
| **Biofilm growth**  | TBD | TBD | TBD | TBD | TBD |

In both completed cases, execution concentrates in a few SimPoint clusters:
the largest cluster accounts for 50.4% (epidemiology) and 42.5% (tumor
growth) of total execution, and the top three clusters cover at least 75%.

## Repository layout

```
├── benchmarks/
│   ├── epidemiology/        Epi SimPoints, analysis plots, benchmark.env
│   ├── tumor-growth/        Tumor SimPoints, gem5 scripts, benchmark.env
│   └── biofilm/             (under development)
├── pipeline/                Generic SimPoint + gem5 pipeline
│   ├── configs/             gem5 Python configs (SE mode)
│   ├── scripts/             Shell wrappers for each stage
│   ├── analysis/            Metric aggregation (DAMOV + roofline)
│   └── gem5-patches/        Patch docs (code lives in gem5-BeSA)
├── analysis/
│   └── comparison/          Cross-benchmark analysis and plots
└── docs/                    BioDynaMo internals documentation
```

## Pipeline overview

The pipeline takes a BioDynaMo benchmark from source to architectural
characterization in eight stages:

| # | Stage | Tool | What it does |
|---|-------|------|-------------|
| 0 | Setup | bash | Install BioDynaMo, gem5, conda env, shim |
| 1 | Build | user | Build the benchmark binary |
| 2 | BBV | Valgrind exp-bbv | Generate basic-block vectors |
| 3 | Trim | awk | Strip JIT startup intervals |
| 4 | Cluster | SimPoint 3.2 | Select representative intervals |
| 5 | Smoke test | gem5 SE | Verify binary runs under gem5 |
| 6 | Checkpoint | gem5 AtomicSimpleCPU | Fast-forward to each SimPoint |
| 7 | Detailed sim | gem5 O3CPU + caches | Cycle-accurate simulation |
| 8 | Aggregate | Python | Weighted metrics, DAMOV class, roofline |

See [pipeline/README.md](pipeline/README.md) for detailed usage.

## Quick start

```bash
# 1. Clone
git clone <repo-url> besa && cd besa

# 2. Set up (once)
bash pipeline/scripts/setup_env.sh

# 3. Configure for a benchmark
cp pipeline/pipeline.env.example pipeline/pipeline.env
# Edit pipeline.env — or start from a benchmark's preset:
#   cat benchmarks/tumor-growth/benchmark.env
vi pipeline/pipeline.env

# 4. Run the full pipeline (or a range of stages)
bash pipeline/scripts/run_pipeline.sh        # all stages
bash pipeline/scripts/run_pipeline.sh 2-4    # BBV through clustering
bash pipeline/scripts/run_pipeline.sh 6-8    # checkpoint through aggregation
```

## Metrics collected

**Roofline analysis:** Arithmetic Intensity (ops/byte from DRAM),
Performance (GOPS/s), DRAM bandwidth (GB/s).

**DAMOV characterization:**
LFMR (LLC misses / L1 misses), LLC MPKI, Arithmetic Intensity
(ops / L1 cache line). Automatic classification into classes
1a/1b/1c/2a/2c.

**Per-SimPoint breakdown:** CPI, IPC, L1D/L1I/L2 hit rates,
full instruction mix (Int ALU/Mult/Div, Float, SIMD, Mem R/W).

## Key findings (epidemiology)

Running the epidemiology use case on a Google Cloud C4 VM
(Intel Xeon Emerald Rapids, 16 vCPUs, 64 GB) with agent counts
from 10M to 200M:

- **IPC ~0.40** across all scales — the core is underutilized
- **Memory-bound fraction ~60%** (top-down analysis) — consistent
  with DAMOV memory-bound classification
- **Per-agent memory cost ~290 bytes** — 64 GB VM limit caps
  population at ~221M agents

## gem5 fork

The pipeline uses [gem5-BeSA](https://github.com/SAL-Research/gem5-BeSA),
a gem5 fork with SE-mode fixes for agent-based modeling workloads. `setup_env.sh` clones
and builds it automatically.