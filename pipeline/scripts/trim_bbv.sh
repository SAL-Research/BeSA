#!/usr/bin/env bash
# Stage 3: Trim JIT startup intervals from the BBV file.
#
# ROOT/cling JIT compilation produces a fixed number of startup intervals
# that are identical across all runs regardless of workload parameters.
# These must be removed before SimPoint clustering.
#
# Usage:
#   bash pipeline/scripts/trim_bbv.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../pipeline.env"

BBV_DIR="${WORK_DIR}/sampling/bbv"
BB_IN="${BBV_DIR}/${BENCHMARK_NAME}_bbv.bb"
BB_OUT="${BBV_DIR}/${BENCHMARK_NAME}_bbv_trimmed.bb"

if [[ "${TRIM_INTERVALS}" -eq 0 ]]; then
    echo "TRIM_INTERVALS=0, skipping trim (copying as-is)." >&2
    cp "${BB_IN}" "${BB_OUT}"
    exit 0
fi

if [[ ! -f "${BB_IN}" ]]; then
    echo "ERROR: BBV file not found: ${BB_IN}" >&2
    exit 1
fi

TOTAL_BEFORE=$(grep -c '^T' "${BB_IN}")
echo "Trimming first ${TRIM_INTERVALS} intervals from ${BB_IN}" >&2
echo "  Intervals before trim: ${TOTAL_BEFORE}" >&2

# Each interval starts with a line "T" — skip the first TRIM_INTERVALS blocks.
# A "T" line marks the start of each interval block.
awk -v skip="${TRIM_INTERVALS}" '
    /^T/ { count++ }
    count > skip { print }
' "${BB_IN}" > "${BB_OUT}"

TOTAL_AFTER=$(grep -c '^T' "${BB_OUT}")
echo "  Intervals after trim:  ${TOTAL_AFTER}" >&2
echo "  Trim offset recorded:  ${TRIM_INTERVALS}" >&2
echo "${TRIM_INTERVALS}" > "${BBV_DIR}/trim_offset.txt"
