#!/usr/bin/env bash
# Run all 10 SimPoint detailed simulations (O3CPU + caches).
# Each restores from a checkpoint and simulates 100M instructions.
#
# Usage:
#   source ~/miniforge3/etc/profile.d/conda.sh && conda activate gem5
#   cd ~/tumor_gem5
#   bash scripts/run_all_detailed.sh          # sequential
#   bash scripts/run_all_detailed.sh parallel  # all 10 in background
set -euo pipefail

GEM5=~/gem5/build/X86/gem5.opt
SCRIPT=scripts/restore_simpoint.py
CPT_BASE=m5out

SIMPOINTS=(
    "00 196"
    "01 250"
    "02 457"
    "03 479"
    "04 1393"
    "05 2588"
    "06 5275"
    "07 11764"
    "08 12158"
    "09 22871"
)

run_one() {
    local sp_num=$1 sp_idx=$2
    local cpt_dir="${CPT_BASE}/cpt.simpoint_${sp_num}_idx${sp_idx}"
    local out_dir="${CPT_BASE}/detail_sp${sp_num}_idx${sp_idx}"

    if [ ! -d "$cpt_dir" ]; then
        echo "ERROR: Checkpoint not found: $cpt_dir"
        return 1
    fi

    echo "[SP ${sp_num}] Restoring from ${cpt_dir} -> ${out_dir}"
    $GEM5 -d "$out_dir" "$SCRIPT" --checkpoint-dir "$cpt_dir"
    echo "[SP ${sp_num}] Done."
}

if [ "${1:-}" = "parallel" ]; then
    echo "Running all 10 SimPoints in parallel..."
    pids=()
    for entry in "${SIMPOINTS[@]}"; do
        read -r sp_num sp_idx <<< "$entry"
        run_one "$sp_num" "$sp_idx" &
        pids+=($!)
    done
    echo "Waiting for ${#pids[@]} jobs..."
    for pid in "${pids[@]}"; do
        wait "$pid"
    done
    echo "All detailed simulations complete."
else
    echo "Running all 10 SimPoints sequentially..."
    for entry in "${SIMPOINTS[@]}"; do
        read -r sp_num sp_idx <<< "$entry"
        run_one "$sp_num" "$sp_idx"
    done
    echo "All detailed simulations complete."
fi
