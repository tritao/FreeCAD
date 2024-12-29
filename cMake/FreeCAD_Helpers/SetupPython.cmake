macro(SetupPython)
# -------------------------------- Python --------------------------------

    find_package(Python3 COMPONENTS Interpreter Development REQUIRED)

    if (${Python3_VERSION} VERSION_LESS "3.10")
         message(FATAL_ERROR "To build FreeCAD you need at least Python 3.10\n")
    endif()

    # If a custom Python directory was passed in, then save it as PYTHON_HOME_DIR,
    # which is used by config.h.cmake when generating the config header file.
    if (DEFINED Python3_ROOT_DIR)
        set(HAVE_PYTHON_HOME_DIR ON)
        file(REAL_PATH "${Python3_ROOT_DIR}" PYTHON_HOME_DIR)
    endif ()


endmacro(SetupPython)
