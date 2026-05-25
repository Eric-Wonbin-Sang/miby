from pathlib import Path
from dataclasses import dataclass
import shutil
import os
from .status import StepResult


@dataclass
class OverlayBuildContext:
    project_ctx: object
    overlay_name: str
    source_dir: Path
    files_dir: Path
    output_dir: Path


class FirmwareOverlay:
    name: str = ""

    def __init__(self, ctx):
        self.ctx = ctx

    @classmethod
    def overlay_name(cls) -> str:
        return cls.name

    def source_dir(self) -> Path:
        return self.ctx.root_dir / "tools" / "overlays" / self.name

    def files_dir(self) -> Path:
        return self.source_dir() / "files"

    def output_dir(self) -> Path:
        return self.ctx.overlays_dir / self.name

    def init_scripts(self) -> list[Path]:
        return []

    def executable_files(self) -> list[Path]:
        return self.init_scripts()

    def clean_output(self) -> None:
        out = self.output_dir()
        if out.exists():
            shutil.rmtree(out)

    def copy_static_files(self) -> None:
        src = self.files_dir()
        dst = self.output_dir()
        if not src.exists():
            return
        dst.mkdir(parents=True, exist_ok=True)
        # Copy entire tree preserving symlinks and permissions
        try:
            shutil.copytree(src, dst, symlinks=True, dirs_exist_ok=True)
        except TypeError:
            # Python <3.8 fallback: walk manually
            for root, dirs, files in os.walk(src):
                rel = os.path.relpath(root, src)
                target_root = os.path.join(dst, rel) if rel != '.' else str(dst)
                os.makedirs(target_root, exist_ok=True)
                for d in dirs:
                    src_d = os.path.join(root, d)
                    dst_d = os.path.join(target_root, d)
                    if os.path.islink(src_d):
                        linkto = os.readlink(src_d)
                        try:
                            os.symlink(linkto, dst_d)
                        except Exception:
                            pass
                    else:
                        os.makedirs(dst_d, exist_ok=True)
                for f in files:
                    src_f = os.path.join(root, f)
                    dst_f = os.path.join(target_root, f)
                    if os.path.islink(src_f):
                        linkto = os.readlink(src_f)
                        try:
                            os.symlink(linkto, dst_f)
                        except Exception:
                            pass
                    else:
                        shutil.copy2(src_f, dst_f)

    def build(self, **kwargs) -> StepResult:
        out = self.output_dir()

        if not self.ctx.dry_run:
            self.clean_output()
            out.mkdir(parents=True, exist_ok=True)

        self.copy_static_files()

        post_result = self.post_build()
        if not post_result.ok:
            return post_result

        return StepResult.done(
            f"build_overlay_{self.name}",
            f"Built overlay: {out}",
            paths=[out, *post_result.paths],
        )

    def post_build(self) -> StepResult:
        for path in self.init_scripts():
            if not path.exists():
                return StepResult.fail(
                    f"post_build_{self.name}",
                    f"Expected init script missing: {path}",
                )

            if path.stat().st_size == 0:
                return StepResult.fail(
                    f"post_build_{self.name}",
                    f"Expected init script is empty: {path}",
                )

            path.chmod(0o755)

        return StepResult.done(
            f"post_build_{self.name}",
            "Overlay post-build checks passed",
            paths=self.init_scripts(),
        )

    def validate(self) -> StepResult:
        out = self.output_dir()
        if out.exists():
            return StepResult.done(f"validate_overlay_{self.name}", "OK", paths=[out])
        return StepResult.fail(f"validate_overlay_{self.name}", "Missing overlay output")

    def important_paths(self) -> list:
        return [self.output_dir()]
