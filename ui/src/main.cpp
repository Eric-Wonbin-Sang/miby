//
// Simple LVGL app launcher shell with a scrollable home screen.
// Includes a File Explorer demo app with a back button.
// - PC: uses SDL window/input
// - Device: uses Linux FBDEV
//

#include "lvgl.h"
#include "pages/file_explorer.h"
#include "pages/mesh_demo.h"

#include <unistd.h>
#include <dirent.h>
#include <sys/stat.h>
#include <limits.h>
#include <string.h>

#include <string>
#include <vector>
#include <functional>
#include <algorithm>
#include <errno.h>
#include <cstdlib>

#if defined(UI_PLATFORM_SDL)
#include "drivers/sdl/lv_sdl_window.h"
#include "drivers/sdl/lv_sdl_mouse.h"
#include "drivers/sdl/lv_sdl_keyboard.h"
#elif defined(UI_PLATFORM_FBDEV)
#include "drivers/display/fb/lv_linux_fbdev.h"
#include "drivers/evdev/lv_evdev.h"
#endif

static void tick_cb(lv_timer_t*) { lv_tick_inc(5); }

static bool is_dir(const std::string& path) {
    struct stat st{};
    if (stat(path.c_str(), &st) != 0) return false;
    return S_ISDIR(st.st_mode);
}

static std::string join_path(const std::string& a, const std::string& b) {
    if (a.empty()) return b;
    if (a.back() == '/') return a + b;
    return a + "/" + b;
}

static int atoi_default(const char* s, int defv) {
    if (!s) return defv;
    int v = atoi(s);
    return v > 0 ? v : defv;
}

struct TreeCtx {
    lv_obj_t* list;
    int max_depth;
};

static void list_add_entry(lv_obj_t* list, const char* icon, const std::string& name, int depth) {
    std::string label(depth * 2, ' ');
    label += name;
    lv_obj_t* btn = lv_list_add_button(list, icon, label.c_str());
    (void)btn;
}

static void walk_dir(TreeCtx& ctx, const std::string& root, int depth) {
    if (ctx.max_depth > 0 && depth > ctx.max_depth) return;

    DIR* d = opendir(root.c_str());
    if (!d) return;

    std::vector<std::string> dirs;
    std::vector<std::string> files;

    while (true) {
        errno = 0;
        dirent* e = readdir(d);
        if (!e) break;
        if (strcmp(e->d_name, ".") == 0 || strcmp(e->d_name, "..") == 0) continue;
        std::string p = join_path(root, e->d_name);
        if (is_dir(p)) dirs.emplace_back(e->d_name);
        else files.emplace_back(e->d_name);
    }
    closedir(d);

    // Sort entries alphabetically
    std::sort(dirs.begin(), dirs.end());
    std::sort(files.begin(), files.end());

    for (const auto& dn : dirs) {
        list_add_entry(ctx.list, LV_SYMBOL_DIRECTORY, dn, depth);
        walk_dir(ctx, join_path(root, dn), depth + 1);
    }
    for (const auto& fn : files) {
        list_add_entry(ctx.list, LV_SYMBOL_FILE, fn, depth);
    }
}

static void clear_children(lv_obj_t* parent) { lv_obj_clean(parent); }

// Removed page-specific logic; moved to pages/file_explorer.{h,cpp}

// --- App framework: home screen + app pages ---

struct AppCtx {
    lv_obj_t* root{};      // active screen root
    lv_obj_t* home{};      // home page container (scrollable list of buttons)
    lv_obj_t* app_page{};  // current app page (with back header)
    int argc{};
    char** argv{};
};

static void show_home(AppCtx* app) {
    if (!app) return;
    if (app->app_page) {
        lv_obj_delete(app->app_page);
        app->app_page = nullptr;
    }
    if (app->home) {
        lv_obj_clear_flag(app->home, LV_OBJ_FLAG_HIDDEN);
    }
}

