"""
SimPoint checkpoint pass for BioDynaMo tumor_concept (800 iterations).

Runs AtomicSimpleCPU (fast, no caches) and takes a checkpoint at each of
the 10 SimPoint intervals. The checkpoints are saved under m5out/cpt.*
and will be restored later with O3CPU for detailed simulation.

SimPoint data (original indices, i.e. trimmed_index + 160):
  Index  Weight      Instruction offset (index * 100M)
  196    0.00242     19,600,000,000
  250    0.00238     25,000,000,000
  457    0.01419     45,700,000,000
  479    0.00657     47,900,000,000
  1393   0.06718     139,300,000,000
  2588   0.00343     258,800,000,000
  5275   0.21891     527,500,000,000
  11764  0.00206     1,176,400,000,000
  12158  0.42528     1,215,800,000,000
  22871  0.25760     2,287,100,000,000

Strategy: single ascending-order run. Schedule max_insts exit events at
each SimPoint offset, take checkpoint, continue to next.

Usage:
    source ~/miniforge3/etc/profile.d/conda.sh && conda activate gem5
    cd ~/tumor_gem5
    ~/gem5/build/X86/gem5.opt scripts/checkpoint_simpoints.py
"""
import os
import m5
from m5.objects import *

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

INTERVAL_SIZE = 100_000_000  # 100M instructions per interval

SIMPOINTS = [
    (196,   0.00241799),
    (250,   0.00237769),
    (457,   0.01418550),
    (479,   0.00656887),
    (1393,  0.06717980),
    (2588,  0.00342549),
    (5275,  0.21890900),
    (11764, 0.00205529),
    (12158, 0.42528400),
    (22871, 0.25759700),
]

SIMPOINTS.sort(key=lambda x: x[0])

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

instructions_so_far = 0

for i, (sp_index, weight) in enumerate(SIMPOINTS):
    target = sp_index * INTERVAL_SIZE
    delta = target - instructions_so_far

    if delta <= 0:
        print(f"[SP {i}] index={sp_index} target={target:,} -- "
              f"already past this point ({instructions_so_far:,}), skipping")
        continue

    print(f"[SP {i}] index={sp_index} weight={weight:.5f} "
          f"fast-forwarding {delta:,} instructions to {target:,} ...")

    simulator.schedule_max_insts(delta)
    simulator.run()

    exit_cause = simulator.get_last_exit_event_cause()
    if "max inst" not in exit_cause.lower() and "simpoint" not in exit_cause.lower():
        print(f"[SP {i}] Unexpected exit: {exit_cause} -- aborting")
        break

    instructions_so_far = target

    cpt_dir = os.path.join(
        m5.options.outdir, f"cpt.simpoint_{i:02d}_idx{sp_index}"
    )
    print(f"[SP {i}] Taking checkpoint at {instructions_so_far:,} "
          f"instructions -> {cpt_dir}")
    m5.checkpoint(cpt_dir)

print(f"\nAll checkpoints done. Total instructions fast-forwarded: "
      f"{instructions_so_far:,}")
