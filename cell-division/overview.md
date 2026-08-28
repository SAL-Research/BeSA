# Overview of cell division BioDynaMo use case

**Directory:** `demo/cell_division/` — files: `src/cell_division.h` (setup + `Simulate()`), `src/cell_division.cc` (thin `main()` calling `bdm::cell_division::Simulate`).

**Setup (`cell_division.h:30-59`):** No custom `Param`, no diffusion. Creates a `4x4x4` grid (`cells_per_dim = 4`) of plain `Cell` agents spaced 20 units apart via `ModelInitializer::Grid3D(cells_per_dim, spacing, construct)`. The `construct` lambda (lines 41-51) builds each `Cell` with `diameter_min = 5`, and attaches `new GrowthDivision(diameter_max=10, growth_ratio=50)`.

**Behavior:** Uses the built-in core behavior `bdm::GrowthDivision` (`src/core/behavior/growth_division.h:28-69`), not a custom one. Its `Run()`:
```cpp
void Run(Agent* agent) override {
  if (auto* cell = dynamic_cast&lt;Cell*&gt;(agent)) {
    if (cell-&gt;GetDiameter() &lt;= threshold_) {
      cell-&gt;ChangeVolume(growth_rate_);
    } else {
      cell-&gt;Divide();
    }
  }
}
```
(growth_division.h:54-63) — grows the cell each step until diameter exceeds `threshold_` (10), then calls `Cell::Divide()`, which splits the cell into two daughters (default random split ratio/direction) that each inherit a copy of the behavior via `Initialize()` (lines 38-49), which copies `threshold_`/`growth_rate_` from the mother's behavior instance.

**Custom Agent subclass:** None — uses stock `Cell`.

**Substances/diffusion:** None used.

**Flow:** `Simulation` created with defaults → 64 cells placed on a grid → `simulation.GetScheduler()-&gt;Simulate(111)` runs 111 steps (default scheduler operations: mechanical forces/displacement + behavior execution) → prints "Simulation completed successfully!". No custom scheduler operations added.