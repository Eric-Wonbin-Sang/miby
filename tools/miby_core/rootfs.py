import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import List

from .command import CommandRunner, remove_path, require_dir
from .status import StepResult


def get_file_md5(path: Path) -> str:
    """Compute an MD5 hash for a file using streaming reads."""
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def mksquashfs_rootfs(source_dir: Path, output_path: Path, runner: CommandRunner) -> StepResult:
    """Create a SquashFS image from the extracted rootfs directory."""
    if not source_dir.exists() or not source_dir.is_dir():
        return StepResult.fail("mksquashfs_rootfs", f"Source directory missing: {source_dir}")
    try:
        if not runner.dry_run:
            ensure_parent = output_path.parent
            ensure_parent.mkdir(parents=True, exist_ok=True)
        runner.run(
            [
                "mksquashfs",
                str(source_dir),
                str(output_path),
                "-comp",
                "lzo",
                "-b",
                "131072",
                "-noappend",
                "-xattrs",
                "-exports",
                "-no-tailends",
            ],
            sudo=True,
        )
        return StepResult.done("mksquashfs_rootfs", f"Created SquashFS image: {output_path}", paths=[output_path])
    except Exception as exc:
        return StepResult.fail("mksquashfs_rootfs", str(exc))


def split_rootfs_to_chunks(path: Path, bytes_per_chunk: int, img_md5: str, runner: CommandRunner) -> List[str]:
    """Split a SquashFS image into numbered chunks and write MD5 metadata."""
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(f"Rootfs image missing: {path}")

    chunk_hashes: List[str] = []
    chunk_paths: List[Path] = []
    directory = path.parent

    # Read the SquashFS image in fixed-size chunks so the resulting names and
    # MD5 chain match the device's OTA update format.
    with path.open("rb") as source:
        index = 0
        while True:
            data = source.read(bytes_per_chunk)
            if not data:
                break
            chunk_name = f"{path.name}.{index:04d}"
            chunk_path = directory / chunk_name
            with chunk_path.open("wb") as chunk_file:
                chunk_file.write(data)
            chunk_paths.append(chunk_path)
            chunk_hashes.append(hashlib.md5(data).hexdigest())
            index += 1

    if not chunk_paths:
        raise RuntimeError("No chunks created from rootfs")

    for idx, chunk in enumerate(chunk_paths):
        suffix = img_md5 if idx == 0 else chunk_hashes[idx - 1]
        renamed = chunk.with_name(f"{chunk.name}.{suffix}")
        chunk.rename(renamed)
        chunk_paths[idx] = renamed

    md5_list_path = directory / f"ota_md5_{path.name}.{img_md5}"
    if not runner.dry_run:
        md5_list_path.write_text("\n".join(chunk_hashes) + "\n", encoding="utf-8")

    return chunk_hashes


def update_ota_update_file(chunks_dir: Path, ota_update_file: Path, dry_run: bool = False) -> StepResult:
    """Update ota_update.in with the new rootfs chunk size and MD5 chain."""
    if not chunks_dir.exists() or not chunks_dir.is_dir():
        return StepResult.fail("update_ota_update_file", f"Chunks directory missing: {chunks_dir}")
    if not ota_update_file.exists() or not ota_update_file.is_file():
        return StepResult.fail("update_ota_update_file", f"OTA update file missing: {ota_update_file}")

    with ota_update_file.open("r", encoding="utf-8") as fh:
        lines = fh.read().splitlines()

    data_dicts = []
    current = {}
    for line in lines:
        if not line.strip():
            if current:
                data_dicts.append(current)
                current = {}
            continue
        if "=" in line:
            key, value = line.split("=", 1)
            current[key] = value
    if current:
        data_dicts.append(current)

    chunks = sorted(
        [p for p in chunks_dir.glob("rootfs.squashfs.*.*") if p.is_file()],
        key=lambda p: int(p.name.split(".")[-2]) if len(p.name.split(".")) >= 3 else 0,
    )
    if not chunks:
        return StepResult.fail("update_ota_update_file", "No rootfs chunk files found for update")

    img_size = sum(p.stat().st_size for p in chunks)
    img_md5 = chunks[0].name.split(".")[-1]

    output_lines: List[str] = []
    for data in data_dicts:
        if data.get("img_type") == "rootfs":
            data["img_size"] = str(img_size)
            data["img_md5"] = str(img_md5)
        for key, value in data.items():
            output_lines.append(f"{key}={value}")
        output_lines.append("")

    if not dry_run:
        ota_update_file.write_text("\n".join(output_lines).rstrip() + "\n", encoding="utf-8")

    return StepResult.done("update_ota_update_file", f"Updated {ota_update_file}", paths=[ota_update_file])


def remove_old_rootfs_bundle_files(bundle_ota_dir: Path, runner: CommandRunner) -> StepResult:
    if not bundle_ota_dir.exists() or not bundle_ota_dir.is_dir():
        return StepResult.fail("remove_old_rootfs_bundle_files", f"Bundle OTA directory missing: {bundle_ota_dir}")

    old_paths = []
    old_paths.extend(bundle_ota_dir.glob("rootfs.squashfs.*.*"))
    old_paths.extend(bundle_ota_dir.glob("ota_md5_rootfs.squashfs.*"))
    rootfs_image = bundle_ota_dir / "rootfs.squashfs"
    rootfs_extracted = bundle_ota_dir / "rootfs.squashfs_extracted"
    old_paths.append(rootfs_image)
    if rootfs_extracted.exists():
        old_paths.append(rootfs_extracted)

    for path in old_paths:
        remove_path(path, runner, sudo=True)

    return StepResult.done("remove_old_rootfs_bundle_files", f"Removed {len(old_paths)} old rootfs bundle artifacts")
