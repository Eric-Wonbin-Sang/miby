import re
import shutil
from pathlib import Path
from typing import List

from .command import CommandRunner, ensure_dir, remove_path, require_dir, require_file
from .context import FirmwareWorkspace, ProjectContext
from .rootfs import update_ota_update_file, get_file_md5, mksquashfs_rootfs, remove_old_rootfs_bundle_files, split_rootfs_to_chunks
from .status import StepResult


def list_source_firmwares(ctx: ProjectContext) -> List[Path]:
    if not ctx.firmware_sources_dir.exists():
        return []
    return sorted(ctx.firmware_sources_dir.glob("*.upt"))


def extract_upt(ctx: ProjectContext, firmware_name: str, force: bool = False) -> StepResult:
    """Extract a source UPT into a workspace directory."""
    runner = CommandRunner(ctx.dry_run)
    fw = FirmwareWorkspace.from_source(ctx, firmware_name)

    if not fw.source_path.exists():
        return StepResult.fail("extract_upt", f"Source firmware missing: {fw.source_path}")

    if fw.extracted_dir.exists():
        if force:
            remove_path(fw.extracted_dir, runner, sudo=True)
        else:
            return StepResult.skip("extract_upt", "Extraction already exists")

    try:
        cmd = ["7z", "x", str(fw.source_path), f"-o{str(fw.extracted_dir)}", "-y"]
        runner.run(cmd)
        return StepResult.done("extract_upt", f"Extracted {firmware_name}", paths=[fw.extracted_dir])
    except Exception as exc:
        return StepResult.fail("extract_upt", str(exc))


def join_rootfs_chunks(ctx: ProjectContext, firmware_name: str, force: bool = False) -> StepResult:
    """Concatenate OTA rootfs chunks into a single SquashFS image."""
    runner = CommandRunner(ctx.dry_run)
    fw = FirmwareWorkspace.from_source(ctx, firmware_name)

    if not fw.ota_dir.exists():
        return StepResult.fail("join_rootfs_chunks", f"OTA directory missing: {fw.ota_dir}")

    pattern = re.compile(r"^rootfs\.squashfs\.(\d{4})\..+$")
    chunks = [p for p in fw.ota_dir.iterdir() if p.is_file() and pattern.match(p.name)]
    if not chunks:
        return StepResult.fail("join_rootfs_chunks", "No rootfs chunk files found")

    def chunk_index(path: Path) -> int:
        match = pattern.match(path.name)
        return int(match.group(1)) if match else 0

    chunks = sorted(chunks, key=chunk_index)

    if fw.rootfs_image_path.exists():
        if force:
            remove_path(fw.rootfs_image_path, runner, sudo=True)
        else:
            return StepResult.skip("join_rootfs_chunks", "Rootfs image already joined")

    try:
        ensure_dir(fw.rootfs_image_path.parent)
        with fw.rootfs_image_path.open("wb") as target:
            for chunk in chunks:
                with chunk.open("rb") as source:
                    shutil.copyfileobj(source, target)
        return StepResult.done("join_rootfs_chunks", f"Joined {len(chunks)} rootfs chunks", paths=[fw.rootfs_image_path])
    except Exception as exc:
        return StepResult.fail("join_rootfs_chunks", str(exc))


def extract_rootfs(ctx: ProjectContext, firmware_name: str, force: bool = False) -> StepResult:
    """Extract the concatenated SquashFS image into a temporary rootfs tree."""
    runner = CommandRunner(ctx.dry_run)
    fw = FirmwareWorkspace.from_source(ctx, firmware_name)

    if not fw.rootfs_image_path.exists():
        return StepResult.fail("extract_rootfs", f"Rootfs image missing: {fw.rootfs_image_path}")

    if fw.rootfs_extracted_dir.exists():
        if force:
            remove_path(fw.rootfs_extracted_dir, runner, sudo=True)
        else:
            return StepResult.skip("extract_rootfs", "Rootfs already extracted")

    try:
        runner.run(["unsquashfs", "-d", str(fw.rootfs_extracted_dir), str(fw.rootfs_image_path)], sudo=True)
        return StepResult.done("extract_rootfs", f"Extracted rootfs to {fw.rootfs_extracted_dir}", paths=[fw.rootfs_extracted_dir])
    except Exception as exc:
        return StepResult.fail("extract_rootfs", str(exc))


