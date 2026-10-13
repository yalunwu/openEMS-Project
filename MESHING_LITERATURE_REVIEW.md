# Meshing literature review and proposed experiments

October 8, 2026. Initial targeted review for openEMS; not an exhaustive survey.
The aim is to improve accuracy, speed, and usability together. Published results
below motivate experiments; they do not establish speedups or accuracy in this
checkout. Recommendations and implementation estimates are our assessment.

## What the research adds to the plan

The strongest immediate addition is to compare mesh-generation algorithms before
choosing a replacement smoother. Also measure phase error and sensitivity to
geometry placement, rather than evaluating meshes only by line spacing and cell
count. For further accuracy gains, investigate how geometry is represented inside
cells. Subgridding and local time stepping remain separate, larger projects.

| Candidate | Expected contribution | Fit and next action |
| --- | --- | --- |
| Constrained spacing envelopes | Coordinate overlapping regional requirements and transitions across an entire axis | High near-term fit; prototype after fixed-line/protected-interval semantics are defined |
| Phase-error diagnostics | Identify coarse regions that distort propagation even when a wavelength rule is satisfied | Add propagation and graded-transition benchmarks |
| Output-driven refinement studies | Spend resolution where it changes impedance, resonance, or radiation results | Automate controlled reruns; use extrapolation only after checking convergence behavior |
| Thin-feature models | Avoid resolving some wire radii or conductor thicknesses with extremely small cells | Audit existing sheet/wire behavior; investigate a radius-aware wire extension |
| Interface-aware dielectric averaging | Reduce errors at sloped and curved dielectric interfaces | Benchmark current averaging first; prototype a restricted lossless-dielectric case |
| Conformal PEC treatment | Improve curved conducting boundaries on a Cartesian grid | Separate solver experiment with explicit stability checks |
| Stable Cartesian subgridding and local time stepping | Confine fine spatial and temporal resolution to small regions | Longer-term feasibility study; establish stability and backend costs first |
| Faster material mapping | Reduce mesh-to-operator setup time | Profile geometric queries and material assignment before choosing an acceleration strategy |

## Papers, limits, and openEMS implications

### 1. Structured meshing with regional constraints

