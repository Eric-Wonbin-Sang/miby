from pathlib import Path
from tools.miby_core.overlay_base import FirmwareOverlay
from tools.miby_core.status import StepResult


class Overlay(FirmwareOverlay):
    name = "adb"

    def init_scripts(self) -> list[Path]:
        return [
            self.output_dir() / "etc" / "init.d" / "S91adb_enable",
        ]

    def build(self, **kwargs):
        out = self.output_dir()
        if not self.ctx.dry_run:
            self.clean_output()
            out.mkdir(parents=True, exist_ok=True)
        # copy static files from tools/overlays/adb/files into output
        self.copy_static_files()

        init_path = out / "etc" / "init.d" / "S91adb_enable"
        init_path.chmod(0o755)

        return StepResult.done(f"build_overlay_{self.name}", f"Built overlay: {out}", paths=[out, init_path])

    def normalize_injected_rootfs(self, rootfs_dir: Path, runner) -> StepResult:
        script = rootfs_dir / "etc/init.d/S91adb_enable"

        if script.exists():
            runner.run(["chown", "root:root", str(script)], sudo=True)
            runner.run(["chmod", "0755", str(script)], sudo=True)

        return StepResult.done(
            f"normalize_rootfs_{self.name}",
            "Normalized ADB rootfs permissions",
        )
