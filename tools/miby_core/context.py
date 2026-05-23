from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectContext:
    """Repository-wide configuration and standard layout paths."""
    root_dir: Path
    firmware_sources_dir: Path
    work_dir: Path
    output_dir: Path
    overlays_dir: Path
    tools_dir: Path
    dry_run: bool = False

    @classmethod
    def from_root(cls, root_dir: Path, dry_run: bool = False) -> "ProjectContext":
        """Create a project context from the repository root.

        This collapses the build system layout into a single object for all
        commands and helpers.
        """
        root_dir = root_dir.resolve()
        return cls(
            root_dir=root_dir,
            firmware_sources_dir=root_dir / "firmware" / "sources",
            work_dir=root_dir / "work",
            output_dir=root_dir / "output",
            overlays_dir=root_dir / "overlays",
            tools_dir=root_dir / "work" / "tools",
            dry_run=dry_run,
        )


@dataclass(frozen=True)
class FirmwareWorkspace:
    """Firmware-specific workspace paths for a given source UPT."""
    source_path: Path
    extracted_dir: Path
    bundle_dir: Path
    ota_dir: Path
    ota_update_path: Path
    rootfs_image_path: Path
    rootfs_extracted_dir: Path

    @classmethod
    def from_source(cls, ctx: ProjectContext, firmware_name: str) -> "FirmwareWorkspace":
        source_path = ctx.firmware_sources_dir / firmware_name
        extracted_dir = ctx.work_dir / f"{firmware_name}_extracted"
        bundle_dir = ctx.work_dir / f"{firmware_name}_bundle"
        ota_dir = extracted_dir / "ota_v0"
        return cls(
            source_path=source_path,
            extracted_dir=extracted_dir,
            bundle_dir=bundle_dir,
            ota_dir=ota_dir,
            ota_update_path=ota_dir / "ota_update.in",
            rootfs_image_path=ota_dir / "rootfs.squashfs",
            rootfs_extracted_dir=ota_dir / "rootfs.squashfs_extracted",
        )
