import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class StepResult:
    """Standard result object for build system operations."""
    name: str
    ok: bool
    skipped: bool = False
    message: str = ""
    paths: List[Path] = field(default_factory=list)

    @classmethod
    def done(cls, name: str, message: str = "", paths: List[Path] = None) -> "StepResult":
        return cls(name=name, ok=True, skipped=False, message=message or "OK", paths=paths or [])

    @classmethod
    def skip(cls, name: str, message: str = "", paths: List[Path] = None) -> "StepResult":
        return cls(name=name, ok=True, skipped=True, message=message or "Skipped", paths=paths or [])

    @classmethod
    def fail(cls, name: str, message: str = "") -> "StepResult":
        return cls(name=name, ok=False, skipped=False, message=message or "Failed")


@dataclass
class FirmwareStatus:
    firmware_name: str
    source_exists: bool
    upt_extracted: bool
    ota_dir_exists: bool
    rootfs_joined: bool
    rootfs_extracted: bool
    bundle_exists: bool
    output_candidates: List[Path]
    injected_overlays: List[str] = field(default_factory=list)


@dataclass
class ProjectStatus:
    source_firmwares: List[Path]
    firmware_statuses: List[FirmwareStatus]
    dropbear_tarball_exists: bool
    dropbear_source_exists: bool
    dropbear_build_dir_exists: bool
    dropbear_binary_exists: bool
    dropbear_overlay_exists: bool
    dropbear_default_pubkey_exists: bool
    dropbear_root_ssh_symlink_valid: bool


def list_project_status(ctx) -> ProjectStatus:
    """Gather a summary of the current project and firmware workspace state."""
    source_firmwares = []
    if ctx.firmware_sources_dir.exists():
        source_firmwares = sorted(ctx.firmware_sources_dir.glob("*.upt"))

    firmware_statuses = []
    for firmware_path in source_firmwares:
        fw_name = firmware_path.name
        extracted_dir = ctx.work_dir / f"{fw_name}_extracted"
        bundle_dir = ctx.work_dir / f"{fw_name}_bundle"
        ota_dir = extracted_dir / "ota_v0"
        rootfs_image = ota_dir / "rootfs.squashfs"
        rootfs_extracted = ota_dir / "rootfs.squashfs_extracted"
        injected = []
        record_file = extracted_dir / ".miby_injected_overlays"
        if record_file.exists():
            try:
                injected = [l.strip() for l in record_file.read_text().splitlines() if l.strip()]
            except Exception:
                injected = []

        output_candidates = []
        if ctx.output_dir.exists():
            output_candidates = sorted(ctx.output_dir.glob(f"{firmware_path.stem}*_miby.upt"))

        firmware_statuses.append(
            FirmwareStatus(
                firmware_name=fw_name,
                source_exists=True,
                upt_extracted=extracted_dir.exists(),
                ota_dir_exists=ota_dir.exists(),
                rootfs_joined=rootfs_image.exists(),
                rootfs_extracted=rootfs_extracted.exists(),
                bundle_exists=bundle_dir.exists(),
                output_candidates=output_candidates,
                injected_overlays=injected,
            )
        )

    dropbear_base = ctx.tools_dir / "dropbear"
    tarball = dropbear_base / "dropbear-2026.91.tar.bz2"
    source_dir = dropbear_base / "dropbear-2026.91"
    build_dir = dropbear_base / "build-dropbear-mipsel-linux-gnu"
    binary = build_dir / "dropbearmulti"
    overlay = ctx.overlays_dir / "dropbear"
    pubkey = overlay / "etc/dropbear/authorized_keys.default"
    root_ssh = overlay / "root" / ".ssh"

    return ProjectStatus(
        source_firmwares=source_firmwares,
        firmware_statuses=firmware_statuses,
        dropbear_tarball_exists=tarball.exists(),
        dropbear_source_exists=source_dir.exists(),
        dropbear_build_dir_exists=build_dir.exists(),
        dropbear_binary_exists=binary.exists(),
        dropbear_overlay_exists=overlay.exists(),
        dropbear_default_pubkey_exists=pubkey.exists() and pubkey.stat().st_size > 0 if pubkey.exists() else False,
        dropbear_root_ssh_symlink_valid=root_ssh.is_symlink() and os.readlink(root_ssh) == "/usr/data/dropbear/root/.ssh",
    )


def print_project_status(status: ProjectStatus) -> None:
    print("Project status:")
    print("  firmware sources:")
    if status.source_firmwares:
        for source in status.source_firmwares:
            print(f"    - {source.relative_to(source.parent.parent)}")
    else:
        print("    - none")

    print("\n  firmware workspaces:")
    if status.firmware_statuses:
        for fw in status.firmware_statuses:
            print(f"    - {fw.firmware_name}")
            print(f"      source_exists: {fw.source_exists}")
            print(f"      extracted: {fw.upt_extracted}")
            print(f"      ota_v0: {fw.ota_dir_exists}")
            print(f"      rootfs joined: {fw.rootfs_joined}")
            print(f"      rootfs extracted: {fw.rootfs_extracted}")
            print(f"      bundle exists: {fw.bundle_exists}")
            print(f"      outputs: {', '.join(str(p.name) for p in fw.output_candidates) or 'none'}")
            print(f"      injected overlays: {', '.join(fw.injected_overlays) or 'none'}")
    else:
        print("    - none")

    print("\n  dropbear build state:")
    print(f"    tarball: {status.dropbear_tarball_exists}")
    print(f"    source: {status.dropbear_source_exists}")
    print(f"    build dir: {status.dropbear_build_dir_exists}")
    print(f"    binary: {status.dropbear_binary_exists}")
    print(f"    overlay: {status.dropbear_overlay_exists}")
    print(f"    authorized_keys.default: {status.dropbear_default_pubkey_exists}")
    print(f"    baked /root/.ssh symlink: {status.dropbear_root_ssh_symlink_valid}")
