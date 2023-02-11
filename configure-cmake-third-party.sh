#!/usr/bin/env bash
set -eu

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

cd $SCRIPT_DIR/third_party/zlib/ && ./configure.sh
cd $SCRIPT_DIR/third_party/boost/ && ./configure.sh
cd $SCRIPT_DIR/third_party/eigen/ && ./configure.sh
cd $SCRIPT_DIR/third_party/OCCT/ && ./configure.sh
cd $SCRIPT_DIR/third_party/xerces-c/ && ./configure.sh
cd $SCRIPT_DIR/third_party/qtbase/ && ./configure.sh