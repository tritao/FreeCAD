#!/usr/bin/env bash
set -eux

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
BUILD_DIR=build_em
mkdir -p $BUILD_DIR && cd $BUILD_DIR

CMAKE="emcmake cmake"
$CMAKE -G "Ninja" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS="1" \
    $SCRIPT_DIR

ninja install
