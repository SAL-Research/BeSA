"""
Shared configuration for all gem5 SE-mode scripts.

Reads paths and parameters from environment variables set by the pipeline
shell scripts, with sensible defaults for standalone use.
"""
import os

INTERVAL_SIZE = int(os.environ.get("INTERVAL_SIZE", 100_000_000))

BDM_INSTALL = os.path.expanduser(
    os.environ.get("BDM_INSTALL_DIR", "~/biodynamo-v1.05.153")
)
BDM_FORK = os.path.expanduser(
    os.environ.get("BDM_FORK_DIR", "~/biodynamo-fork")
)

BINARY_REL = os.environ.get("BINARY_REL", "demo/tumor_concept/build/tumor_concept")
CONFIG_REL = os.environ.get("CONFIG_REL", "demo/tumor_concept/tumor_bbv_800.json")

BINARY_PATH = os.path.join(BDM_FORK, BINARY_REL)
CONFIG_PATH = os.path.join(BDM_FORK, CONFIG_REL)

BDM_LIB = os.path.join(BDM_INSTALL, "lib")
ROOT_LIB = os.path.join(BDM_INSTALL, "third_party/root/lib")
ROOTSYS = os.path.join(BDM_INSTALL, "third_party/root")
LD_PATH = f"{BDM_LIB}:{ROOT_LIB}"
HOME = os.path.expanduser("~")
BDMSYS = BDM_INSTALL

WORK_DIR = os.path.expanduser(
    os.environ.get("WORK_DIR", f"~/{os.path.basename(BINARY_REL)}_gem5")
)
GEM5_DIR = os.path.expanduser(os.environ.get("GEM5_DIR", "~/gem5"))
SHIM = os.path.join(GEM5_DIR, "gem5-patches", "gem5_system_shim.so")

NUM_CORES = int(os.environ.get("GEM5_NUM_CORES", 2))
CLK_FREQ = os.environ.get("GEM5_CLK_FREQ", "3GHz")
L1D_SIZE = os.environ.get("GEM5_L1D_SIZE", "48kB")
L1I_SIZE = os.environ.get("GEM5_L1I_SIZE", "32kB")
L2_SIZE = os.environ.get("GEM5_L2_SIZE", "2MB")
MEM_SIZE = os.environ.get("GEM5_MEM_SIZE", "4GiB")


def env_list():
    """Environment variables for the simulated process."""
    return [
        f"LD_PRELOAD={SHIM}",
        f"LD_LIBRARY_PATH={LD_PATH}",
        f"HOME={HOME}",
        f"ROOTSYS={ROOTSYS}",
        f"BDMSYS={BDMSYS}",
        f"ROOT_HIST={os.environ.get('GEM5_ENV_ROOT_HIST', '0')}",
        f"OMP_NUM_THREADS={os.environ.get('GEM5_ENV_OMP_NUM_THREADS', '1')}",
        f"OMP_PROC_BIND={os.environ.get('GEM5_ENV_OMP_PROC_BIND', 'false')}",
    ]
