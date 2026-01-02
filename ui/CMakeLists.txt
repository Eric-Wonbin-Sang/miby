cmake_minimum_required(VERSION 3.16)
project(ui LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_compile_definitions(LV_CONF_INCLUDE_SIMPLE)
add_compile_definitions(LV_LVGL_H_INCLUDE_SIMPLE)

include_directories(
  ${CMAKE_CURRENT_SOURCE_DIR}/include
  ${CMAKE_CURRENT_SOURCE_DIR}/third_party/lvgl
  ${CMAKE_CURRENT_SOURCE_DIR}/third_party/lvgl/src
)

# Platform options (set by build.sh)
option(UI_PLATFORM_SDL "Build with SDL window/input" ON)
option(UI_PLATFORM_FBDEV "Build with Linux FBDEV display" OFF)

if(UI_PLATFORM_SDL AND UI_PLATFORM_FBDEV)
  message(FATAL_ERROR "Choose only one: UI_PLATFORM_SDL or UI_PLATFORM_FBDEV")
endif()

if(UI_PLATFORM_SDL)
  add_compile_definitions(UI_PLATFORM_SDL)
  find_package(SDL2 REQUIRED)
endif()

# Define FBDEV platform macro when enabled
if(UI_PLATFORM_FBDEV)
  add_compile_definitions(UI_PLATFORM_FBDEV)
endif()

file(GLOB_RECURSE LVGL_SRC
  third_party/lvgl/src/*.c
)
add_library(lvgl STATIC ${LVGL_SRC})

if(UI_PLATFORM_SDL)
  target_link_libraries(lvgl PRIVATE ${SDL2_LIBRARIES})
endif()

# Collect all C++ sources under src/ recursively
file(GLOB_RECURSE UI_SRC CONFIGURE_DEPENDS
  src/*.cpp
)

add_executable(ui_app ${UI_SRC})
target_link_libraries(ui_app PRIVATE lvgl)

if(UI_PLATFORM_SDL)
  target_link_libraries(ui_app PRIVATE ${SDL2_LIBRARIES})
endif()
