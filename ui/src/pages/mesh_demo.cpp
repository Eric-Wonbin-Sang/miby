// Rotating 3D wireframe cube rendered to an LVGL canvas with FPS counter

#include "mesh_demo.h"
#include <cmath>
#include <vector>
#include <string>

namespace pages {

struct MeshDemoCtx {
    lv_obj_t* canvas{};
    lv_draw_buf_t* draw_buf{};
    lv_obj_t* fps_label{};
    lv_timer_t* timer{};
    int w{0};
    int h{0};
    float angle{0.0f};
    // FPS state
    uint32_t last_ts{0};
    uint32_t frames{0};
};

static void ensure_buf(MeshDemoCtx* ctx) {
    if (!ctx || !ctx->canvas) return;
    int w = lv_obj_get_width(ctx->canvas);
    int h = lv_obj_get_height(ctx->canvas);
    if (w <= 0 || h <= 0) return;
    if (w == ctx->w && h == ctx->h && ctx->draw_buf) return;
    if (ctx->draw_buf) { lv_draw_buf_destroy(ctx->draw_buf); ctx->draw_buf = nullptr; }
    ctx->draw_buf = lv_draw_buf_create(w, h, LV_COLOR_FORMAT_RGB565, LV_STRIDE_AUTO);
    lv_canvas_set_draw_buf(ctx->canvas, ctx->draw_buf);
    ctx->w = w; ctx->h = h;
}

static void render_cube(MeshDemoCtx* ctx) {
    if (!ctx) return;
    // Clear background
    lv_canvas_fill_bg(ctx->canvas, lv_color_black(), LV_OPA_COVER);

    // Prepare drawing layer
    lv_layer_t layer;
    lv_canvas_init_layer(ctx->canvas, &layer);

    // Cube vertices (-1..1)
    struct V3 { float x,y,z; };
    static const V3 verts[8] = {
        {-1,-1,-1}, {1,-1,-1}, {1,1,-1}, {-1,1,-1},
        {-1,-1, 1}, {1,-1, 1}, {1,1, 1}, {-1,1, 1}
    };
    static const int edges[12][2] = {
        {0,1},{1,2},{2,3},{3,0}, // back
        {4,5},{5,6},{6,7},{7,4}, // front
        {0,4},{1,5},{2,6},{3,7}  // sides
    };

    float a = ctx->angle;
    float ca = std::cos(a), sa = std::sin(a);
    float cb = std::cos(a*0.7f), sb = std::sin(a*0.7f);

    // Projected 2D points
    std::vector<lv_point_t> pts(8);
    float scale = (ctx->w < ctx->h ? ctx->w : ctx->h) * 0.8f;
    float cx = ctx->w * 0.5f, cy = ctx->h * 0.5f;
    for (int i=0;i<8;i++) {
        // Rotate around X then Y
        float x = verts[i].x;
        float y = verts[i].y;
        float z = verts[i].z;
        // X
        float y1 = y*ca - z*sa;
        float z1 = y*sa + z*ca;
        // Y
        float x2 = x*cb + z1*sb;
        float z2 = -x*sb + z1*cb;
        float d = z2 + 3.5f; // push forward
        float px = (x2 / d) * scale + cx;
        float py = (y1 / d) * scale + cy;
        pts[i].x = static_cast<lv_coord_t>(px);
        pts[i].y = static_cast<lv_coord_t>(py);
    }

    // Draw edges
    lv_draw_line_dsc_t ld; lv_draw_line_dsc_init(&ld);
    ld.color = lv_color_white();
    ld.width = 2;
    ld.opa = LV_OPA_COVER;
    for (auto &e : edges) {
        ld.p1.x = pts[e[0]].x; ld.p1.y = pts[e[0]].y;
        ld.p2.x = pts[e[1]].x; ld.p2.y = pts[e[1]].y;
        lv_draw_line(&layer, &ld);
    }

    lv_canvas_finish_layer(ctx->canvas, &layer);
}

static void timer_cb(lv_timer_t* t) {
    auto* ctx = static_cast<MeshDemoCtx*>(lv_timer_get_user_data(t));
    if (!ctx) return;
    ctx->angle += 0.03f;
    render_cube(ctx);

    // FPS calc
    ctx->frames++;
    uint32_t now = lv_tick_get();
    if (ctx->last_ts == 0) ctx->last_ts = now;
    uint32_t dt = now - ctx->last_ts;
    if (dt >= 1000) {
        float fps = (ctx->frames * 1000.0f) / (float)dt;
        char buf[64];
        snprintf(buf, sizeof(buf), "FPS: %.1f", fps);
        lv_label_set_text(ctx->fps_label, buf);
        ctx->frames = 0;
        ctx->last_ts = now;
    }
}

MeshDemoCtx* create_mesh_demo(lv_obj_t* parent) {
    auto* ctx = new MeshDemoCtx();

    // Canvas fills the content area
    // ctx->canvas = lv_canvas_create(parent);
    // lv_obj_set_size(ctx->canvas, LV_PCT(100), LV_PCT(100));
    // lv_obj_set_flex_grow(ctx->canvas, 1);

    ctx->canvas = lv_canvas_create(parent);
    lv_obj_set_width(ctx->canvas, LV_PCT(100));
    lv_obj_set_flex_grow(ctx->canvas, 1);
    // lv_obj_set_height(ctx->canvas, LV_PCT(100)); // don't


    // FPS label as sibling overlay in bottom-right of content, white text
    ctx->fps_label = lv_label_create(parent);
    lv_label_set_text(ctx->fps_label, "FPS: --");
    lv_obj_set_style_text_color(ctx->fps_label, lv_color_white(), 0);
    // IMPORTANT: exclude from flex layout
    lv_obj_add_flag(ctx->fps_label, LV_OBJ_FLAG_FLOATING);
    lv_obj_align(ctx->fps_label, LV_ALIGN_BOTTOM_RIGHT, -6, -6);

    // React to size changes to resize canvas buffer
    lv_obj_add_event_cb(ctx->canvas, [](lv_event_t* e){
        auto* c = static_cast<MeshDemoCtx*>(lv_event_get_user_data(e));
        if (!c) return;
        ensure_buf(c);
        render_cube(c);
    }, LV_EVENT_SIZE_CHANGED, ctx);

    // Initial buffer setup
    ensure_buf(ctx);

    // Timer ~60 FPS
    ctx->timer = lv_timer_create(timer_cb, 16, ctx);

    // Initial render
    render_cube(ctx);

    return ctx;
}

void destroy_mesh_demo(MeshDemoCtx* ctx) {
    if (!ctx) return;
    if (ctx->timer) { lv_timer_delete(ctx->timer); ctx->timer = nullptr; }
    if (ctx->draw_buf) { lv_draw_buf_destroy(ctx->draw_buf); ctx->draw_buf = nullptr; }
    delete ctx;
}

} // namespace pages
