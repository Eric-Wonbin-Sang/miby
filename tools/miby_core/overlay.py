from pathlib import Path

from .command import CommandRunner, require_dir, require_file
from .context import FirmwareWorkspace, ProjectContext
from .status import StepResult


# Overlay semantics:
# A named overlay is a host-side directory under overlays/ that mirrors the
# device rootfs paths. The overlay contents are copied into the extracted rootfs
# tree before the image is rebuilt.


def resolve_overlay(ctx: ProjectContext, overlay_name_or_path: str) -> Path:
    """Resolve an overlay name or explicit directory path."""
    overlay_path = Path(overlay_name_or_path)
    if overlay_path.is_dir():
        return overlay_path
    candidate = ctx.overlays_dir / overlay_name_or_path
    if candidate.is_dir():
        return candidate
    raise FileNotFoundError(f"Overlay not found: {overlay_name_or_path}")


def inject_overlay(ctx: ProjectContext, firmware_name: str, overlay_name_or_path: str, force: bool = False) -> StepResult:
    runner = CommandRunner(ctx.dry_run)
    fw = FirmwareWorkspace.from_source(ctx, firmware_name)

    if not fw.rootfs_extracted_dir.exists():
        return StepResult.fail("inject_overlay", f"Rootfs extract missing: {fw.rootfs_extracted_dir}")

    try:
        overlay_dir = resolve_overlay(ctx, overlay_name_or_path)
    except Exception as exc:
        return StepResult.fail("inject_overlay", str(exc))

    if not overlay_dir.exists() or not overlay_dir.is_dir():
        return StepResult.fail("inject_overlay", f"Overlay path is not a directory: {overlay_dir}")

    # Use `cp -a` to preserve ownership, permissions, symlinks, and extended
    # attributes when copying the overlay into the extracted rootfs.

    try:
        runner.run(["cp", "-a", f"{str(overlay_dir)}/.", str(fw.rootfs_extracted_dir)], sudo=True)
        return StepResult.done("inject_overlay", f"Injected overlay {overlay_dir.name} into {fw.rootfs_extracted_dir}", paths=[fw.rootfs_extracted_dir])
    except Exception as exc:
        return StepResult.fail("inject_overlay", str(exc))
