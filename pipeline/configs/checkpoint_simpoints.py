"""
Stage 6: SimPoint checkpoint pass.

Single ascending-order run with AtomicSimpleCPU (fast, no caches).
Fast-forwards to each SimPoint offset and takes a checkpoint.

Reads SimPoint data from environment or falls back to files in
$WORK_DIR/sampling/simpoints/.

Usage:
    export WORK_DIR=~/tumor_concept_gem5
    ~/gem5/build/X86/gem5.opt configs/checkpoint_simpoints.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from gem5_common import *

import m5
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


def load_simpoints():
    """Load SimPoints from the pipeline's output files."""
    sp_dir = os.path.join(WORK_DIR, "sampling", "simpoints")
    bench = os.environ.get("BENCHMARK_NAME", "tumor_concept")

    simpts_file = os.path.join(sp_dir, f"{bench}_original.simpts")
    weights_file = os.path.join(sp_dir, f"{bench}.weights")

    indices = {}
    with open(simpts_file) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                orig_idx, cluster = int(parts[0]), int(parts[1])
                indices[cluster] = orig_idx

    weights = {}
    with open(weights_file) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2:
                weights[int(parts[1])] = float(parts[0])

    simpoints = []
    for cluster in sorted(indices.keys()):
        simpoints.append((indices[cluster], weights.get(cluster, 0.0)))

    simpoints.sort(key=lambda x: x[0])
    return simpoints


SIMPOINTS = load_simpoints()
print(f"Loaded {len(SIMPOINTS)} SimPoints:")
for i, (idx, w) in enumerate(SIMPOINTS):
    print(f"  SP {i}: index={idx} weight={w:.5f} offset={idx * INTERVAL_SIZE:,}")

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
instructions_so_far = 0

for i, (sp_index, weight) in enumerate(SIMPOINTS):
    target = sp_index * INTERVAL_SIZE
    delta = target - instructions_so_far

    if delta <= 0:
        print(f"[SP {i}] index={sp_index} target={target:,} -- "
              f"already past ({instructions_so_far:,}), skipping")
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
