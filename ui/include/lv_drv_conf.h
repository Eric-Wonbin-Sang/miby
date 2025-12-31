// Minimal lv_drivers configuration for this project
// Enables SDL-based display and input for the PC target.

#ifndef LV_DRV_CONF_H
#define LV_DRV_CONF_H

#include "lv_conf.h"

/* SDL based drivers for display, mouse, mousewheel and keyboard */
#ifndef USE_SDL
#define USE_SDL 1
#endif

/* Hardware accelerated SDL driver not used */
#ifndef USE_SDL_GPU
#define USE_SDL_GPU 0
#endif

/* Default SDL settings (match main.cpp) */
#ifndef SDL_HOR_RES
#define SDL_HOR_RES 480
#endif

#ifndef SDL_VER_RES
#define SDL_VER_RES 320
#endif

#ifndef SDL_ZOOM
#define SDL_ZOOM 1
#endif

#ifndef SDL_DOUBLE_BUFFERED
#define SDL_DOUBLE_BUFFERED 0
#endif

/* Path to SDL include header */
#ifndef SDL_INCLUDE_PATH
#define SDL_INCLUDE_PATH <SDL2/SDL.h>
#endif

/* Disable other drivers by default (kept as 0) */
#ifndef USE_MONITOR
#define USE_MONITOR 0
#endif

#ifndef USE_X11
#define USE_X11 0
#endif

#ifndef USE_WAYLAND
#define USE_WAYLAND 0
#endif

#ifndef USE_GTK
#define USE_GTK 0
#endif

#ifndef USE_LIBINPUT
#define USE_LIBINPUT 0
#endif

#ifndef USE_BSD_LIBINPUT
#define USE_BSD_LIBINPUT 0
#endif

#ifndef USE_EVDEV
#define USE_EVDEV 0
#endif

#ifndef USE_BSD_EVDEV
#define USE_BSD_EVDEV 0
#endif

#endif /* LV_DRV_CONF_H */

