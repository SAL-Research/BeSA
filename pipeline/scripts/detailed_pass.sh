# Stage 7: Run all detailed SimPoint simulations (O3CPU + caches).
# Each restores from a checkpoint and simulates one interval (100M instructions).
# Usage:
#   bash pipeline/scripts/detailed_pass.sh              
#   bash pipeline/scripts/detailed_pass.sh parallel      
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../pipeline.env"

source "${HOME}/miniforge3/etc/profile.d/conda.sh"
conda activate gem5

export INTERVAL_SIZE BDM_INSTALL_DIR BDM_FORK_DIR BINARY_REL CONFIG_REL
export WORK_DIR GEM5_DIR GEM5_NUM_CORES GEM5_CLK_FREQ GEM5_MEM_SIZE
export GEM5_L1D_SIZE GEM5_L1I_SIZE GEM5_L2_SIZE
export GEM5_ENV_ROOT_HIST GEM5_ENV_OMP_NUM_THREADS GEM5_ENV_OMP_PROC_BIND

cd "${WORK_DIR}"
CPT_BASE="${WORK_DIR}/m5out"
RESTORE_SCRIPT="${SCRIPT_DIR}/../configs/restore_simpoint.py"

CHECKPOINTS=()
for cpt_dir in "${CPT_BASE}"/cpt.simpoint_*; do
    if [[ -d "$cpt_dir" ]]; then
        CHECKPOINTS+=("$cpt_dir")
    fi
done

if [[ ${#CHECKPOINTS[@]} -eq 0 ]]; then
    echo "ERROR: No checkpoints found in ${CPT_BASE}/" >&2
    echo "Run checkpoint_pass.sh first." >&2
    exit 1
fi

echo "=== Detailed SimPoint Simulations ===" >&2
echo "  Found ${#CHECKPOINTS[@]} checkpoints" >&2
echo "  CPU: O3, Caches: L1d=${GEM5_L1D_SIZE} L1i=${GEM5_L1I_SIZE} L2=${GEM5_L2_SIZE}" >&2
echo "  Instructions per SimPoint: ${INTERVAL_SIZE}" >&2

run_one() {
    local cpt_dir="$1"
    local basename
    basename=$(basename "$cpt_dir")
    # cpt.simpoint_00_idx196 -> detail_sp00_idx196
    local sp_tag="${basename#cpt.simpoint_}"
    local out_dir="${CPT_BASE}/detail_sp${sp_tag}"

    echo "[${sp_tag}] Restoring from ${cpt_dir}" >&2
    "${GEM5_BIN}" -d "$out_dir" "$RESTORE_SCRIPT" --checkpoint-dir "$cpt_dir"
    echo "[${sp_tag}] Done. Stats: ${out_dir}/stats.txt" >&2
}

if [[ "${1:-}" == "parallel" ]]; then
    echo "  Running all ${#CHECKPOINTS[@]} in parallel..." >&2
    pids=()
    for cpt_dir in "${CHECKPOINTS[@]}"; do
        run_one "$cpt_dir" &
        pids+=($!)
    done
    echo "  Waiting for ${#pids[@]} jobs..." >&2
    for pid in "${pids[@]}"; do
        wait "$pid"
    done
else
    echo "  Running sequentially..." >&2
    for cpt_dir in "${CHECKPOINTS[@]}"; do
        run_one "$cpt_dir"
    done
fi

echo "" >&2
echo "All detailed simulations complete." >&2
echo "Run aggregate.sh to compute weighted metrics." >&2
