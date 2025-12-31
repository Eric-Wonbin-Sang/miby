//
// Simple directory tree viewer with scrolling.
// - PC: uses SDL window/input
// - Device: uses Linux FBDEV
//

#include "lvgl.h"

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

struct UiRefs {
    lv_obj_t* ta_path;
    lv_obj_t* list;
};

static void rebuild_tree(UiRefs* ui, const char* path) {
    clear_children(ui->list);
    const char* md = getenv("UI_MAX_DEPTH");
    int max_depth = md ? atoi_default(md, 0) : 3; // default to 3 to avoid OOM
    TreeCtx ctx{ui->list, max_depth};
    // Root title
    {
        std::string title = std::string("Root: ") + path;
        lv_list_add_text(ui->list, title.c_str());
    }
    walk_dir(ctx, path, 1);
}

static void btn_go_event(lv_event_t* e) {
    UiRefs* ui = static_cast<UiRefs*>(lv_event_get_user_data(e));
    const char* p = lv_textarea_get_text(ui->ta_path);
    rebuild_tree(ui, p);
}

static void btn_up_event(lv_event_t* e) {
    UiRefs* ui = static_cast<UiRefs*>(lv_event_get_user_data(e));
    std::string p = lv_textarea_get_text(ui->ta_path);
    // remove trailing slash (except root)
    while (p.size() > 1 && p.back() == '/') p.pop_back();
    size_t pos = p.find_last_of('/');
    if (pos == std::string::npos) p = "/";
    else if (pos == 0) p = "/";
    else p.erase(pos);
    lv_textarea_set_text(ui->ta_path, p.c_str());
    rebuild_tree(ui, p.c_str());
}

static void btn_pc_event(lv_event_t* e) {
    UiRefs* ui = static_cast<UiRefs*>(lv_event_get_user_data(e));
    char buf[PATH_MAX] = {0};
    if (getcwd(buf, sizeof(buf) - 1) == nullptr) strncpy(buf, "/", sizeof(buf) - 1);
    lv_textarea_set_text(ui->ta_path, buf);
    rebuild_tree(ui, buf);
}

static void btn_dev_event(lv_event_t* e) {
    UiRefs* ui = static_cast<UiRefs*>(lv_event_get_user_data(e));
    const char* def = getenv("UI_DEVICE_PATH");
    if (!def || !*def) def = "/";
    lv_textarea_set_text(ui->ta_path, def);
    rebuild_tree(ui, def);
}

static std::string initial_path_from_args(int argc, char** argv) {
    // 1) --path=...
    for (int i = 1; i < argc; ++i) {
        const char* a = argv[i];
        static const char* k = "--path=";
        if (strncmp(a, k, strlen(k)) == 0) return std::string(a + strlen(k));
    }
    // 2) UI_START_PATH env
    const char* envp = getenv("UI_START_PATH");
    if (envp && *envp) return std::string(envp);
    // 3) CWD
    char buf[PATH_MAX] = {0};
    if (getcwd(buf, sizeof(buf) - 1)) return std::string(buf);
    return "/";
}

int main(int argc, char** argv) {
    lv_init();

    // Display + input
    lv_display_t* disp = nullptr;
#if defined(UI_PLATFORM_SDL)
    disp = lv_sdl_window_create(480, 720);
    (void)lv_sdl_mouse_create();
    (void)lv_sdl_keyboard_create();
#elif defined(UI_PLATFORM_FBDEV)
    disp = lv_linux_fbdev_create();
    const char* fb = getenv("FBDEV");
    if (fb && *fb) lv_linux_fbdev_set_file(disp, fb);
#else
    // Default to SDL if nothing specified
    disp = lv_sdl_window_create(480, 720);
    (void)lv_sdl_mouse_create();
    (void)lv_sdl_keyboard_create();
#endif
    (void)disp;

    // Root layout: column
    lv_obj_t* root = lv_screen_active();
    lv_obj_set_flex_flow(root, LV_FLEX_FLOW_COLUMN);
    lv_obj_set_style_pad_all(root, 8, 0);
    lv_obj_set_style_pad_row(root, 6, 0);

    // Header row: Path input + buttons
    UiRefs ui{};
    lv_obj_t* hdr = lv_obj_create(root);
    lv_obj_remove_style_all(hdr);
    lv_obj_set_flex_flow(hdr, LV_FLEX_FLOW_ROW);
    lv_obj_set_style_pad_column(hdr, 6, 0);
    lv_obj_set_width(hdr, LV_PCT(100));

    lv_obj_t* lbl = lv_label_create(hdr);
    lv_label_set_text(lbl, "Path:");

    ui.ta_path = lv_textarea_create(hdr);
    lv_textarea_set_one_line(ui.ta_path, true);
    lv_obj_set_flex_grow(ui.ta_path, 1);
    std::string init_path = initial_path_from_args(argc, argv);
    lv_textarea_set_text(ui.ta_path, init_path.c_str());

    lv_obj_t* btn_go = lv_button_create(hdr);
    lv_obj_t* btn_go_lbl = lv_label_create(btn_go);
    lv_label_set_text(btn_go_lbl, "Go");
    lv_obj_center(btn_go_lbl);
    lv_obj_add_event_cb(btn_go, btn_go_event, LV_EVENT_CLICKED, &ui);

    lv_obj_t* btn_up = lv_button_create(hdr);
    lv_obj_t* btn_up_lbl = lv_label_create(btn_up);
    lv_label_set_text(btn_up_lbl, "Up");
    lv_obj_center(btn_up_lbl);
    lv_obj_add_event_cb(btn_up, btn_up_event, LV_EVENT_CLICKED, &ui);

    lv_obj_t* btn_pc = lv_button_create(hdr);
    lv_obj_t* btn_pc_lbl = lv_label_create(btn_pc);
    lv_label_set_text(btn_pc_lbl, "PC");
    lv_obj_center(btn_pc_lbl);
    lv_obj_add_event_cb(btn_pc, btn_pc_event, LV_EVENT_CLICKED, &ui);

    lv_obj_t* btn_dev = lv_button_create(hdr);
    lv_obj_t* btn_dev_lbl = lv_label_create(btn_dev);
    lv_label_set_text(btn_dev_lbl, "Device");
    lv_obj_center(btn_dev_lbl);
    lv_obj_add_event_cb(btn_dev, btn_dev_event, LV_EVENT_CLICKED, &ui);

    // List container (scrollable)
    ui.list = lv_list_create(root);
    lv_obj_set_size(ui.list, LV_PCT(100), LV_PCT(100));
    lv_obj_set_flex_grow(ui.list, 1);

    // Build initial tree
    rebuild_tree(&ui, init_path.c_str());

    // LVGL tick + loop
    lv_timer_create(tick_cb, 5, nullptr);
    while (true) {
        lv_timer_handler();
        usleep(5 * 1000);
    }
}
