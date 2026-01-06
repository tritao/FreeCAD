# SPDX-License-Identifier: LGPL-2.1-or-later

add_library(FreeCADView SHARED)

if(WIN32)
    add_definitions(-DFCView)
endif()

target_include_directories(
    FreeCADView
    PRIVATE
    ${CMAKE_BINARY_DIR}/src
    ${CMAKE_SOURCE_DIR}/src
    ${CMAKE_CURRENT_BINARY_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}
)

target_include_directories(FreeCADView SYSTEM PUBLIC ${COIN3D_INCLUDE_DIRS})
target_link_directories(FreeCADView PUBLIC ${COIN3D_LIB_DIRS})
target_link_libraries(FreeCADView PUBLIC ${COIN3D_LIBRARIES})

set(FreeCADView_SRCS
    SoDevicePixelRatioElement.cpp
    SoDevicePixelRatioElement.h
    Inventor/MarkerBitmaps.cpp
    Inventor/MarkerBitmaps.h
    Inventor/SmSwitchboard.cpp
    Inventor/SmSwitchboard.h
    Inventor/SoAutoZoomTranslation.cpp
    Inventor/SoAutoZoomTranslation.h
    Inventor/SoDrawingGrid.cpp
    Inventor/SoDrawingGrid.h
    Inventor/SoFCBackgroundGradient.cpp
    Inventor/SoFCBackgroundGradient.h
    Inventor/SoFCBoundingBox.cpp
    Inventor/SoFCBoundingBox.h
    Inventor/SoFCTransform.cpp
    Inventor/SoFCTransform.h
    Inventor/SoMouseWheelEvent.cpp
    Inventor/SoMouseWheelEvent.h
)

if (EIGEN3_NO_DEPRECATED_COPY)
    set_source_files_properties(
        Inventor/SoAutoZoomTranslation.cpp
        PROPERTIES COMPILE_FLAGS ${EIGEN3_NO_DEPRECATED_COPY})
endif ()

target_sources(FreeCADView PRIVATE ${FreeCADView_SRCS})

set_target_properties(FreeCADView PROPERTIES OUTPUT_NAME "FreeCADView")

SET_BIN_DIR(FreeCADView FreeCADView)

if(WIN32)
    install(TARGETS FreeCADView
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    )
else()
    install(TARGETS FreeCADView
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    )
endif()

