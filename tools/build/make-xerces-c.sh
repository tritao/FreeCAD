#!/usr/bin/env bash
set -eux

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
BUILD_DIR=build_em
mkdir -p $BUILD_DIR && cd $BUILD_DIR

CMAKE="emcmake cmake"
$CMAKE -G "Ninja" \
    -DXERCES_STATIC_LIBRARY="1" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS="1" \
    $SCRIPT_DIR

ninja install

EMSCRIPTEN_SYSROOT=../../emsdk/upstream/emscripten/cache/sysroot/
cp $EMSCRIPTEN_SYSROOT/lib/libxerces-c-4.0.a $EMSCRIPTEN_SYSROOT/lib/libxerces-c.a 