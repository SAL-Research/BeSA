# Overview of tumor concept BioDynaMo use case

**Directory:** `demo/tumor_concept/` — files: `src/tumor_concept.h` (custom agent, `Growth` behavior, `Simulate()`), `src/tumor_concept.cc` (`main`).

**Setup (`tumor_concept.h:99-144`):** `bound_space=kClosed`, domain `0..100`. Creates `nb_of_cells = 2400` normal `MyCell` agents at uniform random positions in the cube, `SetDiameter(7.5)`, and `SetCellColor` based on `y_coord` layer (0-5), added via `ctxt-&gt;AddAgent(cell)` (no behavior — static tissue). Then one special "cancerous" cell is created at `(20,50,50)`, diameter 6, color 8, `SetCanDivide(true)`, with `AddBehavior(new Growth())` — the only proliferating/growing agent.

**Custom Agent subclass (`tumor_concept.h:28-64`):** `MyCell : public Cell` adds `bool can_divide_` and `int cell_color_`. Overrides `Initialize(const NewAgentEvent&amp;)` (lines 38-50) so daughters from division copy the mother's `cell_color_`, and specifically for `CellDivisionEvent`, the daughter gets `can_divide_ = true` (otherwise inherits mother's flag) — ensures division capability propagates only through actual division events.

**Behavior — custom `Growth` (`tumor_concept.h:67-97`):** `AlwaysCopyToNew()` in constructor. `Run()`:
```cpp
if (cell-&gt;GetDiameter() &lt; 8) {
  cell-&gt;ChangeVolume(400);
  Real3 cell_movements = random-&gt;UniformArray&lt;3&gt;(-2, 2);
  cell-&gt;UpdatePosition(cell_movements);
} else {
  if (cell-&gt;GetCanDivide() &amp;&amp; random-&gt;Uniform(0,1) &lt; 0.8) {
    cell-&gt;Divide();
  } else {
    cell-&gt;SetCanDivide(false);
  }
}
```
So below diameter 8 it grows and does a small random walk; once ≥8, it divides with 80% probability per step (else permanently disables further division).

**Substances/diffusion:** None used in this demo.

**Flow:** 2400 static cells + 1 seeded cancer cell → `simulation.GetScheduler()-&gt;Simulate(500)` steps using default operations (mechanical forces + behavior execution) → prints completion message. No custom scheduler operations added.