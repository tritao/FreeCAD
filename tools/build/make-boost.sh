#!/usr/bin/env bash
set -eux
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

# replace in emscripten.jam
# toolset.flags emscripten.archive .AR $(condition) : $(archiver[1]) ; to "emar"
# toolset.flags emscripten.archive .RANLIB $(condition) : $(ranlib[1]) ; to "emranlib"

if [ ! -d "$SCRIPT_DIR/tools/b2" ]; then
    git clone https://github.com/bfgroup/b2.git $SCRIPT_DIR/tools/b2
    cd $SCRIPT_DIR/tools/b2
    curl https://patch-diff.githubusercontent.com/raw/bfgroup/b2/pull/111.patch -o 111.patch
    git apply 111.patch
    ./bootstrap.sh
fi

cd $SCRIPT_DIR
BOOST_LIBS="system filesystem program_options regex system thread date_time"
./tools/b2/b2 toolset=emscripten link=static variant=release threading=single runtime-link=static $BOOST_LIBS

# if it fails, add:
# #pragma clang diagnostic ignored "-Wenum-constexpr-conversion"
# to third_party/boost/boost/mpl/integral_c.hpp

./tools/b2/b2 headers

EMSCRIPTEN_SYSROOT=../emsdk/upstream/emscripten/cache/sysroot/
cp -R boost $EMSCRIPTEN_SYSROOT/include

TOOLSET=emscripten-3.1.21
cp bin.v2/libs/filesystem/build/$TOOLSET/release/link-static/visibility-hidden/libboost_filesystem.a $EMSCRIPTEN_SYSROOT/lib
cp bin.v2/libs/program_options/build/$TOOLSET/release/link-static/visibility-hidden/libboost_program_options.a $EMSCRIPTEN_SYSROOT/lib
cp bin.v2/libs/regex/build/$TOOLSET/release/link-static/runtime-link-static/visibility-hidden/libboost_regex.a $EMSCRIPTEN_SYSROOT/lib
cp bin.v2/libs/system/build/$TOOLSET/release/link-static/visibility-hidden/libboost_system.a $EMSCRIPTEN_SYSROOT/lib
cp bin.v2/libs/thread/build/$TOOLSET/release/link-static/threadapi-pthread/threading-multi/visibility-hidden/libboost_thread.a $EMSCRIPTEN_SYSROOT/lib
cp bin.v2/libs/date_time/build/$TOOLSET/release/link-static/visibility-hidden/libboost_date_time.a $EMSCRIPTEN_SYSROOT/lib
