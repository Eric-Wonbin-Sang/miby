from pathlib import Path
import shutil
from tools.miby_core.overlay_base import FirmwareOverlay
from tools.miby_core.status import StepResult
from tools.miby_core.dropbear import _dropbear_binary


class Overlay(FirmwareOverlay):
    name = "dropbear"

    def init_scripts(self) -> list[Path]:
        return [
            self.output_dir() / "etc" / "init.d" / "S95dropbear",
        ]

    def executable_files(self) -> list[Path]:
        return [
            self.output_dir() / "etc" / "init.d" / "S95dropbear",
            self.output_dir() / "usr" / "bin" / "dropbearmulti",
            self.output_dir() / "usr" / "bin" / "sshon",
            self.output_dir() / "usr" / "bin" / "sshoff",
        ]

    def build(self, public_key: str = None, **kwargs):
        out = self.output_dir()
        if not self.ctx.dry_run:
            self.clean_output()
            out.mkdir(parents=True, exist_ok=True)
        # copy any static files from files/ into overlay output
        self.copy_static_files()

        # copy built binary if present
        try:
            binary = Path(_dropbear_binary(self.ctx))
            if binary.exists():
                usr_bin = out / "usr" / "bin"
                usr_bin.mkdir(parents=True, exist_ok=True)
                shutil.copy2(binary, usr_bin / "dropbearmulti")
                (usr_bin / "dropbearmulti").chmod(0o755)
                for name in ["dropbear", "dropbearkey", "dbclient"]:
                    target = usr_bin / name
                    try:
                        if target.exists() or target.is_symlink():
                            target.unlink()
                        target.symlink_to("dropbearmulti")
                    except Exception:
                        pass
        except Exception:
            pass

        # authorized_keys.default
        etc_dropbear = out / "etc" / "dropbear"
        if public_key:
            pk = Path(public_key).expanduser()
            if pk.exists():
                etc_dropbear.mkdir(parents=True, exist_ok=True)
                etc_dropbear.joinpath('authorized_keys.default').write_text(pk.read_text(encoding='utf-8'), encoding='utf-8')

        # bake symlink in overlay root
        try:
            root_dir = out / "root"
            root_dir.mkdir(parents=True, exist_ok=True)
            target = Path('/usr/data/dropbear/root/.ssh')
            link = root_dir / '.ssh'
            if link.exists() or link.is_symlink():
                try:
                    link.unlink()
                except Exception:
                    pass
            link.symlink_to(target)
        except Exception:
            pass

        init_path = out / "etc" / "init.d" / "S95dropbear"
        init_path.chmod(0o755)

        return StepResult.done(f"build_overlay_{self.name}", f"Built overlay: {out}", paths=[out, init_path])

    def normalize_injected_rootfs(self, rootfs_dir: Path, runner) -> StepResult:
        commands = [
            ["chown", "root:root", rootfs_dir / "root"],
            ["chmod", "0755", rootfs_dir / "root"],
            ["chown", "-h", "root:root", rootfs_dir / "root/.ssh"],

            ["chown", "-R", "root:root", rootfs_dir / "etc/dropbear"],
            ["chmod", "0755", rootfs_dir / "etc/dropbear"],
            ["chmod", "0644", rootfs_dir / "etc/dropbear/authorized_keys.default"],

            ["chown", "root:root", rootfs_dir / "etc/init.d/S95dropbear"],
            ["chmod", "0755", rootfs_dir / "etc/init.d/S95dropbear"],

            ["chown", "root:root", rootfs_dir / "usr/bin/dropbearmulti"],
            ["chmod", "0755", rootfs_dir / "usr/bin/dropbearmulti"],

            ["chown", "-h", "root:root", rootfs_dir / "usr/bin/dropbear"],
            ["chown", "-h", "root:root", rootfs_dir / "usr/bin/dropbearkey"],
            ["chown", "-h", "root:root", rootfs_dir / "usr/bin/dbclient"],
        ]

        for cmd in commands:
            runner.run([str(x) for x in cmd], sudo=True)

        return StepResult.done(
            f"normalize_rootfs_{self.name}",
            "Normalized Dropbear rootfs permissions",
        )
