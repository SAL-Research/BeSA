"""
Stage 5: gem5 SE-mode smoke test.
Runs AtomicSimpleCPU with no caches to verify the binary boots and enters
the simulation loop under gem5.
Usage:
    export SMOKE_TEST_INSTS=1000000000
    ~/gem5/build/X86/gem5.opt configs/smoke_test.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gem5_common import *

from gem5.components.boards.simple_board import SimpleBoard
from gem5.components.cachehierarchies.classic.no_cache import NoCache
from gem5.components.memory.single_channel import SingleChannelDDR3_1600
from gem5.components.processors.cpu_types import CPUTypes
from gem5.components.processors.simple_processor import SimpleProcessor
from gem5.isas import ISA
from gem5.resources.resource import BinaryResource
from gem5.simulate.simulator import Simulator
from gem5.utils.requires import requires

requires(isa_required=ISA.X86)

MAX_INSTS = int(os.environ.get("SMOKE_TEST_INSTS", 1_000_000_000))

board = SimpleBoard(
    clk_freq=CLK_FREQ,
    processor=SimpleProcessor(
        cpu_type=CPUTypes.ATOMIC, isa=ISA.X86, num_cores=NUM_CORES
    ),
    memory=SingleChannelDDR3_1600(size=MEM_SIZE),
    cache_hierarchy=NoCache(),
)

board.set_se_binary_workload(
    binary=BinaryResource(local_path=BINARY_PATH),
    arguments=["--config", CONFIG_PATH],
    env_list=env_list(),
)

simulator = Simulator(board=board)
simulator.schedule_max_insts(MAX_INSTS)
simulator.run()

cause = simulator.get_last_exit_event_cause()
print(f"Exit cause: {cause}")
if "max inst" in cause.lower():
    print(f"PASS: Reached {MAX_INSTS:,} instructions successfully.")
else:
    print(f"FAIL: Unexpected exit at < {MAX_INSTS:,} instructions.")
    sys.exit(1)
