# Stage 0: Set up a fresh VM with BioDynaMo, gem5-BeSA, and all dependencies.
# Usage:
#   ssh $VM_NAME 'bash pipeline/scripts/setup_env.sh'
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/../pipeline.env"

echo "=== [1/5] System prerequisites ===" >&2
sudo apt-get update -qq
sudo apt-get install -y -qq valgrind build-essential git

echo "=== [2/5] Installing BioDynaMo ===" >&2
export BDM_INSTALL=master
export SILENT_INSTALL=1
export DEBIAN_FRONTEND=noninteractive
if [[ ! -d "${BDM_INSTALL_DIR}" ]]; then
    curl -sSL https://biodynamo.github.io/install | bash
fi

shopt -s nullglob
BDM_CANDIDATES=("${HOME}"/biodynamo-v*/)
shopt -u nullglob
if [[ ${#BDM_CANDIDATES[@]} -eq 0 ]]; then
    echo "ERROR: No BioDynaMo found at ~/biodynamo-v*/" >&2
    exit 1
fi
BDM_DIR=$(printf '%s\n' "${BDM_CANDIDATES[@]}" | sort -V | tail -1)
BDM_DIR="${BDM_DIR%/}"
echo "    BioDynaMo: ${BDM_DIR}" >&2

set +u
source "${BDM_DIR}/bin/thisbdm.sh"
set -u

echo "=== [3/5] Installing conda + gem5 build env ===" >&2
if [[ ! -d "${HOME}/miniforge3" ]]; then
    wget -q https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
    bash Miniforge3-Linux-x86_64.sh -b -p "${HOME}/miniforge3"
    rm Miniforge3-Linux-x86_64.sh
fi
source "${HOME}/miniforge3/etc/profile.d/conda.sh"

if ! conda env list | grep -q "^gem5 "; then
    conda create -n gem5 -y python=3.11 scons gcc=13 gxx=13 m4 zlib libprotobuf=3.21.* libpng
fi
conda activate gem5

echo "=== [4/5] Building gem5-BeSA (includes SE-mode patches + shim) ===" >&2
if [[ ! -d "${GEM5_DIR}" ]]; then
    git clone https://github.com/SAL-Research/gem5-BeSA.git "${GEM5_DIR}"
fi

if [[ ! -f "${GEM5_BIN}" ]]; then
    bash "${GEM5_DIR}/util/abm/build_gem5.sh" "${GEM5_ISA}" -j"$(nproc)"
fi

GEM5_SHIM="${GEM5_DIR}/gem5-patches/gem5_system_shim.so"
if [[ ! -f "${GEM5_SHIM}" ]]; then
    echo "ERROR: Shim not built. Expected at ${GEM5_SHIM}" >&2
    exit 1
fi
echo "    gem5:  ${GEM5_BIN}" >&2
echo "    shim:  ${GEM5_SHIM}" >&2

echo "=== [5/5] Cloning fork and building benchmark ===" >&2
if [[ ! -d "${BDM_FORK_DIR}" ]]; then
    git clone https://github.com/aminatpwk/biodynamo.git "${BDM_FORK_DIR}"
fi

cd "${BDM_FORK_DIR}/${BENCHMARK_DEMO_DIR}"
biodynamo build

BINARY="${BDM_FORK_DIR}/${BINARY_REL}"
if [[ ! -x "${BINARY}" ]]; then
    echo "ERROR: Binary not found: ${BINARY}" >&2
    exit 1
fi
echo "    Binary: ${BINARY}" >&2

mkdir -p "${WORK_DIR}"
echo "" >&2
echo "Setup complete. Run the pipeline with:" >&2
echo "  bash pipeline/scripts/run_pipeline.sh" >&2
