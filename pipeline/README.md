# SimPoint + gem5 Pipeline for BioDynaMo Agent-Based Models

End-to-end pipeline: BBV generation, SimPoint clustering, gem5 SE-mode
checkpoint/restore, weighted metric aggregation, roofline analysis, and
DAMOV-methodology characterization.

Uses [gem5-BeSA](https://github.com/SAL-Research/gem5-BeSA), a gem5 fork
with SE-mode fixes for agent-based modeling workloads.

## Pipeline stages

| Stage | Script | Input | Output |
|-------|--------|-------|--------|
| 0. Setup | `scripts/setup_env.sh` | Fresh setup | BioDynaMo + gem5 + conda env |
| 1. Build | `scripts/build_benchmark.sh` | Source + config | Static binary + `gem5_system_shim.so` |
| 2. BBV | `scripts/generate_bbv.sh` | Binary + config | `.bb` + `.pc` files |
| 3. Trim | `scripts/trim_bbv.sh` | Raw `.bb` | Trimmed `.bb` (JIT startup removed) |
| 4. Cluster | `scripts/run_simpoint.sh` | Trimmed `.bb` | `.simpts` + `.weights` |
| 5. Smoke test | `scripts/smoke_test.sh` | Binary + gem5 | Pass/fail at 1B instructions |
| 6. Checkpoint | `scripts/checkpoint_pass.sh` | Binary + SimPoints | `m5out/cpt.simpoint_*` |
| 7. Detailed sim | `scripts/detailed_pass.sh` | Checkpoints | `m5out/detail_sp*/stats.txt` |
| 8. Aggregate | `scripts/aggregate.sh` | stats.txt + weights | CSV + JSON + DAMOV class |

## Quick start

```bash
# 1. Set up (once — clones gem5-BeSA + BioDynaMo, builds everything)
bash pipeline/scripts/setup_env.sh

# 2. Configure your benchmark (edit pipeline.env)
cp pipeline/pipeline.env.example pipeline/pipeline.env
vi pipeline/pipeline.env

# 3. Run all stages
bash pipeline/scripts/run_pipeline.sh
```

## Metrics collected

### For Roofline Analysis
- Arithmetic Intensity (ops/byte from DRAM)
- Performance (GOPS/s)
- DRAM bandwidth (GB/s)

### For DAMOV Characterization
- LFMR (Last-to-First Miss Ratio = LLC misses / L1 misses)
- LLC MPKI (L2 misses per kilo-instruction)
- Arithmetic Intensity (ops per L1 cache line accessed)
- Automatic bottleneck classification (1a/1b/1c/2a/2c)

### Additional
- CPI, IPC, L1D/L1I/L2 hit rates
- Full instruction mix (Int ALU/Mult/Div, Float, SIMD, Mem R/W)
