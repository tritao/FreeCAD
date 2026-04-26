SET(PreferencePacks_Files
        "package.xml"
)

FILE(GLOB_RECURSE PreferencePacks_PackFiles
        CONFIGURE_DEPENDS
        RELATIVE "${CMAKE_CURRENT_SOURCE_DIR}"
        "FreeCAD Classic/*"
        "Dark behave/*"
        "FreeCAD Light/*"
        "FreeCAD Dark/*"
)

ADD_CUSTOM_TARGET(PreferencePacks_data ALL
        SOURCES ${PreferencePacks_Files} ${PreferencePacks_PackFiles}
)

FILE(COPY ${PreferencePacks_Files} DESTINATION "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Gui/PreferencePacks")
FILE(COPY "FreeCAD Classic" "Dark behave" "FreeCAD Light" "FreeCAD Dark"
     DESTINATION "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Gui/PreferencePacks")

fc_copy_sources(PreferencePacks_data "${CMAKE_BINARY_DIR}/${CMAKE_INSTALL_DATADIR}/Gui/PreferencePacks"
        ${PreferencePacks_Files}
        ${PreferencePacks_PackFiles})

INSTALL(
        FILES
        ${PreferencePacks_Files}
        DESTINATION
        ${CMAKE_INSTALL_DATADIR}/Gui/PreferencePacks
)

INSTALL(
        DIRECTORY
        "FreeCAD Classic"
        "Dark behave"
        "FreeCAD Light"
        "FreeCAD Dark"
        DESTINATION
        ${CMAKE_INSTALL_DATADIR}/Gui/PreferencePacks
)
