cmake_minimum_required(VERSION 3.20)

project(fcui_qt_viewer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(CMAKE_AUTOMOC ON)

find_package(Python3 COMPONENTS Interpreter REQUIRED)

find_package(Qt6 COMPONENTS Widgets QUIET)
if(Qt6_FOUND)
  set(FCUI_QT_PACKAGE Qt6)
else()
  find_package(Qt5 COMPONENTS Widgets REQUIRED)
  set(FCUI_QT_PACKAGE Qt5)
endif()

set(FCUI_COMPILER ${CMAKE_CURRENT_LIST_DIR}/../FCUI/tools/fcui_compile.py)
set(FCUI_SHELL_PY ${CMAKE_CURRENT_LIST_DIR}/../FCUI/shell/main.fcui.py)
set(FCUI_SHELL_JSON ${CMAKE_CURRENT_BINARY_DIR}/fcui_shell/main.fcuim.json)

add_custom_command(
  OUTPUT ${FCUI_SHELL_JSON}
  COMMAND ${Python3_EXECUTABLE} ${FCUI_COMPILER} --in ${FCUI_SHELL_PY} --out ${FCUI_SHELL_JSON} --pretty
  DEPENDS ${FCUI_COMPILER} ${FCUI_SHELL_PY}
  COMMENT "Compiling FCUI-Py shell module for sample viewer"
  VERBATIM
)

add_custom_target(fcui_modules ALL DEPENDS ${FCUI_SHELL_JSON})

add_executable(fcui_qt_viewer
  src/main.cpp
)

add_library(FCUIQtRuntime STATIC
  ../FCUI/FCUIQtHost.h
  ../FCUI/FCUIQtRuntime.cpp
  ../FCUI/FCUIQtRuntime.h
  ../FCUI/VmEval.cpp
  ../FCUI/VmEval.h
)

target_include_directories(FCUIQtRuntime PUBLIC src ../FCUI)
target_link_libraries(FCUIQtRuntime PUBLIC ${FCUI_QT_PACKAGE}::Widgets)

target_include_directories(fcui_qt_viewer PRIVATE src)
target_link_libraries(fcui_qt_viewer PRIVATE FCUIQtRuntime)
