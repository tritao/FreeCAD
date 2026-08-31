# SPDX-License-Identifier: LGPL-2.1-or-later

foreach(_required INPUT OUTPUT ABI_HASH_FILE ENTRY)
    if(NOT DEFINED ${_required} OR "${${_required}}" STREQUAL "")
        message(FATAL_ERROR
            "GenerateExtensionManifest.cmake requires ${_required}")
    endif()
endforeach()

file(READ "${INPUT}" _source)
string(REGEX REPLACE "#[^\r\n]*" "" _source "${_source}")

string(REGEX MATCHALL
    "(^|\n)[ \t]*name[ \t]*=[ \t]*\"[^\"]*\""
    _name_matches
    "${_source}"
)
list(LENGTH _name_matches _name_count)
if(NOT _name_count EQUAL 1)
    message(FATAL_ERROR
        "freecad-extension.toml must contain exactly one name string")
endif()
string(REGEX MATCH
    "(^|\n)[ \t]*name[ \t]*=[ \t]*\"([^\"]*)\""
    _name_match
    "${_source}"
)
set(_name "${CMAKE_MATCH_2}")
if(_name MATCHES "[\\\"]")
    message(FATAL_ERROR "extension manifest name cannot contain escapes or quotes")
endif()

set(_permissions)
string(REGEX MATCH
    "(^|\n)[ \t]*permissions[ \t]*=[ \t]*\\[([^]]*)\\]"
    _permissions_match
    "${_source}"
)
set(_permission_source "${CMAKE_MATCH_2}")
if(_source MATCHES "(^|\n)[ \t]*permissions[ \t]*=" AND NOT _permissions_match)
    message(FATAL_ERROR "permissions must be an array of basic strings")
endif()
if(_permissions_match)
    string(REGEX MATCHALL "\"[^\"]*\"" _permission_matches
        "${_permission_source}")
    foreach(_permission_match IN LISTS _permission_matches)
        string(REGEX REPLACE "^\"|\"$" "" _permission
            "${_permission_match}")
        if(_permission MATCHES "[\\\"]")
            message(FATAL_ERROR
                "extension manifest permissions cannot contain escapes or quotes")
        endif()
        list(APPEND _permissions "${_permission}")
    endforeach()
    string(REGEX REPLACE "\"[^\"]*\"" "" _permission_remainder
        "${_permission_source}")
    string(REGEX REPLACE "[ \t\r\n,]" "" _permission_remainder
        "${_permission_remainder}")
    if(NOT _permission_remainder STREQUAL "")
        message(FATAL_ERROR
            "permissions must be an array of basic strings")
    endif()
endif()

set(_remaining "${_source}")
string(REPLACE "${_name_match}" "" _remaining "${_remaining}")
if(_permissions_match)
    string(REPLACE "${_permissions_match}" "" _remaining
        "${_remaining}")
endif()
string(REGEX REPLACE "[ \t\r\n]" "" _remaining "${_remaining}")
if(NOT _remaining STREQUAL "")
    message(FATAL_ERROR
        "freecad-extension.toml contains unsupported or malformed fields")
endif()

file(READ "${ABI_HASH_FILE}" _abi_hash)
string(STRIP "${_abi_hash}" _abi_hash)
string(LENGTH "${_abi_hash}" _abi_hash_length)
if(NOT _abi_hash_length EQUAL 71
   OR NOT _abi_hash MATCHES "^sha256:[0-9a-f]+$")
    message(FATAL_ERROR "invalid FreeCAD Extension SDK ABI hash")
endif()
if(NOT ENTRY MATCHES "^[A-Za-z0-9._-]+$")
    message(FATAL_ERROR "generated extension entry has an unsupported filename")
endif()

set(_permission_json)
foreach(_permission IN LISTS _permissions)
    list(APPEND _permission_json "    \"${_permission}\"")
endforeach()
if(_permission_json)
    list(JOIN _permission_json ",\n" _permission_json)
    set(_permissions_block "[\n${_permission_json}\n  ]")
else()
    set(_permissions_block "[]")
endif()

file(WRITE "${OUTPUT}"
    "{\n"
    "  \"name\": \"${_name}\",\n"
    "  \"extension_api\": 1,\n"
    "  \"abi_hash\": \"${_abi_hash}\",\n"
    "  \"entry\": \"${ENTRY}\",\n"
    "  \"permissions\": ${_permissions_block}\n"
    "}\n"
)
