#!/usr/bin/env bash
set -eux

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
BUILD_DIR=build_em
mkdir -p $BUILD_DIR && cd $BUILD_DIR

CMAKE="emcmake cmake"
$CMAKE -G "Ninja" -DEMSCRIPTEN=1 \
    -DBUILD_MODULE_Visualization=0 \
    -DBUILD_MODULE_ApplicationFramework=0 \
    -DBUILD_MODULE_Draw=0 \
    -DBUILD_MODULE_DETools=0 \
    -DUSE_FREETYPE=0 \
    -DCMAKE_BUILD_TYPE=Release ..

ninja install
