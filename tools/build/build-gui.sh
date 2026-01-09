#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Build FreeCAD GUI targets (incremental).

Usage:
  tools/build/build-gui.sh [options] [-- <cmake --build extra args...>]

Options:
  -B, --build-dir DIR   Build directory (default: auto-detect: $FC_BUILD_DIR, ./build, ./build/debug)
  -j, --jobs N          Parallel build jobs (default: auto)
      --configure       Run CMake configure step if needed
      --preset NAME     Configure preset to use when configuring (default: debug)
      --reduced         Reduced build (disable Sketcher/Mesh/MeshPart/TechDraw/BIM/PartDesign/Draft/Import/Spreadsheet)
      --no-sketcher     Disable Sketcher module (sets -DBUILD_SKETCHER=OFF)
      --no-mesh         Disable Mesh module (sets -DBUILD_MESH=OFF)
      --no-mesh-part    Disable MeshPart module (sets -DBUILD_MESH_PART=OFF)
      --no-techdraw     Disable TechDraw module (sets -DBUILD_TECHDRAW=OFF)
      --no-bim          Disable BIM module (sets -DBUILD_BIM=OFF)
      --no-partdesign   Disable PartDesign module (sets -DBUILD_PART_DESIGN=OFF)
      --no-draft        Disable Draft module (sets -DBUILD_DRAFT=OFF)
      --no-import       Disable Import module (sets -DBUILD_IMPORT=OFF)
      --no-spreadsheet  Disable Spreadsheet module (sets -DBUILD_SPREADSHEET=OFF)
  -t, --target NAME     Target to build (repeatable). Default: FreeCADGui
      --all             Build default target (everything in the build dir)
      --app             Shortcut for: --target FreeCAD
      --gui             Shortcut for: --target FreeCADGui
  -v, --verbose         Verbose build output
  -h, --help            Show this help

Examples:
  tools/build/build-gui.sh
  tools/build/build-gui.sh --app
  tools/build/build-gui.sh -B build -j 12 --target FreeCADGui --target FreeCAD
  tools/build/build-gui.sh --configure --preset debug -B build/debug
  tools/build/build-gui.sh --configure --preset gui-minimal -B build/gui-minimal
EOF
}

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
root_dir="$(cd "${script_dir}/../.." && pwd -P)"

build_dir="${FC_BUILD_DIR:-}"
jobs=""
do_configure="false"
preset="debug"
verbose="false"
targets=()
build_all="false"
extra_build_args=()
reduced="false"
disable_sketcher="false"
disable_mesh="false"
disable_mesh_part="false"
disable_techdraw="false"
disable_bim="false"
disable_partdesign="false"
disable_draft="false"
disable_import="false"
disable_spreadsheet="false"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    -B|--build-dir)
      build_dir="$2"
      shift 2
      ;;
    -j|--jobs)
      jobs="$2"
      shift 2
      ;;
    --configure)
      do_configure="true"
      shift
      ;;
    --preset)
      preset="$2"
      shift 2
      ;;
    --reduced)
      reduced="true"
      shift
      ;;
    --no-sketcher)
      disable_sketcher="true"
      shift
      ;;
    --no-mesh)
      disable_mesh="true"
      shift
      ;;
    --no-mesh-part)
      disable_mesh_part="true"
      shift
      ;;
    --no-techdraw)
      disable_techdraw="true"
      shift
      ;;
    --no-bim)
      disable_bim="true"
      shift
      ;;
    --no-partdesign)
      disable_partdesign="true"
      shift
      ;;
    --no-draft)
      disable_draft="true"
      shift
      ;;
    --no-import)
      disable_import="true"
      shift
      ;;
    --no-spreadsheet)
      disable_spreadsheet="true"
      shift
      ;;
    --all)
      build_all="true"
      shift
      ;;
    -t|--target)
      targets+=("$2")
      shift 2
      ;;
    --app)
      targets+=("FreeCAD")
      shift
      ;;
    --gui)
      targets+=("FreeCADGui")
      shift
      ;;
    -v|--verbose)
      verbose="true"
      shift
      ;;
    --)
      shift
      extra_build_args+=("$@")
      break
      ;;
    *)
      echo "Unknown argument: $1" >&2
      echo >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${build_dir}" ]]; then
  if [[ -f "${root_dir}/build/CMakeCache.txt" ]]; then
    build_dir="${root_dir}/build"
  elif [[ -f "${root_dir}/build/debug/CMakeCache.txt" ]]; then
    build_dir="${root_dir}/build/debug"
  else
    build_dir="${root_dir}/build"
    do_configure="true"
  fi
