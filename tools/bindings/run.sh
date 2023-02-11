#!/usr/bin/env bash
set -e
dir=$(cd "$(dirname "$0")"; pwd)
dotnet_configuration=Release
configuration=debug
platform=x64

red=`tput setaf 1`
green=`tput setaf 2`
reset=`tput sgr0`

generate=true

if [ $generate = true ]; then
    echo "${green}Generating bindings${reset}"
    dotnet build $dir/FreeCADGen.csproj
    dotnet $dir/bin/${dotnet_configuration}/net6.0/FreeCADGen.dll 
fi

#cp -r $dir/gen/emscripten/* $dir/../../src/