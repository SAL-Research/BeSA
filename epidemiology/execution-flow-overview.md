# Execution flow of BioDynaMo epidemiology use case

## 1. Purpose

The demo models the spread of an infectious disease (measles, per the default parameters in `sim-param.h`) through a population of agents using a standard **SIR** (Susceptible → Infected → Recovered) compartmental model, implemented as an **agent-based simulation**. The agent-based result is compared against an **analytical ODE solution** of the same SIR dynamics to validate the simulation, and optionally the model is fit to data via multi-simulation parameter estimation.

## 2. Entry Point: `main()` (`epidemiology.cc`)

Execution starts in `main()`:

1. Registers the simulation-specific parameter group: `Param::RegisterParamGroup(new SimParam())`.
2. Constructs a `Simulation` object from CLI args, which parses config (e.g. `measles.json` / `optim.json`) into `Param` / `SimParam`.
3. Reads `sparam->mode`, which selects one of two execution paths:
   - **`"sim-and-analytical"`** → run a single/repeated ABM simulation and compare it directly to the analytical SIR solution.
   - **any other mode** (e.g. an optimization/fitting mode) → run the **multi-simulation** parameter-estimation routine (`MultiSimulation`), fitting the ABM to the analytical curve.

```
main()
 ├─ RegisterParamGroup(SimParam)
 ├─ Simulation simulation(argc, argv)
 ├─ sparam->mode == "sim-and-analytical"?
 │    ├─ yes → ExperimentSimAndAnalytical(...)
 │    └─ no  → GetAnalyticalResults(...) + MultiSimulation::Execute(Simulate)
```

## 3. Path A — `ExperimentSimAndAnalytical()`

1. **Analytical baseline**: `GetAnalyticalResults(param)` calls `CalculateAnalyticalSolution()`, which integrates the classical SIR ODEs with GSL's `gsl_odeiv2` RK2 stepper (`Odes()` defines dS/dt, dI/dt, dR/dt from `beta`, `gamma`, and population size `n`). Output is normalized fractions of susceptible/infected/recovered over time, stored in a `TimeSeries`.
2. **Simulation wrapper**: a lambda wraps `Simulate(argc, argv, result, param)` (the actual ABM run, see §4).
3. **`Experiment(...)`** runs the wrapped simulation `repeat` times, computes the mean trajectory across runs, and returns the **mean-squared error (MSE)** against the analytical curve.
4. **Plotting**: a lambda calls `PlotResults()` to overlay the analytical curve, the mean of the simulated runs, and each individual run, saving figures (`.svg`, `.root`, `.C`) to the `output` folder.
5. MSE is printed and the program exits.

## 4. Path B — Multi-Simulation Fitting

