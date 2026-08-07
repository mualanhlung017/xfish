cmake_minimum_required(VERSION 3.23)

project(xfish LANGUAGES CXX)

if(NOT (MSVC AND CMAKE_CXX_COMPILER_ID MATCHES "Clang"))
    message(FATAL_ERROR "The xfish Windows baseline must be built with clang-cl and the MSVC ABI.")
endif()

set(XFISH_ARCH "avx2" CACHE STRING "CPU baseline (currently: avx2)")
set_property(CACHE XFISH_ARCH PROPERTY STRINGS avx2)

set(XFISH_PGO "OFF" CACHE STRING "PGO stage: OFF, GENERATE, or USE")
set_property(CACHE XFISH_PGO PROPERTY STRINGS OFF GENERATE USE)
set(XFISH_PGO_PROFILE "" CACHE FILEPATH "Merged LLVM profile used by the USE stage")

option(XFISH_LTO "Enable link-time optimization" ON)

if(NOT XFISH_ARCH STREQUAL "avx2")
    message(FATAL_ERROR "Unsupported XFISH_ARCH='${XFISH_ARCH}'. This baseline is intentionally AVX2-only.")
endif()

string(TOUPPER "${XFISH_PGO}" XFISH_PGO)
if(NOT XFISH_PGO MATCHES "^(OFF|GENERATE|USE)$")
    message(FATAL_ERROR "XFISH_PGO must be OFF, GENERATE, or USE.")
endif()
if(XFISH_PGO STREQUAL "USE" AND NOT EXISTS "${XFISH_PGO_PROFILE}")
    message(FATAL_ERROR "XFISH_PGO_PROFILE must point to a merged .profdata file for the USE stage.")
endif()

file(GLOB_RECURSE XFISH_SOURCES CONFIGURE_DEPENDS "${CMAKE_CURRENT_SOURCE_DIR}/src/*.cpp")
list(FILTER XFISH_SOURCES EXCLUDE REGEX "/universal/")
list(FILTER XFISH_SOURCES EXCLUDE REGEX "/temp_builds/")

add_executable(xfish ${XFISH_SOURCES})
target_compile_features(xfish PRIVATE cxx_std_17)
target_include_directories(xfish PRIVATE "${CMAKE_CURRENT_SOURCE_DIR}/src")

set_target_properties(xfish PROPERTIES
    CXX_EXTENSIONS OFF
    MSVC_RUNTIME_LIBRARY "MultiThreaded"
    RUNTIME_OUTPUT_DIRECTORY "${CMAKE_BINARY_DIR}/bin"
)

# Keep the AVX2 feature set aligned with `make ARCH=x86-64-avx2` while using
# clang-cl, the Microsoft STL, the MSVC ABI, and the static MSVC runtime.
target_compile_definitions(xfish PRIVATE
    ARCH=x86-64-avx2
    USE_AVX2
    USE_POPCNT
    USE_SSE2
    USE_SSE41
    USE_SSSE3
    _CRT_SECURE_NO_WARNINGS
    _HAS_EXCEPTIONS=0
    NOMINMAX
    WIN32_LEAN_AND_MEAN
)

target_compile_options(xfish PRIVATE
    /nologo
    /O2
    /Ob3
    /GF
    /Gy
    /Brepro
    /arch:AVX2
    /clang:-O3
    /clang:-funroll-loops
    /clang:-fno-exceptions
    /clang:-mbmi
    /clang:-mpopcnt
    /clang:-msse4.1
    /clang:-mssse3
)

target_link_options(xfish PRIVATE
    /INCREMENTAL:NO
    /OPT:REF
    /OPT:ICF
)

if(XFISH_LTO)
    include(CheckIPOSupported)
    check_ipo_supported(RESULT XFISH_IPO_SUPPORTED OUTPUT XFISH_IPO_ERROR LANGUAGES CXX)
    if(NOT XFISH_IPO_SUPPORTED)
        message(FATAL_ERROR "clang-cl LTO is unavailable: ${XFISH_IPO_ERROR}")
    endif()
    set_property(TARGET xfish PROPERTY INTERPROCEDURAL_OPTIMIZATION TRUE)
endif()

if(XFISH_PGO STREQUAL "GENERATE")
    target_compile_options(xfish PRIVATE /clang:-fprofile-generate)
elseif(XFISH_PGO STREQUAL "USE")
    file(TO_CMAKE_PATH "${XFISH_PGO_PROFILE}" XFISH_PGO_PROFILE_CLANG)
    target_compile_options(xfish PRIVATE
        "/clang:-fprofile-use=${XFISH_PGO_PROFILE_CLANG}"
        /clang:-Wno-profile-instr-out-of-date
        /clang:-Wno-profile-instr-unprofiled
    )
endif()

execute_process(
    COMMAND git rev-parse --short=8 HEAD
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    OUTPUT_VARIABLE XFISH_GIT_SHA
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
)
execute_process(
    COMMAND git show -s --date=format:%Y%m%d --format=%cd HEAD
    WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
    OUTPUT_VARIABLE XFISH_GIT_DATE
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
)
if(XFISH_GIT_SHA)
    target_compile_definitions(xfish PRIVATE GIT_SHA=${XFISH_GIT_SHA})
endif()
if(XFISH_GIT_DATE)
    target_compile_definitions(xfish PRIVATE GIT_DATE=${XFISH_GIT_DATE})
endif()

message(STATUS "xfish architecture : x86-64-avx2")
message(STATUS "xfish compiler     : ${CMAKE_CXX_COMPILER_ID} ${CMAKE_CXX_COMPILER_VERSION} (${CMAKE_CXX_COMPILER})")
message(STATUS "xfish PGO stage    : ${XFISH_PGO}")
message(STATUS "xfish LTO          : ${XFISH_LTO}")
