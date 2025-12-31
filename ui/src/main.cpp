#include "lvgl.h"
#include <unistd.h>

// Use LVGL's built-in SDL driver (v9)
#include "drivers/sdl/lv_sdl_window.h"
#include "drivers/sdl/lv_sdl_mouse.h"
#include "drivers/sdl/lv_sdl_keyboard.h"

static void tick_cb(lv_timer_t*) {
    lv_tick_inc(5);
}

int main() {
    lv_init();

    // Create an SDL window-backed display
    lv_display_t* disp = lv_sdl_window_create(480, 720);
    (void)disp;

    // Create SDL input devices (mouse, keyboard)
    lv_indev_t* mouse = lv_sdl_mouse_create();
    (void)mouse;
    lv_indev_t* kb = lv_sdl_keyboard_create();
    (void)kb;

    lv_obj_t* label = lv_label_create(lv_screen_active());
    lv_label_set_text(label, "LVGL UI directory works");
    lv_obj_center(label);

    lv_timer_create(tick_cb, 5, nullptr);

    while (true) {
        lv_timer_handler();
        usleep(5 * 1000);
    }
}
