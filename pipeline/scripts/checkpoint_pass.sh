#!/usr/bin/env bash
# Stage 6: Run the SimPoint checkpoint pass.
#
# Fast-forwards with AtomicSimpleCPU to each SimPoint and takes a checkpoint.
# Runs in the background with nohup by default.
#
# Usage:
#   bash pipeline/scripts/checkpoint_pass.sh           # background (nohup)
#   bash pipeline/scripts/checkpoint_pass.sh foreground # foreground
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../pipeline.env"

source "${HOME}/miniforge3/etc/profile.d/conda.sh"
conda activate gem5

export INTERVAL_SIZE BENCHMARK_NAME BDM_INSTALL_DIR BDM_FORK_DIR BINARY_REL
export CONFIG_REL WORK_DIR GEM5_DIR GEM5_NUM_CORES GEM5_CLK_FREQ GEM5_MEM_SIZE
export GEM5_ENV_ROOT_HIST GEM5_ENV_OMP_NUM_THREADS GEM5_ENV_OMP_PROC_BIND

mkdir -p "${WORK_DIR}/m5out"
cd "${WORK_DIR}"

LOG="${WORK_DIR}/checkpoint_pass.log"

echo "=== SimPoint Checkpoint Pass ===" >&2
echo "  Work dir: ${WORK_DIR}" >&2
echo "  Log:      ${LOG}" >&2

if [[ "${1:-}" == "foreground" ]]; then
    "${GEM5_BIN}" "${SCRIPT_DIR}/../configs/checkpoint_simpoints.py" 2>&1 | tee "${LOG}"
else
    echo "  Running in background with nohup..." >&2
    nohup "${GEM5_BIN}" \
        "${SCRIPT_DIR}/../configs/checkpoint_simpoints.py" \
        > "${LOG}" 2>&1 &
    PID=$!
    echo "  PID: ${PID}" >&2
    echo "${PID}" > "${WORK_DIR}/checkpoint_pass.pid"
    echo "" >&2
    echo "Monitor with:  tail -f ${LOG}" >&2
    echo "Check status:  ps -p ${PID}" >&2
fi
