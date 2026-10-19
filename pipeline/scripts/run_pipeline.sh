#!/usr/bin/env bash
# Master orchestrator: run all pipeline stages end-to-end.
#
# Stages:
#   0  setup_env      — install BioDynaMo, gem5, conda env, shim
#   1  build          — build the benchmark binary (user-provided)
#   2  generate_bbv   — Valgrind exp-bbv BBV generation
#   3  trim_bbv       — strip JIT startup intervals
#   4  run_simpoint   — SimPoint clustering + original index mapping
#   5  smoke_test     — quick gem5 SE-mode sanity check
#   6  checkpoint     — AtomicSimpleCPU fast-forward to each SimPoint
#   7  detailed       — O3CPU + caches detailed simulation per SimPoint
#   8  aggregate      — weighted metric aggregation + DAMOV/roofline
#
# Usage:
#   bash pipeline/scripts/run_pipeline.sh                # all stages
#   bash pipeline/scripts/run_pipeline.sh 2-4            # stages 2 through 4
#   bash pipeline/scripts/run_pipeline.sh 6              # single stage
#   bash pipeline/scripts/run_pipeline.sh 6-8            # stages 6 through 8
#   bash pipeline/scripts/run_pipeline.sh --from 5       # stages 5 onward
#
# The pipeline.env file must exist before running.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PIPELINE_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ ! -f "${PIPELINE_DIR}/pipeline.env" ]]; then
    echo "ERROR: ${PIPELINE_DIR}/pipeline.env not found." >&2
    echo "Copy pipeline.env.example and fill in your values." >&2
    exit 1
fi

source "${PIPELINE_DIR}/pipeline.env"

STAGE_NAMES=(
    "setup_env"
    "build"
    "generate_bbv"
    "trim_bbv"
    "run_simpoint"
    "smoke_test"
    "checkpoint_pass"
    "detailed_pass"
    "aggregate"
)

run_stage() {
    local num=$1
    local name="${STAGE_NAMES[$num]}"
    local script="${SCRIPT_DIR}/${name}.sh"

    echo ""
    echo "================================================================"
    echo "  STAGE ${num}: ${name}"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "================================================================"

    if [[ "$num" -eq 1 ]]; then
        echo "Stage 1 (build) is benchmark-specific."
        echo "Build your binary and set BINARY_REL in pipeline.env."
        echo "Skipping."
        return 0
    fi

    if [[ ! -f "$script" ]]; then
        echo "WARNING: ${script} not found, skipping." >&2
        return 0
    fi

    local start_ts
    start_ts=$(date +%s)
    bash "$script"
    local end_ts
    end_ts=$(date +%s)
    local elapsed=$(( end_ts - start_ts ))
    echo ""
    echo "  Stage ${num} (${name}) completed in ${elapsed}s"
}

# Parse stage range
START=0
END=8

if [[ $# -ge 1 ]]; then
    arg="$1"
    if [[ "$arg" == "--from" ]]; then
        START="${2:?Missing stage number after --from}"
        END=8
    elif [[ "$arg" =~ ^([0-8])-([0-8])$ ]]; then
        START="${BASH_REMATCH[1]}"
        END="${BASH_REMATCH[2]}"
    elif [[ "$arg" =~ ^[0-8]$ ]]; then
        START="$arg"
        END="$arg"
    else
        echo "Usage: $0 [stage|start-end|--from stage]" >&2
        exit 1
    fi
fi

echo "================================================================"
echo "  SimPoint Pipeline — Stages ${START} to ${END}"
echo "  Benchmark: ${BENCHMARK_NAME}"
echo "  Work dir:  ${WORK_DIR}"
echo "  Started:   $(date '+%Y-%m-%d %H:%M:%S')"
echo "================================================================"

pipeline_start=$(date +%s)

for stage in $(seq "$START" "$END"); do
    run_stage "$stage"
done

pipeline_end=$(date +%s)
total=$(( pipeline_end - pipeline_start ))
hours=$(( total / 3600 ))
mins=$(( (total % 3600) / 60 ))

echo ""
echo "================================================================"
echo "  Pipeline complete."
echo "  Total time: ${hours}h ${mins}m (${total}s)"
echo "  Results:    ${WORK_DIR}/results/processed/"
echo "================================================================"
