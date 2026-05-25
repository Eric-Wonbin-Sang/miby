from pathlib import Path
from tools.miby_core.overlay_base import FirmwareOverlay
from tools.miby_core.status import StepResult


class Overlay(FirmwareOverlay):
    name = "debug_predropbear"

    def build(self, **kwargs):
        out = self.output_dir()
        if not self.ctx.dry_run:
            self.clean_output()
            out.mkdir(parents=True, exist_ok=True)
        self.copy_static_files()

        init_path = out / "etc" / "init.d" / "S94miby_diag_predropbear"

        if not init_path.exists():
            return StepResult.fail(
                f"build_overlay_{self.name}",
                f"Expected debug init script missing after build: {init_path}"
            )

        init_path.chmod(0o755)

        return StepResult.done(f"build_overlay_{self.name}", f"Built overlay: {out}", paths=[out, init_path])
