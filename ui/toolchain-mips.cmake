cmake_minimum_required(VERSION 3.16)

# Generic MIPS/Linux cross-compilation toolchain file.
#
# Customize via environment variables:
#   - MIPS_TOOLCHAIN_PREFIX : e.g. mipsel-linux-gnu (default) or mips-linux-gnu
#   - MIPS_SYSROOT          : absolute path to a sysroot (RECOMMENDED for embedded targets)
#
# Example:
#   export MIPS_SYSROOT=/home/sang/local_coding_projects/miby/sysroot-r3pro2
#   export MIPS_TOOLCHAIN_PREFIX=mipsel-linux-gnu
#   ui/build.sh device

set(CMAKE_SYSTEM_NAME Linux)

# If you are targeting Ingenic-class little-endian MIPS, this is typically mipsel.
# If your device is big-endian, change to "mips".
set(CMAKE_SYSTEM_PROCESSOR mipsel)

# Toolchain triplet/prefix
if(DEFINED ENV{MIPS_TOOLCHAIN_PREFIX} AND NOT "$ENV{MIPS_TOOLCHAIN_PREFIX}" STREQUAL "")
  set(TOOLCHAIN_PREFIX "$ENV{MIPS_TOOLCHAIN_PREFIX}")
else()
  set(TOOLCHAIN_PREFIX "mipsel-linux-gnu")
endif()

# Resolve toolchain binaries explicitly (prevents silent PATH weirdness)
find_program(MIPS_GCC   NAMES ${TOOLCHAIN_PREFIX}-gcc   REQUIRED)
find_program(MIPS_GXX   NAMES ${TOOLCHAIN_PREFIX}-g++   REQUIRED)
find_program(MIPS_AR    NAMES ${TOOLCHAIN_PREFIX}-ar    REQUIRED)
find_program(MIPS_RANLIB NAMES ${TOOLCHAIN_PREFIX}-ranlib REQUIRED)
find_program(MIPS_STRIP NAMES ${TOOLCHAIN_PREFIX}-strip REQUIRED)

set(CMAKE_C_COMPILER   "${MIPS_GCC}")
set(CMAKE_CXX_COMPILER "${MIPS_GXX}")
set(CMAKE_AR           "${MIPS_AR}"     CACHE FILEPATH "ar")
set(CMAKE_RANLIB       "${MIPS_RANLIB}" CACHE FILEPATH "ranlib")
set(CMAKE_STRIP        "${MIPS_STRIP}"  CACHE FILEPATH "strip")

# ------------------------------------------------------------------------------
# Sysroot detection / selection
# ------------------------------------------------------------------------------

# 1) Prefer explicit env override
if(DEFINED ENV{MIPS_SYSROOT} AND NOT "$ENV{MIPS_SYSROOT}" STREQUAL "")
  set(CMAKE_SYSROOT "$ENV{MIPS_SYSROOT}")
  set(CMAKE_FIND_ROOT_PATH "$ENV{MIPS_SYSROOT}")
else()
  # 2) Fall back to compiler's configured sysroot
  execute_process(
    COMMAND "${CMAKE_C_COMPILER}" -print-sysroot
    OUTPUT_VARIABLE _GCC_PRINT_SYSROOT
    OUTPUT_STRIP_TRAILING_WHITESPACE
    ERROR_QUIET
  )

  # Many "floating" cross compilers return "/" or empty when no sysroot is configured
  if(_GCC_PRINT_SYSROOT AND NOT _GCC_PRINT_SYSROOT STREQUAL "/" AND NOT _GCC_PRINT_SYSROOT STREQUAL "")
    set(CMAKE_SYSROOT "${_GCC_PRINT_SYSROOT}")
    set(CMAKE_FIND_ROOT_PATH "${_GCC_PRINT_SYSROOT}")
  endif()
endif()

# If we have a sysroot, force gcc/g++ to use it
if(DEFINED CMAKE_SYSROOT AND NOT CMAKE_SYSROOT STREQUAL "")
  set(CMAKE_C_FLAGS   "${CMAKE_C_FLAGS} --sysroot=${CMAKE_SYSROOT}")
  set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} --sysroot=${CMAKE_SYSROOT}")
endif()

# Only search target paths for headers/libs; never for programs
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE ONLY)

# ------------------------------------------------------------------------------
# Fail-fast sanity checks (gives a clean error instead of CMake TryCompile noise)
# ------------------------------------------------------------------------------

# Confirm the compiler can locate crt1.o (startup object from libc dev/sysroot)
execute_process(
  COMMAND "${CMAKE_C_COMPILER}" -print-file-name=crt1.o
  OUTPUT_VARIABLE _CRT1
  OUTPUT_STRIP_TRAILING_WHITESPACE
  ERROR_QUIET
)

if(_CRT1 STREQUAL "crt1.o")
  message(FATAL_ERROR
    "Cross toolchain cannot find crt1.o (startup object). "
    "You are missing a valid target sysroot/libc-dev. "
    "Set MIPS_SYSROOT to a sysroot that contains lib/crt1.o and libc (or use a full SDK toolchain).\n"
    "Example:\n"
    "  export MIPS_SYSROOT=/path/to/sysroot\n"
    "  ui/build.sh device\n"
  )
endif()

# Optional: show what sysroot CMake ended up using (handy for debugging)
message(STATUS "MIPS toolchain prefix: ${TOOLCHAIN_PREFIX}")
message(STATUS "MIPS C compiler:       ${CMAKE_C_COMPILER}")
message(STATUS "MIPS sysroot:          ${CMAKE_SYSROOT}")
message(STATUS "crt1.o resolved to:    ${_CRT1}")
