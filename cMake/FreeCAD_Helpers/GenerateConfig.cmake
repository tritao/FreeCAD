macro(GenerateConfig)

    configure_file(${CMAKE_SOURCE_DIR}/src/config.h.cmake ${CMAKE_CURRENT_BINARY_DIR}/config.h)
    add_definitions(-DHAVE_CONFIG_H)

endmacro(GenerateConfig)
