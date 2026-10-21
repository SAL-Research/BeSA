# Stage 5: Run gem5 smoke test — verify the binary runs under gem5 SE mode.
# Usage:
#   bash pipeline/scripts/smoke_test.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../pipeline.env"

source "${HOME}/miniforge3/etc/profile.d/conda.sh"
conda activate gem5

export INTERVAL_SIZE BDM_INSTALL_DIR BDM_FORK_DIR BINARY_REL CONFIG_REL
export WORK_DIR GEM5_DIR GEM5_NUM_CORES GEM5_CLK_FREQ GEM5_MEM_SIZE
export GEM5_ENV_ROOT_HIST GEM5_ENV_OMP_NUM_THREADS GEM5_ENV_OMP_PROC_BIND
export SMOKE_TEST_INSTS

mkdir -p "${WORK_DIR}/m5out"

echo "=== gem5 Smoke Test ===" >&2
echo "  Binary:       ${BDM_FORK_DIR}/${BINARY_REL}" >&2
echo "  Instructions: ${SMOKE_TEST_INSTS}" >&2

cd "${WORK_DIR}"
"${GEM5_BIN}" \
    -d m5out/smoke_test \
    "${SCRIPT_DIR}/../configs/smoke_test.py"

echo "" >&2
echo "Smoke test complete. Check m5out/smoke_test/stats.txt for results." >&2
