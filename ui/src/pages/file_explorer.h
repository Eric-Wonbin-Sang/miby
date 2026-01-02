// Simple File Explorer page API
#pragma once

#include "lvgl.h"

namespace pages {

struct FileExplorerCtx;

// Create the File Explorer UI inside `parent` and return its context.
// `argc/argv` are used to determine the initial path.
FileExplorerCtx* create_file_explorer(lv_obj_t* parent, int argc, char** argv);

// Destroy resources allocated by create_file_explorer. Does not delete `parent`.
void destroy_file_explorer(FileExplorerCtx* ctx);

} // namespace pages