Berens, Flintoft, and Dawson, **Structured Mesh Generation: Open-source automatic
nonuniform mesh generation for FDTD simulation**, IEEE Antennas and Propagation
Magazine 58(3), 45-55 (2016), DOI 10.1109/MAP.2016.2541606.
[Author manuscript](https://eprints.whiterose.ac.uk/id/eprint/100155/1/JournalAPM_postprint.pdf).

The method projects objects onto each axis, resolves overlapping spacing limits,
propagates permissible growth between regions, then fits integer cell counts.
It also treats assigning materials to the structured grid as a distinct problem.
These are useful design references for our regional constraints and setup profiling.

Proposed experiment: compare an envelope-based prototype with current smoothing
on overlapping dielectrics, narrow gaps, and repeated array features. Require
the same hard coordinates and protected edge cells, then compare constraint
violations, minimum spacing, cell count, and generation time. Use our conductor
sampling requirements rather than automatically putting every metal edge on a line.

The authors' [AEG Mesher repository](https://github.com/flintoftid/aegmesher)
currently says the paper's nonuniform line generation is not fully integrated
and is disabled. Treat it as a research reference, not a replacement dependency.

### 2. Numerical dispersion in graded meshes

Christ, Frohlich, and Kuster, **Correction of Numerical Phase Velocity Errors in
Nonuniform FDTD Meshes**, IEICE Transactions on Communications E85-B(12),
2904-2915 (2002).
[Publisher record](https://globals.ieice.org/en_transactions/communications/10.1587/e85-b_12_2904/_p),
[author-hosted paper](https://speag.swiss/assets/downloads/publications/Christ2002.pdf).

The paper develops phase-velocity correction for nonuniform meshes. Its exact
compensation targets one frequency and propagation direction; that is not a
general broadband guarantee.

Proposed experiment: measure phase and artificial reflection across graded
transitions over our operating band and several propagation directions. Use
results to calibrate spacing recommendations before considering coefficient
corrections. Long feed paths and array phase relationships are useful targets.

openEMS already has `Operator::CalcNumericPhaseVelocity()` and uses it in TFSF
setup. It estimates from average spacing, so it should be audited and benchmarked
before reuse as a mesh-quality predictor. Adding diagnostics is a smaller change
than adopting a corrected update scheme.

### 3. Refinement based on quantities we actually need

Austin et al., **Validation of frequency and mode extraction calculations from
time-domain simulations of accelerator cavities** (2010 preprint).
[Paper record](https://arxiv.org/abs/1005.2531).

This work combines time-domain mode extraction, embedded boundaries, and
Richardson extrapolation for cavity validation. It supports examining convergence
of physical outputs, but does not establish a universal error estimator for
arbitrary staircased antenna models.

Proposed experiment: automate at least three controlled resolutions and report
changes in complex S-parameters, resonance, impedance, and main-beam gain. Refine
one region or axis at a time to learn where resolution matters. Fit an observed
order only when the sequence behaves consistently; do not assume second order
through corners, changing feed geometry, or irregular boundary discretization.

This is initially an offline refine-and-rerun workflow. A rigorous goal-oriented
adjoint estimator or dynamic adaptive remeshing needs additional research and
solver support; neither is established by this source.

### 4. Thin-wire subcell models

Ledfelt, **A stable subcell model for arbitrarily oriented thin wires for the FDTD
method**, International Journal of Numerical Modelling 15(5-6), 503-515 (2002),
DOI 10.1002/jnm.466.
[Publisher abstract](https://onlinelibrary.wiley.com/doi/abs/10.1002/jnm.466).

The paper couples field and wire equations to model wires smaller than a cell,
including arbitrary orientations, with stability analysis and antenna examples.
This offers a different route from globally refining the grid to resolve a radius.

The current `CalcPEC_Curves()` follows a grid path and sets PEC coefficients on
that path; the reviewed function has no physical wire-radius correction.
openEMS also already implements conducting sheets. We should evaluate these
existing models before proposing new ones.

Proposed experiment: translate and rotate a fixed-radius dipole and loop relative
to the grid; compare impedance and resonance with a resolved reference or an
independent wire solver. A radius-aware wire model would be a physics extension,
not a change to the smoothing helper. Validate its radius/cell-size range and
coupling to feeds and materials explicitly.

### 5. Better dielectric interface treatment

Farjadpour et al., **Improving accuracy by sub-pixel smoothing in FDTD**, Proc.
SPIE 6322, 63220G (2006), DOI 10.1117/12.706155.
[Author manuscript](https://math.mit.edu/~stevenj/papers/FarjadpourRo06-SPIE.pdf).

The work derives interface-aware anisotropic averaging and demonstrates improved
convergence for sloped dielectric boundaries. Simply increasing the number of
samples or averaging permittivity indiscriminately is not the same algorithm.

The [Meep implementation documentation](https://meep.readthedocs.io/en/latest/Subpixel_Smoothing/)
limits its smoothing of material response to the nondispersive part and describes
reduced convergence at corners and directly on interfaces. It also requires
interfaces to be sufficiently resolved to be locally approximately flat.

openEMS already provides cell-center and quarter-cell material averaging in
`Operator::AverageMatCellCenter()` and `AverageMatQuarterCell()`. Our question is
whether a geometry-aware effective tensor improves on these existing methods.
Off-diagonal tensor coupling may require field-update and storage changes; this
needs an implementation audit, including Vulkan and dispersive extensions.

Proposed experiment: translate/rotate a lossless dielectric slab and test a
dielectric sphere. Compare phase, reflection/scattering, and sensitivity to grid
offset at equal memory. Start with current averaging modes, then a restricted
prototype. Treat metals and dispersive interfaces separately.

### 6. Conformal conducting boundaries without tiny cut-cell penalties

Zagorodnov, Schuhmann, and Weiland, **Conformal FDTD-methods to avoid time step
reduction with and without cell enlargement**, Journal of Computational Physics
(2007).
[Publisher record](https://www.sciencedirect.com/science/article/pii/S0021999107000642).

The authors describe uniformly stable and simplified conformal treatments of
curved PEC boundaries intended to avoid the timestep reduction associated with
small cut cells. The schemes have different stencil and accuracy tradeoffs.

Proposed experiment: curved PEC cavity and sphere scattering against analytic or
high-resolution references, recording resonance/RCS, timestep, and late-time
energy. A stability result must be checked against the exact EC-FDTD formulation
and its boundary/material extensions before integration.

This is distinct from dielectric subpixel averaging and from generating a graded
mesh. It may allow coarser grids for curved conductors, but is a solver feature.
Full algorithm review is required before choosing between the published schemes.

### 7. Stable subgridding, with local time stepping evaluated separately

Bekmambetova, Zhang, and Triverio, **A Dissipation Theory for Three-Dimensional
FDTD With Application to Stability Analysis and Subgridding**, IEEE Transactions
on Antennas and Propagation 66(12), 7156-7170 (2018), DOI
10.1109/TAP.2018.2869617.
[Publisher record](https://ieeexplore.ieee.org/document/8458404/),
[author preprint](https://arxiv.org/abs/1705.02274).

The method derives stability from the energy properties of grids and their
coupling, including material traversal and odd refinement ratios. Its demonstrated
subgrids still use a timestep limited by the fine grid. Spatial savings alone
do not remove the global time-step cost.

Pederson and Raja, **A stable finite-difference time-domain scheme for local
time-stepping on an adaptive mesh**, Journal of Computational Physics 394,
456-476 (2019), DOI 10.1016/j.jcp.2019.05.043.
[Publisher record](https://www.sciencedirect.com/science/article/abs/pii/S0021999119303870).

This separate line of work treats local time stepping and stabilization of
high-frequency aliasing. The published abstract reports 1D, 2D, and 3D examples.
It deserves a full-method review if unavoidable small cells dominate our runtime.

Proposed experiment: first reproduce a passive coarse/fine interface, pulse
reflection, material traversal, and long-time cavity stability on CPU. Then assess
local time stepping, processing timestamps, PML coupling, dispersive materials,
and GPU scheduling. Passing a short pulse test would be insufficient.

### 8. A recent result worth tracking, with a concrete scope limit

Wang et al., **A Stable SBP-SAT FDTD Subgridding Method Without Region Split**,
April 2026 preprint.
[Full text](https://arxiv.org/html/2604.14618v1).

The method embeds a fine region in a surrounding coarse domain without splitting
the latter into multiple auxiliary blocks. It uses an energy-based treatment of
grid coupling. The inspected formulation and examples are 2D TM; its conclusion
lists 3D extension as future work. The examples also use the fine-mesh CFL
timestep. It is therefore promising research, not a demonstrated replacement for
our full 3D solver or a local-time-stepping solution.

## How this changes the implementation decision

1. Keep mesh diagnostics and required-coordinate preservation first.
2. Compare an envelope-based generator against strict repair of the existing
   smoother. Select using identical constraints and measured cost.
3. Expand benchmarks with graded propagation, rotated/translated interfaces,
   curved PEC, and fixed-radius wire cases. Separate representation error from
   wave-propagation and temporal error.
4. Profile geometry-to-material mapping because historical antenna timing shows
   substantial time outside the stepping loop. Investigate acceleration only
   after locating the actual setup bottleneck.
5. Choose one interface or thin-wire prototype based on which benchmark errors
   dominate the intended applications. Keep Cartesian subgridding and local
   time stepping in a separately evaluated research track.

For every candidate, record dimensionality, supported materials, timestep
restriction, stability evidence, changes to the operator/engine, CPU/GPU memory,
and total runtime at matched accuracy. Reproduce a published small example before
generalizing a method to openEMS workloads.

## Review depth and remaining evidence

Read algorithm/limitation sections in the accessible manuscripts for structured
meshing, dielectric smoothing, nonuniform phase correction, dissipation-based
3D subgridding, and the 2026 preprint. Thin-wire, conformal PEC, and local-time
stepping recommendations currently rely on publisher abstracts or accessible
excerpts; the cavity-validation source was reviewed at abstract level. Meep and
AEG Mesher are implementation cross-checks, not independent proofs of suitability.

This review selected primary papers, author manuscripts, and project-owned
documentation. No proposed method was implemented or benchmarked in this turn.
