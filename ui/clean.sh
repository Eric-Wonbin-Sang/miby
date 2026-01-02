#!/usr/bin/env bash
set -e
UI_DIR="$(cd "$(dirname "$0")" && pwd)"
rm -rf "$UI_DIR"/build-pc "$UI_DIR"/build-device || true
rm -rf "$UI_DIR"/build-pc-* "$UI_DIR"/build-device-* || true
echo "Cleaned UI build directories."
