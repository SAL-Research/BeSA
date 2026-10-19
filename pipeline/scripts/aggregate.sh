#!/usr/bin/env bash
# Stage 8: Aggregate weighted metrics from detailed SimPoint runs.
#
# Produces:
#   - Console summary with DAMOV classification
#   - CSV in results/processed/
#   - JSON in results/processed/
#
# Usage:
#   bash pipeline/scripts/aggregate.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../pipeline.env"

RESULTS_DIR="${WORK_DIR}/results"
mkdir -p "${RESULTS_DIR}/raw" "${RESULTS_DIR}/processed"

# Copy raw stats.txt files
for detail_dir in "${WORK_DIR}/m5out"/detail_sp*; do
    if [[ -d "$detail_dir" ]]; then
        basename=$(basename "$detail_dir")
        mkdir -p "${RESULTS_DIR}/raw/${basename}"
        cp "${detail_dir}/stats.txt" "${RESULTS_DIR}/raw/${basename}/" 2>/dev/null || true
        cp "${detail_dir}/config.json" "${RESULTS_DIR}/raw/${basename}/" 2>/dev/null || true
    fi
done

echo "=== Aggregating Metrics ===" >&2

# Run the aggregation script
python3 "${SCRIPT_DIR}/../analysis/aggregate_metrics.py" "${WORK_DIR}/m5out"

# Also produce CSV
python3 "${SCRIPT_DIR}/../analysis/aggregate_metrics.py" "${WORK_DIR}/m5out" --csv \
    > "${RESULTS_DIR}/processed/simpoint_metrics.csv"

# Copy JSON
if [[ -f "${WORK_DIR}/m5out/simpoint_metrics.json" ]]; then
    cp "${WORK_DIR}/m5out/simpoint_metrics.json" "${RESULTS_DIR}/processed/"
fi

echo "" >&2
echo "Results written to:" >&2
echo "  CSV:  ${RESULTS_DIR}/processed/simpoint_metrics.csv" >&2
echo "  JSON: ${RESULTS_DIR}/processed/simpoint_metrics.json" >&2

# Run discovery pass to check DRAM stat names
echo "" >&2
echo "=== DRAM stat discovery (verify stat names match) ===" >&2
python3 "${SCRIPT_DIR}/../analysis/aggregate_metrics.py" "${WORK_DIR}/m5out" --discover 2>&1 \
    | grep -i "dram\|bytes\|mem_ctrl" | head -20 || true
