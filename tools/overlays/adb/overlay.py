from pathlib import Path
from tools.miby_core.overlay_base import FirmwareOverlay
from tools.miby_core.status import StepResult


class Overlay(FirmwareOverlay):
    name = "adb"

    def build(self, **kwargs):
        out = self.output_dir()
        if not self.ctx.dry_run:
            self.clean_output()
            out.mkdir(parents=True, exist_ok=True)
        # copy static files from tools/overlays/adb/files into output
        self.copy_static_files()
        init_path = out / "etc" / "init.d" / "S91adb_enable"
        return StepResult.done(f"build_overlay_{self.name}", f"Built overlay: {out}", paths=[out, init_path])

    
