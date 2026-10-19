#!/usr/bin/env bash
# Stage 2: Generate Basic Block Vectors using Valgrind exp-bbv.
#
# Usage:
#   bash pipeline/scripts/generate_bbv.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../pipeline.env"

BINARY="${BDM_FORK_DIR}/${BINARY_REL}"
CONFIG="${BDM_FORK_DIR}/${CONFIG_REL}"
BBV_DIR="${WORK_DIR}/sampling/bbv"
mkdir -p "${BBV_DIR}"

BB_OUT="${BBV_DIR}/${BENCHMARK_NAME}_bbv.bb"
PC_OUT="${BBV_DIR}/${BENCHMARK_NAME}_bbv.pc"

echo "=== Generating BBV ===" >&2
echo "  Binary:    ${BINARY}" >&2
echo "  Config:    ${CONFIG}" >&2
echo "  Interval:  ${INTERVAL_SIZE}" >&2
echo "  Output:    ${BB_OUT}" >&2

set +u
source "${BDM_INSTALL_DIR}/bin/thisbdm.sh"
set -u

OMP_NUM_THREADS=${OMP_THREADS} \
valgrind --tool=exp-bbv \
    --interval-size="${INTERVAL_SIZE}" \
    --bb-out-file="${BB_OUT}" \
    --pc-out-file="${PC_OUT}" \
    "${BINARY}" --config "${CONFIG}" \
    2>&1 | tee "${BBV_DIR}/valgrind.log"

TOTAL_INTERVALS=$(grep -c '^T' "${BB_OUT}" || true)
echo "" >&2
echo "BBV generation complete." >&2
echo "  Total intervals: ${TOTAL_INTERVALS}" >&2
echo "  Total instructions: ~$((TOTAL_INTERVALS * INTERVAL_SIZE / 1000000000))B" >&2
echo "${TOTAL_INTERVALS}" > "${BBV_DIR}/total_intervals.txt"
