"""
Restore a single SimPoint checkpoint and run 100M instructions with O3CPU
and a realistic cache hierarchy for detailed microarchitectural simulation.

Usage:
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate gem5
    cd ~/tumor_gem5

    # Restore one checkpoint (e.g., SimPoint 0, index 196):
    ~/gem5/build/X86/gem5.opt \
        -d m5out/detail_sp00_idx196 \
        scripts/restore_simpoint.py \
        --checkpoint-dir m5out/cpt.simpoint_00_idx196

    # Or run all 10 in parallel (see run_all_detailed.sh)
"""
import argparse
import os

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.private_l1_private_l2_cache_hierarchy import (
    PrivateL1PrivateL2CacheHierarchy,
)
from gem5.components.memory.single_channel import SingleChannelDDR3_1600
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator
from gem5.utils.requires import requires

requires(isa_required=ISA.X86)

parser = argparse.ArgumentParser()
parser.add_argument("--checkpoint-dir", required=True,
                    help="Path to the checkpoint directory to restore from")
args = parser.parse_args()

INTERVAL_SIZE = 100_000_000  # run exactly one SimPoint interval

BINARY = BinaryResource(
    local_path=os.path.expanduser(
        "~/biodynamo-fork/demo/tumor_concept/build/tumor_concept"
    )
)
CONFIG = os.path.expanduser(
    "~/biodynamo-fork/demo/tumor_concept/tumor_bbv_800.json"
)
BDM_LIB = os.path.expanduser("~/biodynamo-v1.05.153/lib")
ROOT_LIB = os.path.expanduser("~/biodynamo-v1.05.153/third_party/root/lib")
ROOTSYS = os.path.expanduser("~/biodynamo-v1.05.153/third_party/root")
LD_PATH = f"{BDM_LIB}:{ROOT_LIB}"
HOME = os.path.expanduser("~")
BDMSYS = os.path.expanduser("~/biodynamo-v1.05.153")
SHIM = os.path.expanduser("~/tumor_gem5/gem5_system_shim.so")

cache_hierarchy = PrivateL1PrivateL2CacheHierarchy(
    l1d_size="48kB",
    l1i_size="32kB",
    l2_size="2MB",
)

board = SimpleBoard(
    clk_freq="3GHz",
    processor=SimpleProcessor(
        cpu_type=CPUTypes.O3, isa=ISA.X86, num_cores=2
    ),
    memory=SingleChannelDDR3_1600(size="4GiB"),
    cache_hierarchy=cache_hierarchy,
)

board.set_se_binary_workload(
    binary=BINARY,
    arguments=["--config", CONFIG],
    env_list=[
        f"LD_PRELOAD={SHIM}",
        f"LD_LIBRARY_PATH={LD_PATH}",
        f"HOME={HOME}",
        f"ROOTSYS={ROOTSYS}",
        "ROOT_HIST=0",
        "OMP_NUM_THREADS=1",
        "OMP_PROC_BIND=false",
        f"BDMSYS={BDMSYS}",
    ],
)

simulator = Simulator(
    board=board,
    checkpoint_path=args.checkpoint_dir,
)

simulator.schedule_max_insts(INTERVAL_SIZE)
simulator.run()

print(f"Exit cause: {simulator.get_last_exit_event_cause()}")
print(f"Checkpoint: {args.checkpoint_dir}")
print("Stats written to m5out/stats.txt (in the -d output directory)")