// Create a page wrapper with a top header containing a back button and title.
// Returns the page container to place content into (content area below header).
static lv_obj_t* create_app_page_with_back(AppCtx* app, const char* title_text,
        lv_event_cb_t back_cb, void* back_user_data)
{
    lv_obj_t* page = lv_obj_create(app->root);
    lv_obj_remove_style_all(page);

    // Let flex size it; or keep 100% if you want, but grow is usually cleaner in a flex column root.
    lv_obj_set_size(page, LV_PCT(100), LV_PCT(100));
    lv_obj_set_flex_flow(page, LV_FLEX_FLOW_COLUMN);

    lv_obj_set_style_pad_all(page, 0, 0);
    lv_obj_set_style_pad_row(page, 0, 0);

    // Header row
    lv_obj_t* hdr = lv_obj_create(page);
    lv_obj_remove_style_all(hdr);
    lv_obj_set_flex_flow(hdr, LV_FLEX_FLOW_ROW);
    lv_obj_set_width(hdr, LV_PCT(100));

    // *** IMPORTANT: make header shrink to its content ***
    lv_obj_set_height(hdr, LV_SIZE_CONTENT);

    // optional: give the header its own padding so it looks like a bar
    lv_obj_set_style_pad_left(hdr, 6, 0);
    lv_obj_set_style_pad_right(hdr, 6, 0);
    lv_obj_set_style_pad_top(hdr, 6, 0);
    lv_obj_set_style_pad_bottom(hdr, 6, 0);
    lv_obj_set_style_pad_column(hdr, 8, 0);

    lv_obj_t* btn_back = lv_button_create(hdr);
    lv_obj_remove_style_all(btn_back);
    lv_obj_set_size(btn_back, LV_SIZE_CONTENT, LV_SIZE_CONTENT);
    lv_obj_add_event_cb(btn_back, back_cb, LV_EVENT_CLICKED, back_user_data);

    lv_obj_t* back_lbl = lv_label_create(btn_back);
    lv_label_set_text(back_lbl, LV_SYMBOL_LEFT " Back");
    lv_obj_center(back_lbl);

    lv_obj_t* title = lv_label_create(hdr);
    lv_label_set_text(title, title_text ? title_text : "");

    // Content area
    lv_obj_t* content = lv_obj_create(page);
    lv_obj_remove_style_all(content);

    lv_obj_set_width(content, LV_PCT(100));
    // *** IMPORTANT: do NOT set height=100% in a flex column with a header ***
    // lv_obj_set_height(content, LV_PCT(100));  // remove this

    lv_obj_set_flex_grow(content, 1);
    lv_obj_set_flex_flow(content, LV_FLEX_FLOW_COLUMN);

    lv_obj_set_style_pad_all(content, 0, 0);
    lv_obj_set_style_pad_row(content, 0, 0);

    // If you don't need scrolling for the mesh demo, disable it (prevents odd offsets)
    lv_obj_set_scroll_dir(content, LV_DIR_NONE);

    return content;
}


// Build the File Explorer app into a new page and show it; adds a back button.
static void launch_file_explorer(AppCtx* app) {
    if (!app) return;
    if (app->home) lv_obj_add_flag(app->home, LV_OBJ_FLAG_HIDDEN);

    // Back callback closes the page and shows home
    struct BackCtx { AppCtx* app; pages::FileExplorerCtx* fx; };
    auto back_cb = [](lv_event_t* e) {
        BackCtx* b = static_cast<BackCtx*>(lv_event_get_user_data(e));
        if (!b) return;
        AppCtx* app = b->app;
        // Clean up page-specific resources (our ctx only, LVGL objects deleted with page)
        if (b->fx) { pages::destroy_file_explorer(b->fx); b->fx = nullptr; }
        // Show home first
        show_home(app);
        // Then delete the page; use delayed delete to be safe inside event context
        if (app && app->app_page) {
            lv_obj_t* page = app->app_page;
            app->app_page = nullptr;
            lv_obj_delete_delayed(page, 0);
        }
        delete b;
    };

    BackCtx* bctx = new BackCtx{app, nullptr};
    lv_obj_t* content = create_app_page_with_back(app, "File Explorer", back_cb, bctx);
    app->app_page = lv_obj_get_parent(content); // top-level page

    // Build explorer UI into content
    bctx->fx = pages::create_file_explorer(content, app->argc, app->argv);
}

