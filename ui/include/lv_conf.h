#pragma once

#define LV_COLOR_DEPTH 16
#define LV_COLOR_16_SWAP 0

#define LV_USE_LOG 1
#define LV_LOG_LEVEL LV_LOG_LEVEL_WARN

#define LV_USE_LABEL 1
#define LV_USE_BTN 1

#define LV_MEM_SIZE (256U * 1024U)

/* Enable SDL-based drivers from LVGL (v9) */
#define LV_USE_SDL 1
#define LV_SDL_INCLUDE_PATH <SDL2/SDL.h>
