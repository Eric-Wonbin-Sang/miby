#pragma once

#define LV_COLOR_DEPTH 16
#define LV_COLOR_16_SWAP 0

#define LV_USE_LOG 1
#define LV_LOG_LEVEL LV_LOG_LEVEL_WARN

#define LV_USE_LABEL 1
#define LV_USE_BTN 1
#define LV_USE_LIST 1
#define LV_USE_TEXTAREA 1
#define LV_USE_FLEX 1

#if defined(UI_PLATFORM_SDL)
#  define LV_MEM_SIZE (8U * 1024U * 1024U)
#else
#  define LV_MEM_SIZE (512U * 1024U)
#endif

/* Platform-specific LVGL drivers */
#if defined(UI_PLATFORM_SDL)
#  define LV_USE_SDL 1
#  define LV_SDL_INCLUDE_PATH <SDL2/SDL.h>
#else
#  define LV_USE_SDL 0
#endif

#if defined(UI_PLATFORM_FBDEV)
#  define LV_USE_LINUX_FBDEV 1
#  define LV_USE_EVDEV 1
#else
#  define LV_USE_LINUX_FBDEV 0
#  define LV_USE_EVDEV 0
#endif