def extract_firmware(ctx: ProjectContext, firmware_name: str, force: bool = False) -> List[StepResult]:
    results: List[StepResult] = []
    steps = [
        extract_upt(ctx, firmware_name, force=force),
        join_rootfs_chunks(ctx, firmware_name, force=force),
        extract_rootfs(ctx, firmware_name, force=force),
    ]
    for result in steps:
        results.append(result)
        if not result.ok:
            break
    return results


def pack_firmware(ctx: ProjectContext, firmware_name: str, output_name: str = None, force: bool = False) -> List[StepResult]:
    """Bundle modified firmware back into a custom UPT image."""
    runner = CommandRunner(ctx.dry_run)
    fw = FirmwareWorkspace.from_source(ctx, firmware_name)
    results: List[StepResult] = []

    if not fw.rootfs_extracted_dir.exists():
        return [StepResult.fail("pack_firmware", f"Rootfs extracted directory missing: {fw.rootfs_extracted_dir}")]

    ensure_dir(ctx.output_dir)
    # The bundle dir is recreated every pack to ensure the output image is built
    # from a clean copy of the extracted firmware workspace.

    if fw.bundle_dir.exists():
        if force:
            remove_path(fw.bundle_dir, runner, sudo=True)
        else:
            if any(fw.bundle_dir.iterdir()):
                return [StepResult.fail("pack_firmware", f"Bundle exists: {fw.bundle_dir}. Use --force to rebuild")]
            remove_path(fw.bundle_dir, runner, sudo=True)

    ensure_dir(fw.bundle_dir)

    try:
        runner.run(["cp", "-a", f"{str(fw.extracted_dir)}/.", str(fw.bundle_dir)], sudo=True)
    except Exception as exc:
        return [StepResult.fail("pack_firmware", f"Failed copying bundle directory: {exc}")]

    ota_bundle_dir = fw.bundle_dir / "ota_v0"
    remove_result = remove_old_rootfs_bundle_files(ota_bundle_dir, runner)
    results.append(remove_result)
    if not remove_result.ok:
        return results

    squashfs_path = ota_bundle_dir / "rootfs.squashfs"
    mksq_result = mksquashfs_rootfs(fw.rootfs_extracted_dir, squashfs_path, runner)
    results.append(mksq_result)
    if not mksq_result.ok:
        return results

    chunk_list = []
    if not ctx.dry_run:
        try:
            img_md5 = get_file_md5(squashfs_path)
            chunk_list = split_rootfs_to_chunks(squashfs_path, 524288, img_md5, runner)
        except Exception as exc:
            return results + [StepResult.fail("pack_firmware", str(exc))]
    else:
        chunk_list = []

    if not ctx.dry_run:
        remove_path(squashfs_path, runner)

    update_result = update_ota_update_file(ota_bundle_dir, ota_bundle_dir / "ota_update.in", dry_run=ctx.dry_run)
    results.append(update_result)
    if not update_result.ok:
        return results

    output_name = output_name or f"{fw.source_path.stem}_miby.upt"
    output_path = ctx.output_dir / output_name

    try:
        runner.run(["genisoimage", "-o", str(output_path), "-V", "CDROM", "-J", "-r", str(fw.bundle_dir)])
        results.append(StepResult.done("pack_firmware", f"Packed firmware to {output_path}", paths=[output_path]))
    except Exception as exc:
        results.append(StepResult.fail("pack_firmware", str(exc)))

    return results