fi

if [[ "${build_dir}" != /* ]]; then
  build_dir="${root_dir}/${build_dir}"
fi

if [[ "${build_all}" == "false" ]] && [[ ${#targets[@]} -eq 0 ]]; then
  targets=("FreeCADGui")
fi

if [[ "${reduced}" == "true" ]]; then
  disable_sketcher="true"
  disable_mesh="true"
  disable_mesh_part="true"
  disable_techdraw="true"
  disable_bim="true"
  disable_partdesign="true"
  disable_draft="true"
  disable_import="true"
  disable_spreadsheet="true"
fi

cmake_cache_args=()
if [[ "${disable_sketcher}" == "true" ]]; then
  cmake_cache_args+=(-DBUILD_SKETCHER=OFF)
fi
if [[ "${disable_mesh}" == "true" ]]; then
  cmake_cache_args+=(-DBUILD_MESH=OFF)
fi
if [[ "${disable_mesh_part}" == "true" ]]; then
  cmake_cache_args+=(-DBUILD_MESH_PART=OFF)
fi
if [[ "${disable_techdraw}" == "true" ]]; then
  cmake_cache_args+=(-DBUILD_TECHDRAW=OFF)
fi
if [[ "${disable_bim}" == "true" ]]; then
  cmake_cache_args+=(-DBUILD_BIM=OFF)
fi
if [[ "${disable_partdesign}" == "true" ]]; then
  cmake_cache_args+=(-DBUILD_PART_DESIGN=OFF)
fi
if [[ "${disable_draft}" == "true" ]]; then
  cmake_cache_args+=(-DBUILD_DRAFT=OFF)
fi
if [[ "${disable_import}" == "true" ]]; then
  cmake_cache_args+=(-DBUILD_IMPORT=OFF)
fi
if [[ "${disable_spreadsheet}" == "true" ]]; then
  cmake_cache_args+=(-DBUILD_SPREADSHEET=OFF)
fi

if [[ "${do_configure}" == "true" ]] || [[ ! -f "${build_dir}/CMakeCache.txt" ]]; then
  if [[ "${preset}" != "" ]] && [[ "${build_dir}" == "${root_dir}/build/${preset}" ]]; then
    cmake --preset "${preset}" "${cmake_cache_args[@]}"
  else
    build_type="Debug"
    if [[ "${preset}" == "release" ]]; then
      build_type="Release"
    fi
    cmake -S "${root_dir}" -B "${build_dir}" -G Ninja \
      -DCMAKE_EXPORT_COMPILE_COMMANDS=ON \
      -DCMAKE_BUILD_TYPE="${build_type}" \
      -DBUILD_GUI=ON \
      "${cmake_cache_args[@]}"
  fi
fi

cmd=(cmake --build "${build_dir}")
if [[ "${build_all}" == "false" ]]; then
  cmd+=(--target "${targets[@]}")
fi
if [[ -n "${jobs}" ]]; then
  cmd+=(-j "${jobs}")
fi
if [[ "${verbose}" == "true" ]]; then
  cmd+=(--verbose)
fi
cmd+=("${extra_build_args[@]}")

echo "Build dir: ${build_dir}"
if [[ "${build_all}" == "true" ]]; then
  echo "Targets:   (default)"
else
  echo "Targets:   ${targets[*]}"
fi
exec "${cmd[@]}"
