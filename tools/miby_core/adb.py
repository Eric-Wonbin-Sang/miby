"""ADB overlay support for Hiby R3 Pro II custom firmware."""
import shutil
from pathlib import Path
from typing import List

from .command import CommandRunner, ensure_dir
from .overlay import inject_overlay
from .status import StepResult


def create_adb_overlay(ctx) -> StepResult:
    """Create an overlay that enables ADB on the device.
    
    The overlay creates init.d scripts that start the ADB service at boot.
    """
    overlay_dir = ctx.overlays_dir / "adb"

    if not ctx.dry_run and overlay_dir.exists():
        shutil.rmtree(overlay_dir)
    if not ctx.dry_run:
        overlay_dir.mkdir(parents=True, exist_ok=True)

    etc_init = overlay_dir / "etc" / "init.d"
    if not ctx.dry_run:
        etc_init.mkdir(parents=True, exist_ok=True)

    # Create a simple script to enable ADB at startup
    adb_init_script = etc_init / "S91adb_enable"
    adb_script_content = """#!/bin/sh
# Enable ADB daemon and log diagnostics
mkdir -p /usr/data/miby_logs >/dev/null 2>/dev/null || true
LOG=/usr/data/miby_logs/adb.log

echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [adb] enable requested" >> "$LOG" 2>/dev/null || true
setprop persist.sys.usb.config adb >/dev/null 2>&1 || echo "setprop failed" >> "$LOG" 2>/dev/null || true
/system/bin/adbd >> "$LOG" 2>&1 &
echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [adb] started" >> "$LOG" 2>/dev/null || true
exit 0
"""
    if not ctx.dry_run:
        adb_init_script.write_text(adb_script_content, encoding="utf-8")
        adb_init_script.chmod(0o755)

    return StepResult.done(
        "create_adb_overlay",
        f"Created ADB overlay: {overlay_dir}",
        paths=[overlay_dir],
    )


def inject_adb(ctx, firmware_name: str, force: bool = False) -> List[StepResult]:
    """Build and inject the ADB overlay into extracted firmware.
    
    This creates an ADB overlay and injects it into the extracted rootfs,
    enabling ADB access on the device.
    """
    results: List[StepResult] = []

    overlay_result = create_adb_overlay(ctx)
    results.append(overlay_result)

    if not overlay_result.ok:
        return results

    inject_result = inject_overlay(ctx, firmware_name, "adb", force=force)
    results.append(inject_result)

    return results