// Create the Home screen: a scrollable list of app buttons
static void build_home(AppCtx* app) {
    if (!app) return;
    lv_obj_t* home = lv_list_create(app->root);
    lv_obj_set_size(home, LV_PCT(100), LV_PCT(100));
    lv_obj_set_flex_grow(home, 1);

    // Title text
    lv_list_add_text(home, "Apps");

    // File Explorer launcher button
    lv_obj_t* btn = lv_list_add_button(home, LV_SYMBOL_DIRECTORY, "File Explorer");
    lv_obj_add_event_cb(btn, [](lv_event_t* e){
        AppCtx* app = static_cast<AppCtx*>(lv_event_get_user_data(e));
        launch_file_explorer(app);
    }, LV_EVENT_CLICKED, app);

    // 3D Mesh Demo launcher button
    lv_obj_t* btn2 = lv_list_add_button(home, LV_SYMBOL_SHUFFLE, "3D Mesh Demo");
    lv_obj_add_event_cb(btn2, [](lv_event_t* e){
        AppCtx* app = static_cast<AppCtx*>(lv_event_get_user_data(e));
        // Hide home
        if (app->home) lv_obj_add_flag(app->home, LV_OBJ_FLAG_HIDDEN);
        // Back handler
        struct BackCtx { AppCtx* app; pages::MeshDemoCtx* md; };
        auto back_cb = [](lv_event_t* e){
            BackCtx* b = static_cast<BackCtx*>(lv_event_get_user_data(e));
            if (!b) return;
            AppCtx* app = b->app;
            if (b->md) { pages::destroy_mesh_demo(b->md); b->md = nullptr; }
            show_home(app);
            if (app && app->app_page) { lv_obj_t* page = app->app_page; app->app_page = nullptr; lv_obj_delete_delayed(page, 0); }
            delete b;
        };
        BackCtx* bctx = new BackCtx{app, nullptr};
        lv_obj_t* content = create_app_page_with_back(app, "3D Mesh", back_cb, bctx);
        app->app_page = lv_obj_get_parent(content);
        bctx->md = pages::create_mesh_demo(content);
    }, LV_EVENT_CLICKED, app);

    app->home = home;
}

int main(int argc, char** argv) {
    lv_init();
    fprintf(stderr, "[ui] lv_init done\n"); fflush(stderr);

    // Display + input
    lv_display_t* disp = nullptr;
#if defined(UI_PLATFORM_SDL)
    // SDL simulator (PC)
    disp = lv_sdl_window_create(480, 720);
    (void)lv_sdl_mouse_create();
    (void)lv_sdl_keyboard_create();

#elif defined(UI_PLATFORM_FBDEV)
    // Linux framebuffer (device)
    disp = lv_linux_fbdev_create();
    const char* fb = getenv("FBDEV");
    if (fb && *fb) lv_linux_fbdev_set_file(disp, fb);

    // Optional input via evdev (e.g., touch)
    const char* ev = getenv("EVDEV");
    if (!ev || !*ev) ev = "/dev/input/event0";
    (void)lv_evdev_create(LV_INDEV_TYPE_POINTER, ev);

#else
#   error "No platform selected. Enable UI_PLATFORM_SDL or UI_PLATFORM_FBDEV"
#endif
    if(!disp) {
        fprintf(stderr, "Failed to create LVGL display\n");
        return 1;
    }
    (void)disp;
    fprintf(stderr, "[ui] display + input ready\n"); fflush(stderr);

    // Root layout: column
    lv_obj_t* root = lv_screen_active();
    lv_obj_set_flex_flow(root, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_all(root, 0, 0);
    lv_obj_set_style_pad_row(root, 0, 0);

    // App context
    AppCtx app{};
    app.root = root;
    app.argc = argc;
    app.argv = argv;

    // Build and show home
    build_home(&app);
    fprintf(stderr, "[ui] home built\n"); fflush(stderr);

    // LVGL tick + loop
    lv_timer_create(tick_cb, 5, nullptr);
    while (true) {
        lv_timer_handler();
        usleep(5 * 1000);
    }
}
