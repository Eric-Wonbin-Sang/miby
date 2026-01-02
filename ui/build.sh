#!/usr/bin/env bash
set -e

TARGET="${1:-pc}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Prefer Ninja if available to avoid missing Makefiles generator
GEN_ARGS=()
GENERATOR_TAG="make"
if command -v ninja >/dev/null 2>&1; then
  GEN_ARGS+=("-G" "Ninja")
  GENERATOR_TAG="ninja"
fi

BUILD_DIR="$SCRIPT_DIR/build-${TARGET}-${GENERATOR_TAG}"

mkdir -p "$BUILD_DIR"

if [ "$TARGET" = "pc" ]; then
  cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" "${GEN_ARGS[@]}" -DUI_PLATFORM_SDL=ON
elif [ "$TARGET" = "device" ]; then
  cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" "${GEN_ARGS[@]}" \
    -DCMAKE_TOOLCHAIN_FILE=toolchain-mips.cmake \
    -DUI_PLATFORM_SDL=OFF \
    -DUI_PLATFORM_FBDEV=ON
else
  echo "Unknown target: $TARGET"
  exit 1
fi

cmake --build "$BUILD_DIR" -j