If `mode` is not `"sim-and-analytical"`, the analytical solution is still computed as the fitting target, and `MultiSimulation` (from BioDynaMo's `multi_simulation` module) repeatedly executes `Simulate()` with different parameter sets, using the `Experiment`/`database` infrastructure to search for parameters that best reproduce the analytical curve.

## 5. Core Agent-Based Simulation: `Simulate()` (`epidemiology.h`)

This is the core of the ABM and runs identically whether invoked from Path A or Path B:

1. **Parameter override**: a `set_param` lambda restores parameters from `final_params` (from the fitting/experiment layer), fixes `random_seed = 0`, sets `simulation_time_step = 1`, and uses a **toroidal (wrap-around) bounded space**.
2. **Simulation construction**: `Simulation sim(argc, argv, set_param)` initializes the BioDynaMo engine, `UniformGridEnvironment` (spatial index used for neighbor search), RNG, and parameters.
3. **Agent (Person) creation**:
   - A `person_creator` lambda instantiates a `Person` at a given position, sets its diameter, initial `state_`, and attaches behaviors: `Infection`, `Recovery`, and — probabilistically, based on `moving_agents_ratio` — `RandomMovement`.
   - `ModelInitializer::CreateAgentsRandom()` is called **twice**:
     - once to create `initial_population_susceptible` agents in state `kSusceptible`,
     - once to create `initial_population_infected` agents in state `kInfected`.
   - Agents are randomly distributed within `[param->min_bound, param->max_bound]`.
4. **Result collection setup**: `SetupResultCollection(&sim)` registers three `Counter` collectors on the simulation's `TimeSeries` — fractions of susceptible, infected, and recovered agents — each normalized by total agent count every time step.
5. **Spatial grid tuning**: the environment's box length is set to `infection_radius`, so each grid cell roughly matches the infection interaction range (relevant to cache/memory locality of neighbor lookups).
6. **Scheduler setup**: the default `"mechanical forces"` operation is unscheduled (agents don't physically push each other apart — movement is governed only by the `RandomMovement` behavior).
7. **Main loop**: `scheduler->Simulate(sparam->number_of_iterations)` runs the discrete time-stepped simulation for `number_of_iterations` steps (default 1000), timed via a `Timing` scoped timer labeled `"RUNTIME"`. Each step, BioDynaMo iterates over all agents and executes their attached behaviors.
8. **Result extraction**: the simulation's internal `TimeSeries` (populated incrementally by the collectors each step) is moved into the caller-provided `result`.

## 6. Per-Agent Behaviors (`behavior.h`) — What Happens Each Iteration

Each `Person` agent has up to three behaviors executed every simulation step:

- **`Infection`**
  - Only acts if the person is currently `kSusceptible`.
  - Draws a uniform random number; proceeds only if it falls under `infection_probablity`.
  - Uses the execution context's `ForEachNeighbor()` to **gather-scan** all neighboring agents within `infection_radius` (spatial-grid-accelerated neighbor search).
  - If any neighbor is `kInfected`, the person transitions to `kInfected`.
  - This is the **irregular, pointer-chasing, read-heavy** step: each agent reads neighbor state via the spatial grid, with no writes to neighbors (gather semantics, no cross-thread write hazards).

- **`Recovery`**
  - Only acts if the person is `kInfected`.
  - With probability `recovery_probability`, transitions the person to `kRecovered`.
  - Purely local (reads/writes only its own state) — cheap, branchy, memory-light compared to `Infection`.

- **`RandomMovement`** (attached only to a `moving_agents_ratio` fraction of agents)
  - Generates a random 3D unit vector, scales it by `agent_speed`, and updates the agent's position.
  - Interacts with the spatial grid indirectly: moving agents may need to be relocated to different grid cells between steps, which is a secondary source of memory traffic.

## 7. State Model (`person.h`)

`Person` extends `SphericalAgent` (a BioDynaMo `Cell`-like agent with a position and diameter) and adds a single integer field `state_` taking values from the `State` enum: `kSusceptible`, `kInfected`, `kRecovered`. This compact per-agent state plus the spatial grid neighbor lookups are the two data structures most relevant to the memory-access-pattern characterization (cf. DAMOV top-down analysis): the grid drives irregular gather traffic in `Infection`, while `state_` reads/writes are effectively free (co-located, small).

## 8. Parameters (`sim-param.h`)

Key tunables (defaults shown, calibrated to measles):

| Parameter | Default | Role |
|---|---|---|
| `mode` | `"sim-and-analytical"` | Selects execution path (§2) |
| `beta` | 0.06719 | SIR transmission rate (analytical model) |
| `gamma` | 0.00521 | SIR recovery rate (analytical model) |
| `repeat` | 4 | Number of ABM runs averaged in Path A |
| `number_of_iterations` | 1000 | Simulation time steps |
| `initial_population_susceptible` | 2000 | Initial susceptible agent count |
| `initial_population_infected` | 10 | Initial infected agent count |
| `infection_radius` | ~10.51 | Neighbor-search radius for `Infection`; also sets grid box length |
| `moving_agents_ratio` | 1.0 | Fraction of agents with `RandomMovement` |
| `recovery_probability` | 0.00521 | Per-step recovery chance |
| `agent_diameter` | 2.0 | Agent size |
| `agent_speed` | ~5.79 | Per-step movement magnitude |
| `infection_probablity` | ~0.285 | Per-step infection-check chance (gate before neighbor scan) |

## 9. Validation & Output (`evaluate.h`)

- `SetupResultCollection()`: wires up the three normalized-fraction counters described in §5.
- `PlotResults()`: builds a `LineGraph` overlaying (up to) the analytical SIR curves (dashed), the mean of the ABM runs (solid), and each individual run (faint), then saves plots as `.svg`/`.root`/`.C` in the specified output folder. Legend is trimmed to the first four meaningful entries.

## 10. End-to-End Summary Diagram

```
                     ┌────────────────────────┐
                     │        main()          │
                     └───────────┬────────────┘
                                 │
                     RegisterParamGroup(SimParam)
                     Simulation simulation(argc, argv)
                                 │
                 ┌───────────────┴───────────────┐
      mode == "sim-and-analytical"        mode == (fitting)
                 │                                │
   ExperimentSimAndAnalytical            GetAnalyticalResults
                 │                                │
     ┌───────────┴───────────┐          MultiSimulation(Simulate)
 analytical SIR (GSL ODE)   Experiment(          │
                             Simulate, repeat)    │
                                 │                │
                          ┌──────┴───────┐        │
                          │  Simulate()  │◄───────┘
                          │ (ABM, per-run)│
                          └──────┬───────┘
                                 │
       create agents (Susceptible + Infected, random positions)
       attach behaviors: Infection, Recovery, [RandomMovement]
       set grid box length = infection_radius
       unschedule mechanical forces
       scheduler->Simulate(number_of_iterations)
         └─ each step, each agent runs its behaviors:
              Infection  → gather-scan neighbors within radius
              Recovery   → local state transition
              RandomMovement → update position
       collect susceptible/infected/recovered fractions per step
                                 │
                          TimeSeries result
                                 │
                  MSE vs analytical + PlotResults (Path A only)
```

## 11. Relevance to Performance Characterization

- The **`Infection` behavior's neighbor gather** (via `ForEachNeighbor` over the `UniformGridEnvironment`) is the dominant irregular-memory-access step per iteration — pointer-chasing through spatial grid buckets and neighbor agent records, analogous to graph-traversal workloads.
- **`Recovery`** and the `state_` field access are cheap and highly local — not expected to be a major contributor to cache/bandwidth pressure.
- **`RandomMovement`** couples to grid maintenance (agents changing cells), a secondary memory-traffic source scaling with `moving_agents_ratio`.
- Iteration count (`number_of_iterations`) and population size (`initial_population_susceptible/infected`) are the two primary knobs for scaling workload size in thread/agent-count sweeps.