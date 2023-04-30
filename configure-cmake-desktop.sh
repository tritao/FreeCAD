#!/usr/bin/env bash
set -eux

# install python-is-python3

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

BUILD_DIR=$SCRIPT_DIR/build
mkdir -p $BUILD_DIR && cd $BUILD_DIR

CMAKE="cmake"

$CMAKE -G "Ninja" \
    -DCMAKE_BUILD_TYPE="Debug" \
    -DCMAKE_EXPORT_COMPILE_COMMANDS="1" \
    -DBUILD_SMESH:BOOL="0" \
    -DBUILD_FEM:BOOL="0" \
    -DBUILD_GUI:BOOL="1" \
    -DBUILD_IDF:BOOL="0" \
    -DBUILD_IMAGE:BOOL="0" \
    -DBUILD_IMPORT:BOOL="0" \
    -DBUILD_INSPECTION:BOOL="0" \
    -DBUILD_JS:BOOL="0" \
    -DBUILD_MATERIAL:BOOL="0" \
    -DBUILD_MESH_PART:BOOL="0" \
    -DBUILD_MESH:BOOL="0" \
    -DBUILD_OPENSCAD:BOOL="0" \
    -DBUILD_PART_DESIGN:BOOL="0" \
    -DBUILD_PART:BOOL="0" \
    -DBUILD_PATH:BOOL="0" \
    -DBUILD_PLOT:BOOL="0" \
    -DBUILD_POINTS:BOOL="0" \
    -DBUILD_PYTHON:BOOL="1" \
    -DBUILD_QUARTER:BOOL="1" \
    -DBUILD_QT5:BOOL="1" \
    -DBUILD_RAYTRACING:BOOL="0" \
    -DBUILD_REVERSEENGINEERING:BOOL="0" \
    -DBUILD_ROBOT:BOOL="0" \
    -DBUILD_SHOW:BOOL="0" \
    -DBUILD_SKETCHER:BOOL="0" \
    -DBUILD_SPREADSHEET:BOOL="0" \
    -DBUILD_START:BOOL="0" \
    -DBUILD_SURFACE:BOOL="0" \
    -DBUILD_TECHDRAW:BOOL="0" \
    -DBUILD_TEST:BOOL="0" \
    -DBUILD_TUX:BOOL="0" \
    -DBUILD_WEB:BOOL="0" \
    $SCRIPT_DIR

python ../src/Tools/PythonToCPP.py ../src/Base/Parameter.xsd src/Base/Parameter.inl xmlSchemeString

function configure-third-party() {
    cd $SCRIPT_DIR/third_party/zlib/ && ./configure.sh
    cd $SCRIPT_DIR/third_party/boost/ && ./configure.sh
    cd $SCRIPT_DIR/third_party/eigen/ && ./configure.sh
    cd $SCRIPT_DIR/third_party/OCCT/ && ./configure.sh
    cd $SCRIPT_DIR/third_party/xerces-c/ && ./configure.sh
    cd $SCRIPT_DIR/third_party/qtbase/ && ./configure.sh
}