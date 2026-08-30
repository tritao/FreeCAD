@echo on

set WAMR_PROFILE=%~1
if not defined WAMR_PROFILE if "%PKG_NAME%"=="wamr" set WAMR_PROFILE=interp
if not defined WAMR_PROFILE if "%PKG_NAME%"=="wamr-aot" set WAMR_PROFILE=aot
if not defined WAMR_PROFILE if "%PKG_NAME%"=="wamr-jit" set WAMR_PROFILE=jit
if not defined WAMR_PROFILE if "%PKG_NAME%"=="wamr-compiler" set WAMR_PROFILE=compiler
if not defined WAMR_PROFILE (
  echo Unsupported WAMR output: %PKG_NAME%
  exit /b 1
)
if not "%WAMR_PROFILE%"=="interp" if not "%WAMR_PROFILE%"=="aot" if not "%WAMR_PROFILE%"=="jit" if not "%WAMR_PROFILE%"=="compiler" (
  echo Unsupported WAMR profile: %WAMR_PROFILE%
  exit /b 1
)

if "%WAMR_PROFILE%"=="compiler" goto compiler

set FAST_INTERP=0
set BUILD_AOT=0
set BUILD_JIT=0
set INSTRUCTION_METERING=1
set LLVM_DIR_ARG=
set LLVM_LIBXML2_ARGS=
if "%WAMR_PROFILE%"=="aot" (
  set FAST_INTERP=1
  set BUILD_AOT=1
  set INSTRUCTION_METERING=0
)
if "%WAMR_PROFILE%"=="jit" (
  set FAST_INTERP=0
  set BUILD_AOT=1
  set BUILD_JIT=1
  set INSTRUCTION_METERING=0
  set LLVM_CONFIG_DIR=%BUILD_PREFIX%\freecad-wamr-llvm-config
  if not exist "%LLVM_CONFIG_DIR%" mkdir "%LLVM_CONFIG_DIR%"
  > "%LLVM_CONFIG_DIR%\LLVMConfig.cmake" echo include("%PREFIX%/lib/cmake/llvm/LLVMConfig.cmake")
  >> "%LLVM_CONFIG_DIR%\LLVMConfig.cmake" echo set(LLVM_AVAILABLE_LIBS LLVM)
  > "%LLVM_CONFIG_DIR%\LLVMConfigVersion.cmake" echo set(PACKAGE_VERSION "0")
  set LLVM_DIR_ARG=-DLLVM_DIR=%LLVM_CONFIG_DIR%
  set LLVM_LIBXML2_ARGS=-DLIBXML2_LIBRARY=%PREFIX%/lib/libxml2.lib -DLIBXML2_INCLUDE_DIR=%PREFIX%/include/libxml2
)

cmake -S . -B build -G Ninja ^
  %CMAKE_ARGS% ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_INSTALL_PREFIX=%PREFIX% ^
  -DBUILD_SHARED_LIBS=ON ^
  -DWAMR_BUILD_INTERP=1 ^
  -DWAMR_BUILD_FAST_INTERP=%FAST_INTERP% ^
  -DWAMR_BUILD_AOT=%BUILD_AOT% ^
  -DWAMR_BUILD_JIT=%BUILD_JIT% ^
  -DWAMR_BUILD_FAST_JIT=0 ^
  -DWAMR_BUILD_LIBC_BUILTIN=1 ^
  -DWAMR_BUILD_LIBC_WASI=0 ^
  -DWAMR_BUILD_MULTI_MODULE=0 ^
  -DWAMR_BUILD_BULK_MEMORY=1 ^
  -DWAMR_BUILD_SHARED_MEMORY=0 ^
  -DWAMR_BUILD_THREAD_MGR=0 ^
  -DWAMR_BUILD_LIB_PTHREAD=0 ^
  -DWAMR_BUILD_LIB_WASI_THREADS=0 ^
  -DWAMR_BUILD_MINI_LOADER=0 ^
  -DWAMR_BUILD_SIMD=1 ^
  -DWAMR_BUILD_REF_TYPES=1 ^
  -DWAMR_BUILD_MEMORY64=0 ^
  -DWAMR_BUILD_MULTI_MEMORY=0 ^
  -DWAMR_BUILD_INSTRUCTION_METERING=%INSTRUCTION_METERING% ^
  %LLVM_LIBXML2_ARGS% ^
  %LLVM_DIR_ARG%
if errorlevel 1 exit /b 1
goto build

:compiler
cmake -S wamr-compiler -B build -G Ninja ^
  %CMAKE_ARGS% ^
  -DCMAKE_BUILD_TYPE=Release ^
  -DCMAKE_INSTALL_PREFIX=%PREFIX% ^
  -DWAMR_BUILD_WITH_CUSTOM_LLVM=1 ^
  -DLLVM_DIR=%PREFIX%\lib\cmake\llvm ^
  -DLIBXML2_LIBRARY=%PREFIX%/lib/libxml2.lib ^
  -DLIBXML2_INCLUDE_DIR=%PREFIX%/include/libxml2
if errorlevel 1 exit /b 1

:build
cmake --build build --target install --parallel
if "%WAMR_PROFILE%"=="compiler" exit /b 0

if "%WAMR_PROFILE%"=="interp" (
  set PACKAGE_PROFILE=INTERP
  set PACKAGE_SUPPORTS_AOT=FALSE
  set PACKAGE_SUPPORTS_JIT=FALSE
  set PACKAGE_SUPPORTS_INSTRUCTION_METERING=TRUE
)
if "%WAMR_PROFILE%"=="aot" (
  set PACKAGE_PROFILE=AOT
  set PACKAGE_SUPPORTS_AOT=TRUE
  set PACKAGE_SUPPORTS_JIT=FALSE
  set PACKAGE_SUPPORTS_INSTRUCTION_METERING=FALSE
)
if "%WAMR_PROFILE%"=="jit" (
  set PACKAGE_PROFILE=JIT
  set PACKAGE_SUPPORTS_AOT=TRUE
  set PACKAGE_SUPPORTS_JIT=TRUE
  set PACKAGE_SUPPORTS_INSTRUCTION_METERING=FALSE
)
if not exist "%PREFIX%\share\wamr" mkdir "%PREFIX%\share\wamr"
> "%PREFIX%\share\wamr\FreeCADWamrProfile.cmake" echo set(FREECAD_WAMR_PACKAGE_PROFILE "%PACKAGE_PROFILE%")
>> "%PREFIX%\share\wamr\FreeCADWamrProfile.cmake" echo set(FREECAD_WAMR_PACKAGE_SUPPORTS_AOT %PACKAGE_SUPPORTS_AOT%)
>> "%PREFIX%\share\wamr\FreeCADWamrProfile.cmake" echo set(FREECAD_WAMR_PACKAGE_SUPPORTS_JIT %PACKAGE_SUPPORTS_JIT%)
>> "%PREFIX%\share\wamr\FreeCADWamrProfile.cmake" echo set(FREECAD_WAMR_PACKAGE_SUPPORTS_INSTRUCTION_METERING %PACKAGE_SUPPORTS_INSTRUCTION_METERING%)
