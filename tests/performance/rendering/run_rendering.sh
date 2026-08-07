#!/usr/bin/env bash

set -euo pipefail

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
freecad_bin=${FREECAD_BIN:-FreeCAD}
use_xvfb=0

if [[ "${1:-}" == "--xvfb" ]]; then
    use_xvfb=1
    shift
fi

if [[ $# -eq 0 ]]; then
    echo "usage: $0 [--xvfb] <command> [command arguments...]" >&2
    echo "commands: analyze, benchmark, generate-assembly, generate-face, mutation, validate" >&2
    exit 2
fi

script_args_json=$(python3 -c 'import json, sys; print(json.dumps(sys.argv[1:]))' "$@")
freecad_args=("$script_dir/rendering_launcher.fcmacro")
if [[ $use_xvfb -eq 1 ]]; then
    exec env FREECAD_RENDERING_ARGS="$script_args_json" FREECAD_RENDERING_ENVIRONMENT=xvfb \
        xvfb-run -a "$freecad_bin" "${freecad_args[@]}"
fi
exec env FREECAD_RENDERING_ARGS="$script_args_json" FREECAD_RENDERING_ENVIRONMENT=desktop \
    "$freecad_bin" "${freecad_args[@]}"
