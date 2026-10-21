"""
gem5 SE-mode smoke test for BioDynaMo tumor_concept (800 iterations).
Usage (on the benchmark server):
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate gem5
    cd ~/tumor_gem5
    ~/gem5/build/X86/gem5.opt scripts/smoke_test.py
"""
import os

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

board = SimpleBoard(
    clk_freq="3GHz",
    processor=SimpleProcessor(
        cpu_type=CPUTypes.ATOMIC, isa=ISA.X86, num_cores=2
    ),
    memory=SingleChannelDDR3_1600(size="4GiB"),
    cache_hierarchy=NoCache(),
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

simulator = Simulator(board=board)
simulator.schedule_max_insts(500_000_000)
simulator.run()

print(f"Exit cause: {simulator.get_last_exit_event_cause()}")
