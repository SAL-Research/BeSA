# BioDynaMo Execution Model and Synchronization Analysis

## 1. Purpose

This document summarizes findings from source-code inspection of
BioDynaMo, focusing on: - Scheduler architecture - Parallel execution
model - OpenMP synchronization - Barrier placement - Implications for
BarrierPoint and SimPoint - Experimental considerations for performance
characterization

------------------------------------------------------------------------

## 2. BioDynaMo
Simulations advance in **discrete timesteps**, and during
each timestep every agent executes a sequence of operations. BioDynaMo
uses **OpenMP** to parallelize work across CPU threads.

``` text
Simulation
    │
    ▼
Time Step 1
Time Step 2
Time Step 3
...
```

------------------------------------------------------------------------

## 3. Scheduler Architecture

``` text
Scheduler::Execute()
        │
        ▼
RunScheduledOps()
        │
        ▼
RunAgentOps()
        │
        ▼
Standalone Operations
```

-   **Execute()** drives the simulation.
-   **RunScheduledOps()** orchestrates the work performed during each
    timestep.
-   **RunAgentOps()** performs the main agent computations.
-   **Standalone operations** execute afterwards for simulation-wide
    updates.

------------------------------------------------------------------------

## 4. Execution Order Modes

### kForEachAgentForEachOp (Default)

Defined in `param.h` as the default execution mode.

``` text
Agent 1
 ├── Update Staticness
 ├── Bound Space
 ├── Behavior
 ├── Mechanical Forces
 ├── Discretization
 ├── Propagate Staticness
 └── Continuum

Agent 2
...
```

Characteristics: - All seven operations are **bundled** together. - One
OpenMP parallel region for the entire agent phase. - Single implicit
synchronization at the end.

### kForEachOpForEachAgent

``` text
Operation 1 → all agents
Operation 2 → all agents
Operation 3 → all agents
...
```

Characteristics: - Separate OpenMP region per operation. - Multiple
synchronization points. - Finer-grained execution.

------------------------------------------------------------------------

## 5. Default Agent Operations

1.  Update Staticness
2.  Bound Space
3.  Behavior
4.  Mechanical Forces
5.  Discretization
6.  Propagate Staticness AgentOp
7.  Continuum

------------------------------------------------------------------------

## 6. Timestep Structure

``` text
┌────────────────────────────┐
│ Pre-scheduled Operations   │
└──────────────┬─────────────┘
               │
               ▼
┌────────────────────────────┐
│ Parallel Agent Operations  │
│ (single OpenMP region)     │
└──────────────┬─────────────┘
               │
        Implicit Barrier
               │
               ▼
┌────────────────────────────┐
│ Standalone Operations      │
└────────────────────────────┘
```

A timestep consists of: 1. Pre-scheduled bookkeeping. 2. Main parallel
computation over all agents. 3. Sequential standalone updates.

------------------------------------------------------------------------

## 7. Parallelization Model

``` text
#pragma omp parallel

Each thread receives a subset of agents.

For every assigned agent:
    Execute all seven operations

Implicit barrier
```

Threads work independently until the end of the parallel region.

------------------------------------------------------------------------

## 8. Explicit Barrier Analysis

Explicit barriers were identified in `resource_manager.cc` approximately
at lines:

-   295
-   392
-   440
-   461
-   470
-   545

These barriers belong to **resource management**, including: - Load
balancing - Agent migration - Agent removal - Commit phases

These are **maintenance paths**, not part of the normal timestep
executed every iteration.

------------------------------------------------------------------------


## 9. Implications for SimPoint

### Track 1 (Single-threaded)

-   Deterministic execution
-   No synchronization noise
-   Simpler evaluation
-   Good foundation for SimPoint

### Track 2 (Multi-threaded)

-   Preserve timestep granularity
-   Use BarrierPoint
-   Treat each timestep as one synchronization region

------------------------------------------------------------------------

## 10. Key Research Insights

1.  BioDynaMo's default scheduler bundles all agent operations into one
    OpenMP region.
2.  One timestep contains a single dominant synchronization point.
3.  Explicit barriers mainly appear in maintenance code, not regular
    timestep execution.
4.  BioDynaMo's default execution model closely matches BarrierPoint.
5.  Single-threaded and multi-threaded evaluation naturally map to
    SimPoint and BarrierPoint respectively.