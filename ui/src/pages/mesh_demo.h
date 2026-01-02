// 3D Mesh demo page: rotating wireframe cube with FPS counter
#pragma once

#include "lvgl.h"

namespace pages {

struct MeshDemoCtx;

// Create the mesh demo UI inside `parent` and return its context.
MeshDemoCtx* create_mesh_demo(lv_obj_t* parent);

// Destroy resources allocated by create_mesh_demo. Does not delete `parent`.
void destroy_mesh_demo(MeshDemoCtx* ctx);

} // namespace pages

