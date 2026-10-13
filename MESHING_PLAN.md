# Meshing improvement plan

Reviewed October 8, 2026. Priority: balance accuracy, speed, and usability.

Start by making mesh quality measurable and preserving required coordinates.
Then add an opt-in meshing path that enforces explicit constraints and reduces
cost only when convergence tests support the change.

## Literature-informed additions

The [targeted literature review](MESHING_LITERATURE_REVIEW.md) adds several
experiments before selecting the new meshing algorithm:

- Compare a constrained spacing-envelope generator with strict repair of the
  current smoother, using identical fixed lines and protected intervals.
- Measure phase error and reflections at graded transitions, and sensitivity
  to translating or rotating interfaces relative to the grid.
- Audit existing material averaging and sheet/wire representations. Evaluate
  interface-aware averaging and radius-aware wire models where those errors
  dominate, as separate physics prototypes.
- Profile material mapping and geometric queries during operator setup.
- Review stable Cartesian subgridding separately from local time stepping;
  fewer spatial cells do not by themselves remove the fine-grid timestep limit.

The review ranks candidates, links primary sources, identifies scope limits,
and proposes tests. It does not establish performance gains in openEMS.

## Findings from this checkout

| Finding | Evidence | Consequence |
| --- | --- | --- |
| The Python smoother does not enforce the requested grading ratio globally. | `SmoothMeshLines([0, 0.1, 1], 1, ratio=1.5)` returns the input, with a 9:1 spacing jump. Its loop only processes gaps exceeding `max_res`. | A successful call does not mean the finished mesh meets the requested quality. |
| Near-duplicate cleanup can remove a required coordinate. | Smoothing `[0, 1e-8, 1]` with `max_res=0.2` removes the boundary at zero. `Unique()` uses a tolerance based on mean spacing. | Required geometry planes and domain endpoints need protection; close coordinates need an explicit conflict policy. |
| Python geometry hints are limited. | `openEMS/automesh.py` dispatches points and boxes only; transformed boxes return no hint, with a warning. `AddEdges2Grid()` skips missing hints. | A general automatic-meshing workflow needs coverage reporting and more geometry support. |
| MATLAB has useful analysis and algorithm selection that Python lacks. | `AnalyseMesh`, `CheckMesh`, and `AutoSmoothMeshLines` already exist. Static review also found that `CheckMesh` quiet mode suppresses recording min/max spacing errors. | Reuse the concepts, fix the diagnostic discrepancy, and establish common behavior across interfaces. |
| Mesh combination assumes Python lists. | Combining NumPy arrays `[1, 3]` and `[2, 4]` produces `[3, 7]`, because `+` adds arrays. The `sort` argument is unused. | Normalize supported input types and define ordering/duplicate semantics. |

