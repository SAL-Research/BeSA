"""
Stage 7: Restore a single SimPoint checkpoint for detailed simulation.
Runs O3CPU with realistic cache hierarchy (L1d + L1i + L2) for exactly
one SimPoint interval.
Usage:
    ~/gem5/build/X86/gem5.opt -d m5out/detail_sp00_idx196 \
        configs/restore_simpoint.py --checkpoint-dir m5out/cpt.simpoint_00_idx196
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gem5_common import *

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
parser.add_argument("--checkpoint-dir", required=True)
args = parser.parse_args()

cache_hierarchy = PrivateL1PrivateL2CacheHierarchy(
    l1d_size=L1D_SIZE,
    l1i_size=L1I_SIZE,
    l2_size=L2_SIZE,
)

board = SimpleBoard(
    clk_freq=CLK_FREQ,
    processor=SimpleProcessor(
        cpu_type=CPUTypes.O3, isa=ISA.X86, num_cores=NUM_CORES
    ),
    memory=SingleChannelDDR3_1600(size=MEM_SIZE),
    cache_hierarchy=cache_hierarchy,
)

board.set_se_binary_workload(
    binary=BinaryResource(local_path=BINARY_PATH),
    arguments=["--config", CONFIG_PATH],
    env_list=env_list(),
)

simulator = Simulator(
    board=board,
    checkpoint_path=args.checkpoint_dir,
)

simulator.schedule_max_insts(INTERVAL_SIZE)
simulator.run()

print(f"Exit cause: {simulator.get_last_exit_event_cause()}")
print(f"Checkpoint: {args.checkpoint_dir}")
print("Stats written to stats.txt in the -d output directory.")
