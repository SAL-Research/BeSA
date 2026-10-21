# Stage 4: Run SimPoint clustering on the trimmed BBV file.
# Outputs .simpts and .weights files, plus a mapping to original indices
# Usage:
#   bash pipeline/scripts/run_simpoint.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../pipeline.env"

BBV_DIR="${WORK_DIR}/sampling/bbv"
SP_DIR="${WORK_DIR}/sampling/simpoints"
mkdir -p "${SP_DIR}"

BB_TRIMMED="${BBV_DIR}/${BENCHMARK_NAME}_bbv_trimmed.bb"
if [[ ! -f "${BB_TRIMMED}" ]]; then
    echo "ERROR: Trimmed BBV not found: ${BB_TRIMMED}" >&2
    echo "Run trim_bbv.sh first." >&2
    exit 1
fi

# SimPoint may need large stack for big BBV files
ulimit -s unlimited 2>/dev/null || true

echo "=== Running SimPoint ===" >&2
echo "  Input:     ${BB_TRIMMED}" >&2
echo "  maxK:      ${SIMPOINT_MAX_K}" >&2
echo "  dim:       ${SIMPOINT_DIM}" >&2

"${SIMPOINT_BIN}" \
    -loadFVFile "${BB_TRIMMED}" \
    -maxK "${SIMPOINT_MAX_K}" \
    -numInitSeeds "${SIMPOINT_NUM_SEEDS}" \
    -dim "${SIMPOINT_DIM}" \
    -saveSimpoints "${SP_DIR}/${BENCHMARK_NAME}.simpts" \
    -saveSimpointWeights "${SP_DIR}/${BENCHMARK_NAME}.weights" \
    -saveLabels "${SP_DIR}/${BENCHMARK_NAME}.labels" \
    -saveVectorWeights "${SP_DIR}/${BENCHMARK_NAME}.vecweights" \
    2>&1 | tee "${SP_DIR}/simpoint.log"

# Convert trimmed indices to original indices
TRIM_OFFSET=0
if [[ -f "${BBV_DIR}/trim_offset.txt" ]]; then
    TRIM_OFFSET=$(cat "${BBV_DIR}/trim_offset.txt")
fi

echo "" >&2
echo "=== SimPoint Results ===" >&2
echo "  Trim offset: ${TRIM_OFFSET}" >&2
echo "" >&2

python3 -c "
import sys
offset = ${TRIM_OFFSET}
simpts = []
with open('${SP_DIR}/${BENCHMARK_NAME}.simpts') as f:
    for line in f:
        parts = line.split()
        if len(parts) >= 2:
            idx, cluster = int(parts[0]), int(parts[1])
            simpts.append((idx, cluster, idx + offset))

weights = {}
with open('${SP_DIR}/${BENCHMARK_NAME}.weights') as f:
    for line in f:
        parts = line.split()
        if len(parts) >= 2:
            weights[int(parts[1])] = float(parts[0])

# Write original-index mapping
with open('${SP_DIR}/${BENCHMARK_NAME}_original.simpts', 'w') as f:
    for idx, cluster, orig in sorted(simpts, key=lambda x: x[2]):
        f.write(f'{orig} {cluster}\n')

# Write combined summary
print(f'  {\"Cluster\":>8} {\"Trimmed\":>10} {\"Original\":>10} {\"Weight\":>10}')
print(f'  {\"-\"*8:>8} {\"-\"*10:>10} {\"-\"*10:>10} {\"-\"*10:>10}')
for idx, cluster, orig in sorted(simpts, key=lambda x: x[2]):
    w = weights.get(cluster, 0)
    print(f'  {cluster:>8} {idx:>10} {orig:>10} {w:>10.5f}')

total_w = sum(weights.values())
print(f'\n  Total weight: {total_w:.6f}')
print(f'  Clusters:     {len(simpts)}')
"

echo "" >&2
echo "SimPoint complete. Results in ${SP_DIR}/" >&2