The current upstream [meshing documentation](https://docs.openems.de/en/latest/concepts/mesh.html#smoothing)
also explicitly states that the ratio is not a post-condition. This is a known
limitation to address deliberately, rather than an undocumented promise we can
assume already holds.

Validation performed: all 25 existing Python smoothing and automesh tests passed;
the targeted cases above were run against the current pure-Python sources.
Native objects came from the existing Windows installation, not a fresh build.
The environment emitted an HDF5 version warning; no HDF5 operations or new FDTD
simulations were run. The MATLAB quiet-mode finding is from code inspection.
The reproducer and output are in `build/meshing_review.py` and
`build/meshing-review-results.txt` (ignored local review artifacts).

## Existing performance baseline

Saved antenna XML files contain uniform Cartesian meshes at about 9.993 mm spacing:

| Saved preset | Grid lines x/y/z | Geometric cells | Solver storage nodes |
| --- | --- | ---: | ---: |
| large-mesh | 337 / 321 / 51 | 5,376,000 | 5,517,027 |
| xlarge-ready | 625 / 609 / 51 | 18,969,600 | 19,411,875 |
| stress-mesh | 913 / 897 / 51 | 40,857,600 | 41,767,011 |

Keep these counts distinct: geometric cells are `(Nx-1)(Ny-1)(Nz-1)`, while the
solver reports `Nx*Ny*Nz` storage nodes as cells. All three have an estimated
vacuum CFL timestep of 19.245 ps. Report that estimate separately from the actual
solver-selected timestep, particularly for nonuniform meshes.

The saved large-array run reports 7.09 seconds for 1,000 iterations and 54.64
seconds overall. That makes setup and other overhead worth measuring separately.
It is a historical fixed-step performance result, not an accuracy baseline.

## Proposed sequence

### 1. Establish diagnostics and numerical baselines

Add a reusable mesh report before simulation, available from Python and
MATLAB/Octave. Put coordinate and spacing analysis in CSXCAD; put frequency,
material, port, boundary, and solver cost interpretation in openEMS.

Report:

- Finite coordinates, positive finite units, sufficient lines, and positive spacings.
- Minimum/maximum spacing, worst adjacent ratio, and the coordinates of violations.
- Required sheet/port alignment, unresolved geometry hints, and PML/NF2FF placement.
- Geometric cell count, solver storage size, and backend-specific memory estimates
  with their assumptions and omissions stated.
- Cartesian vacuum CFL estimate and its limiting intervals; actual timestep and
  step count after setup. Cylindrical grids need metric-aware analysis, not the
  current Cartesian helper applied to angular coordinates.

Correct MATLAB quiet-mode accounting and normalize mesh-combination inputs.
Return structured diagnostics as well as readable messages so scripts can enforce
budgets without parsing console output.

Create a small benchmark set: rectangular waveguide or cavity, CPW/microstrip with
thin metal, a dipole, and a small array. Reuse existing physics tests where useful.
Use the saved large arrays for scale measurements; add a maintained small-array
fixture for refinement studies, since its former tutorial source is absent from
this checkout.

Completion: both interfaces detect the same malformed fixtures; reports identify
specific coordinates; each benchmark has three mesh levels and recorded accuracy,
memory, setup time, solve time, actual timestep, and stopping criterion.

### 2. Make smoothing constraints explicit

Distinguish required lines from generated lines. Preserve required values exactly,
including endpoints and sheet planes; deduplicate exact duplicates, but do not
silently merge distinct required coordinates. Make any optional snapping
unit-aware and report what changed.

Introduce protected intervals for conductor-edge cells and other placements that
must survive smoothing. This is essential before enforcing grading more strictly:
splitting a handcrafted edge cell can defeat its intended field sampling.

Add an opt-in strict smoother that checks maximum spacing and adjacent ratios
over the whole final axis, with finite input validation, an iteration/line budget,
and a final verification step. When protected intervals, minimum spacing, grading,
or budgets conflict, return the conflicting constraints and positions.

Completion: tests cover the reproduced failures, translated/asymmetric meshes,
symmetry, fixed-plane preservation, protected intervals, invalid inputs, and
bounded failure. Existing symmetry fixes remain covered. Legacy behavior remains
available while examples migrate to the stricter contract.

### 3. Add geometry-aware, cost-aware generation

Build a high-level pipeline: gather constraints, resolve conflicts, generate axis
lines, add smooth transitions and PML padding, then validate the finished mesh.

Start with boxes, thin sheets, substrates, ports, and axis-preserving transforms.
Next add polygons/extrusions and axis-aligned cylinders. General rotations and
curved objects need conservative hints plus explicit resolution controls; a
bounding box alone does not resolve their surfaces. Every unsupported primitive
must appear in the report.

Support per-axis and per-region spacing caps, material wavelength limits, and
explicit feature/gap resolution. Start material-derived limits with positive,
nondispersive isotropic materials; require explicit guidance for cases the policy
cannot interpret reliably. Preserve conductor-edge cells and sheet planes as
different constraints. Make PML padding and object clearance explicit, drawing on
the existing MATLAB `AddPML` helper.

Track why each line was added. Show which feature creates the smallest spacing
and how a proposed refinement affects total storage and estimated work. In this
rectilinear grid, an added line spans the domain: refinement near one feature can
increase cost everywhere along that plane.

Completion: representative models can be meshed through one documented workflow;
all required constraints survive; unsupported cases are visible; candidate meshes
fit their budgets or explain why they cannot.

### 4. Optimize against measured convergence

Compare uniform meshes with graded meshes that retain fine spacing at feeds,
gaps, conductor edges, and interfaces and permit coarser spacing elsewhere.
Start with the small fixtures before the 19M/42M-node arrays.

Rank candidates by total wall time and peak memory subject to numerical accuracy.
Also record storage nodes multiplied by actual step count: fewer nodes alone can
be misleading if a tiny interval forces a smaller timestep.

Keep geometry, material values, port reference planes, physical simulation time,
and boundary treatment controlled across comparisons. Separate temporal settling
from spatial convergence; fixed iteration counts simulate different durations
when the timestep changes. Avoid changing the physical feed model as the mesh is
refined. Repeat selected cases on CPU and Vulkan after the mesh is validated.

Proposed starting convergence gates, to tune per fixture: less than 1% resonance
shift, maximum complex S-parameter change below 0.02 over the declared band, and
less than 0.2 dB main-beam gain change when applicable. Retain analytic checks and
inspect patterns near nulls with an appropriate absolute measure. Compare at
least three levels; agreement between two meshes alone is weak evidence.

Completion: publish accuracy-versus-cost tables and select settings only where
the measurements establish a benefit. No speedup percentage is assumed in advance.

### 5. Make the workflow easy to inspect

Provide preview/balanced/accuracy presets with visible numerical settings, a
preflight-only mode, saved reports, and spacing plots that mark fixed lines,
protected intervals, grading failures, and the smallest cells. Presets are
starting points, not certificates of convergence.

After the reports and API stabilize, expose the same diagnostics in AppCSXCAD /
QCSXCAD. Keep Python and MATLAB examples aligned and document the migration path.

## Scope and first implementation slice

Keep the first release within the existing rectilinear solver. General Cartesian
subgridding, adaptive remeshing, conformal-cell methods, and local time stepping
are separate solver research projects. Revisit them if measured cost remains
dominated by unavoidable small features after this work. Existing cylindrical
multigrid remains a specialized option for suitable models.

The first implementation slice should deliver the mesh report, regression
coverage for the reproduced failures, and safe fixes to line handling and
diagnostics. Establish benchmark baselines in parallel with that work, then
implement strict smoothing with protected intervals. Geometry automation and
performance tuning follow once those foundations are reliable.

Production meshing code was not changed during this review.
