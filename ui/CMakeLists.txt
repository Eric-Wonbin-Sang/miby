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

find_package(SDL2 REQUIRED)

file(GLOB_RECURSE LVGL_SRC
  third_party/lvgl/src/*.c
)
add_library(lvgl STATIC ${LVGL_SRC})

target_link_libraries(lvgl PRIVATE ${SDL2_LIBRARIES})

add_executable(ui_app src/main.cpp)
target_link_libraries(ui_app PRIVATE lvgl ${SDL2_LIBRARIES})
