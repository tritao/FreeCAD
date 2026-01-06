#!/usr/bin/env bash
set -euo pipefail

preset="${1:-debug}"
jobs="${JOBS:-}"
extra_cmake_args=()
if [[ -n "${CMAKE_ARGS:-}" ]]; then
  # shellcheck disable=SC2206
  extra_cmake_args+=(${CMAKE_ARGS})
fi

# Keep Base-only CI/dev runs lightweight: avoid optional submodules unless the
# caller explicitly enables them.
extra_cmake_args+=(-DBUILD_ASSEMBLY=OFF)
extra_cmake_args+=(-DBUILD_ADDONMGR=OFF)

if [[ "${SUBMODULES:-1}" != "0" ]]; then
  git submodule update --init --recursive
fi

case "$preset" in
  debug|release|conda-linux-debug|conda-linux-release|rpm) ;;
  *)
    echo "Usage: $0 [cmake-preset]" >&2
    echo "Known presets: debug, release, conda-linux-debug, conda-linux-release, rpm" >&2
    exit 2
    ;;
esac

if [[ -n "$jobs" ]]; then
  build_jobs=(--parallel "$jobs")
else
  build_jobs=(--parallel)
fi

cmake --preset "$preset" "${extra_cmake_args[@]}"

case "$preset" in
  debug) build_dir="build/debug" ;;
  release) build_dir="build/release" ;;
  *) build_dir="build/$preset" ;;
esac

cmake --build "$build_dir" "${build_jobs[@]}" --target Base_tests_run

(
  cd "$build_dir"
  ctest -R '^Base' --output-on-failure
)
