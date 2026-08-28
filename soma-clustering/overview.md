# Overview of soma clustering BioDynaMo use case

**Directory:** `demo/soma_clustering/` — files: `src/soma_clustering.h` (setup), `src/soma_clustering.cc` (`main`), `src/my_cell.h` (custom agent), `src/validation_criterion.h` (post-run clustering check).

**Setup (`soma_clustering.h:38-114`):** Custom `set_param` sets `bound_space = kClosed`, `min_bound=0`, `max_bound=800`. Random seed fixed to 4357. Two substances defined via `ModelInitializer::DefineSubstance(kSubstance0/1, name, diffusion_coeff=0.05, decay=0.001, resolution=40)` (lines 60-63). `num_cells = 32000` total, created half as type `1` (secreting/following `Substance_0`) and half as type `-1` (`Substance_1`), each with `SetDiameter(10)`, `SetMass(0.1)`, via `ModelInitializer::CreateAgentsRandom(...)` into a cube of side `2*cell_cube_length=250` centered in the domain (lines 82-93).

**Custom Agent subclass (`my_cell.h:25-38`):** `MyCell : public Cell` adds one field `int cell_type_` with constructor `MyCell(position, cell_type)` and `GetCellType()` getter — used to distinguish the two secreting populations.

**Behaviors attached (lines 76-77):** `Secretion(substance_name, secretion_constant=1.0)` and `Chemotaxis(substance_name, chemotaxis_constant=0.75)`, both core behaviors.
- `Secretion::Run` (`secretion.h:53-56`): `dgrid_-&gt;ChangeConcentrationBy(agent-&gt;GetPosition(), quantity_, mode_)` — deposits substance at the cell's location each step.
- `Chemotaxis::Run` (`chemotaxis.h:48-54`): computes normalized gradient at the cell position (`dgrid_-&gt;GetGradient`) and moves the cell via `cell-&gt;UpdatePosition(gradient * speed_)` — climbs its own type's gradient, causing same-type cells to aggregate.

**Substances/diffusion:** Two independent diffusion grids (`Substance_0`, `Substance_1`), each cell type only secretes/follows its own substance, driving segregated clustering.

**Flow:** `Simulate(1000)` steps (code warns 6000 is recommended) → after simulation, `GetCriterion(spatial_range=15, num_cells/8)` (`validation_criterion.h:28-138`) scans a sub-volume (first octant), computes same-type vs. different-type neighbor counts within `spatial_range`, and prints whether the "clustering criterion" is met.