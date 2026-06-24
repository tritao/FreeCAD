macro(SetupBoost)
# -------------------------------- Boost --------------------------------

    set(_boost_TEST_VERSIONS ${Boost_ADDITIONAL_VERSIONS})

    find_package(Boost ${BOOST_MIN_VERSION}
        REQUIRED)

endmacro(SetupBoost)
