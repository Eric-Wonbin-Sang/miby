#!/usr/bin/env bash
set -e

TARGET="${1:-pc}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build-$TARGET"

mkdir -p "$BUILD_DIR"

if [ "$TARGET" = "pc" ]; then
  cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" -DUI_PLATFORM_SDL=ON
elif [ "$TARGET" = "device" ]; then
  cmake -S "$SCRIPT_DIR" -B "$BUILD_DIR" \
    -DCMAKE_TOOLCHAIN_FILE=toolchain-mips.cmake \
    -DUI_PLATFORM_FBDEV=ON
else
  echo "Unknown target: $TARGET"
  exit 1
fi

cmake --build "$BUILD_DIR" -j
