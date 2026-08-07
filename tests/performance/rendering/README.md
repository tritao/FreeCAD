# Rendering performance fixtures

The tools in this directory generate deterministic FCStd inputs, validate
their save/reopen and Coin scene-graph state, and benchmark fixed camera
rotations. The launcher runs them in a normal FreeCAD GUI process; this is
required for view providers and OpenGL rendering. The shell wrapper transports
arguments through `FREECAD_RENDERING_ARGS` so FreeCAD receives only the macro
path and exits consistently after the command completes.

Set `FREECAD_BIN` to the GUI build you want to test. Add `--xvfb` for a
repeatable headless Linux run:

```bash
FREECAD_BIN=/path/to/FreeCAD \
  bash run_rendering.sh --xvfb generate-face \
  --preset perface-same-medium --output /tmp/face_perface_same_medium.FCStd

FREECAD_BIN=/path/to/FreeCAD \
  bash run_rendering.sh --xvfb generate-face \
  --preset perface-calibrated-large --output /tmp/face_perface_calibrated_large.FCStd

FREECAD_BIN=/path/to/FreeCAD \
  bash run_rendering.sh --xvfb generate-assembly \
  --preset links-medium --output /tmp/assembly_links_medium.FCStd

FREECAD_BIN=/path/to/FreeCAD \
  bash run_rendering.sh --xvfb validate \
  /tmp/face_perface_same_medium.FCStd \
  --scene-graph --require-scene-graph

FREECAD_BIN=/path/to/FreeCAD \
  bash run_rendering.sh --xvfb benchmark \
  /tmp/face_perface_same_medium.FCStd \
  --frames 120 --warmup 30 --output /tmp/face-results.json
```

The benchmark JSON records the OpenGL vendor, renderer, versions, GLSL
version, direct-rendering status, viewport, build type, FreeCAD commit, Coin
version, fixture hash, and raw measured frame times. Xvfb runs are labelled
`xvfb-llvmpipe` when that renderer is detected.

On a desktop Mesa session, disable presentation synchronization for renderer
microbenchmarks or the samples may be pinned near the monitor refresh period:

```bash
vblank_mode=0 FREECAD_BIN=/path/to/FreeCAD \
  bash run_rendering.sh benchmark /tmp/face_palette_16_medium.FCStd \
  --frames 60 --warmup 10 --output /tmp/uncapped.json
```

Use the resulting values only when the reported medians are no longer
clustered around 16.67 ms on a 60 Hz display. Keep the environment and
renderer fields in the result JSON when comparing runs.

For pre/post measurements of one build, create a JSON configuration containing
the build binary, fixture hashes, and run settings. The same binary path may be
used for both phases; collect `pre` before rebuilding and `post` afterwards.

When comparing separate build directories, `compare_builds.py` prepends each
phase binary's sibling `build/lib` directory to `LD_LIBRARY_PATH`. This keeps
the executable, FreeCAD libraries, and Coin library from being mixed between
phases.

```json
{
  "phases": {
    "pre": {"binary": "/path/to/build/bin/FreeCAD", "build_type": "Debug"},
    "post": {"binary": "/path/to/build/bin/FreeCAD", "build_type": "Debug"}
  },
  "fixtures": [
    {"name": "face-overall-medium", "path": "/tmp/face_overall_medium.FCStd", "sha256": "..."},
    {"name": "face-perface-same-medium", "path": "/tmp/face_perface_same_medium.FCStd", "sha256": "..."},
    {"name": "face-perface-alternating-medium", "path": "/tmp/face_perface_alternating_medium.FCStd", "sha256": "..."},
    {"name": "assembly-links-medium", "path": "/tmp/assembly_links_medium.FCStd", "sha256": "..."}
  ],
  "runs": 5,
  "frames": 360,
  "warmup": 100,
  "xvfb": true
}
```

Collect the baseline before changing Coin:

```bash
python3 compare_builds.py --config comparison.json --phase pre \
  --xvfb --output-dir /tmp/rendering-comparison-pre
```

After rebuilding with the performance fix, collect the post results into a
different directory:

```bash
python3 compare_builds.py --config comparison.json --phase post \
  --xvfb --output-dir /tmp/rendering-comparison-post
python3 compare_results.py \
  --pre /tmp/rendering-comparison-pre/comparison.json \
  --post /tmp/rendering-comparison-post/comparison.json \
  --output-dir /tmp/rendering-comparison
```

Each phase/fixture/run is a fresh FreeCAD process. `comparison.json` contains
the aggregate statistics; `comparison.md` contains the collection or pre/post
summary; and `raw/` retains every result JSON and frame sample. The final
comparison rejects mismatched fixture hashes or render environments.

The generators perform their own save/reopen validation. Generate canonical
fixtures once, record their SHA-256 hashes, and reuse those exact files when
comparing FreeCAD revisions.

The `perface-calibrated-large` face fixture uses the existing large 64x64 plate
grid (24,576 faces) and a deterministic 13-color palette, matching the scale
and palette cardinality of the face-dominated issue model.

The face generator also provides palette-cardinality presets for crossover
experiments. They keep the geometry and seed fixed while changing only the
number of deterministic face colors:

```text
perface-palette-1-medium
perface-palette-2-medium
perface-palette-4-medium
perface-palette-8-medium
perface-palette-13-medium
perface-palette-16-medium
perface-palette-32-medium
perface-palette-64-medium
perface-palette-256-medium
```

For the adaptive grouped-versus-unified experiment, use Coin's referenced
material analysis instead of a fixed color-count switch:

```bash
COIN_FACE_MATERIAL_STRATEGY=auto \
COIN_FACE_MATERIAL_MAX_GROUPS=8 \
COIN_FACE_MATERIAL_MIN_TRIANGLES_PER_GROUP=32 \
COIN_FACE_MATERIAL_MIN_UNIFIED_TRIANGLES=512 \
  FREECAD_BIN=/path/to/FreeCAD bash run_rendering.sh --xvfb benchmark \
  /tmp/face_palette_16_medium.FCStd --frames 60 --warmup 10 \
  --output /tmp/adaptive.json
```

`auto` selects grouped rendering for a small palette with sufficiently large
groups and unified rendering for larger palettes on supported opaque geometry.
For focused diagnostics, `COIN_FACE_MATERIAL_STRATEGY` can also be set to
`grouped`, `unified`, `overall`, or `fallback`. The adaptive mode remains
opt-in until real-GPU measurements establish the crossover.

`SoBrepFaceSet` retains only the FreeCAD-specific material remap: its
topological-face colors are expanded to the rendered-triangle
`PER_FACE_INDEXED` representation that Coin consumes. Coin then owns the
overall, grouped, unified, and fallback strategy selection and its caches.

Run the focused live-mutation smoke test against a canonical fixture to check
that color and geometry notifications invalidate the render-ready cache:

```bash
FREECAD_BIN=/path/to/FreeCAD bash run_rendering.sh mutation \
  /tmp/face_perface_calibrated_large.FCStd \
  --stats /tmp/mutation-report.json
```

The test uses asymmetric RGBA values, mutates face colors, coordinate data,
normals, and indices, and records the expected cache invalidations. It also
attempts to install a custom vertex attribute; Coin must reject that state
rather than expanding an unhandled attribute array.
