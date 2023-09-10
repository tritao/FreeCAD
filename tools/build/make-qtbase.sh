#!/usr/bin/env bash
set -eux

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

git checkout 5.15.2

BUILD_DIR=build_em
mkdir -p $BUILD_DIR && cd $BUILD_DIR

# Qt 5

emconfigure ../configure \
    -opensource -confirm-license \
    -xplatform wasm-emscripten \
    -prefix $SCRIPT_DIR/../emsdk/upstream/emscripten/cache/sysroot \
    -static \
    -nomake examples \
    -no-feature-testlib \
    -no-feature-sql \
    -no-feature-gui \
    -no-feature-widgets \

make -j8
make install

# Qt6

# CMAKE="emcmake cmake"
# $CMAKE -G "Ninja" \
#     -DQT_NO_PACKAGE_VERSION_CHECK="1" \
#     -DQT_NO_PACKAGE_VERSION_INCOMPATIBLE_WARNING="1" \
#     -DQT_HOST_PATH="$HOME/Qt6/6.3.2/gcc_64" \
#     -DFEATURE_testlib="0" \
#     -DFEATURE_xml="0" \
#     -DFEATURE_sql="0" \
#     -DFEATURE_network="0" \
#     -DFEATURE_gui="0" \
#     -DFEATURE_widgets="0" \
#     -DFEATURE_printsupport="0" \
#     -DBUILD_SHARED_LIBS="0" \
#     -DCMAKE_EXPORT_COMPILE_COMMANDS="1" \
#     $SCRIPT_DIR

#ninja
#ninja install