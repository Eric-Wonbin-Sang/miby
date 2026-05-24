import os
import shutil
import subprocess
import tarfile
from pathlib import Path
from typing import List, Optional
from string import Template

from .command import CommandRunner, ensure_dir, require_tool
from .overlay import inject_overlay
from .status import StepResult

DROPBEAR_VERSION = "2026.91"
DROPBEAR_TARBALL = f"dropbear-{DROPBEAR_VERSION}.tar.bz2"
DROPBEAR_URLS = [
    f"https://matt.ucc.asn.au/dropbear/releases/{DROPBEAR_TARBALL}",
    f"https://download.savannah.gnu.org/releases/dropbear/{DROPBEAR_TARBALL}",
]
HOST = "mipsel-linux-gnu"
CC = "mipsel-linux-gnu-gcc"


def _dropbear_base(ctx) -> Path:
    return ctx.tools_dir / "dropbear"


def _dropbear_tarball(ctx) -> Path:
    return _dropbear_base(ctx) / DROPBEAR_TARBALL


def _dropbear_source_dir(ctx) -> Path:
    return _dropbear_base(ctx) / f"dropbear-{DROPBEAR_VERSION}"


def _dropbear_build_dir(ctx) -> Path:
    return _dropbear_base(ctx) / f"build-dropbear-{HOST}"


def _dropbear_binary(ctx) -> Path:
    return _dropbear_build_dir(ctx) / "dropbearmulti"


def download_dropbear_source(ctx, redownload_source: bool = False) -> StepResult:
    runner = CommandRunner(ctx.dry_run)
    tarball = _dropbear_tarball(ctx)
    base = _dropbear_base(ctx)
    ensure_dir(base)

    if tarball.exists() and not redownload_source:
        return StepResult.skip("download_dropbear_source", f"Tarball already exists: {tarball}")

    local_candidate = ctx.root_dir / DROPBEAR_TARBALL
    if local_candidate.exists():
        if not ctx.dry_run:
            shutil.copy2(local_candidate, tarball)
        return StepResult.done("download_dropbear_source", f"Copied local tarball to {tarball}", paths=[tarball])

    import urllib.request

    last_error: Optional[str] = None
    for url in DROPBEAR_URLS:
        try:
            print(f"Downloading {url}")
            if ctx.dry_run:
                return StepResult.done("download_dropbear_source", f"Would download {url}")
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as response:
                with tarball.open("wb") as out_file:
                    shutil.copyfileobj(response, out_file)
            return StepResult.done("download_dropbear_source", f"Downloaded {tarball}", paths=[tarball])
        except Exception as exc:
            last_error = str(exc)
            print(f"Download failed: {exc}")
    return StepResult.fail("download_dropbear_source", f"All downloads failed: {last_error}")


def extract_dropbear_source(ctx, force: bool = False) -> StepResult:
    tarball = _dropbear_tarball(ctx)
    source_dir = _dropbear_source_dir(ctx)
    base = _dropbear_base(ctx)
    ensure_dir(base)

    if source_dir.exists():
        if force:
            shutil.rmtree(source_dir)
        else:
            return StepResult.skip("extract_dropbear_source", f"Source already extracted: {source_dir}")

    if not tarball.exists():
        return StepResult.fail("extract_dropbear_source", f"Tarball missing: {tarball}")

    if ctx.dry_run:
        return StepResult.done("extract_dropbear_source", f"Would extract {tarball}")

    try:
        with tarfile.open(tarball, "r:bz2") as archive:
            archive.extractall(path=base)
        return StepResult.done("extract_dropbear_source", f"Extracted {source_dir}", paths=[source_dir])
    except Exception as exc:
        return StepResult.fail("extract_dropbear_source", str(exc))


def verify_dropbear_binary(binary: Path) -> None:
    if not binary.exists():
        raise FileNotFoundError(f"Dropbear binary missing: {binary}")

    file_proc = subprocess.run(["file", str(binary)], capture_output=True, text=True)
    readelf_proc = subprocess.run(["mipsel-linux-gnu-readelf", "-h", str(binary)], capture_output=True, text=True)
    if file_proc.returncode != 0:
        raise RuntimeError(f"file command failed: {file_proc.stderr}")
    if readelf_proc.returncode != 0:
        raise RuntimeError(f"readelf command failed: {readelf_proc.stderr}")

    file_output = file_proc.stdout.lower()
    readelf_output = readelf_proc.stdout.lower()
    if "x86-64" in file_output or "intel" in file_output:
        raise RuntimeError("Built binary is not MIPS")
    if "mips" not in file_output and "mips" not in readelf_output:
        raise RuntimeError("Built binary does not identify as MIPS")
    if "elf 64-bit" in file_output:
        raise RuntimeError("Built binary is ELF64")
    if "lsb" not in file_output:
        raise RuntimeError("Built binary is not little-endian")


def _write_localoptions(build_dir: Path) -> None:
    contents = """#ifndef LOCALOPTIONS_H
#define LOCALOPTIONS_H
#define DROPBEAR_SVR_PASSWORD_AUTH 0
#define DROPBEAR_SVR_PAM_AUTH 0
#define DROPBEAR_SVR_PUBKEY_AUTH 1
#define DROPBEAR_CLI_PASSWORD_AUTH 0
#define DROPBEAR_CLI_PUBKEY_AUTH 1
#define DROPBEAR_X11FWD 0
#define DROPBEAR_AGENTFWD 0
#define DROPBEAR_TCP_ACCEPT 0
#define DROPBEAR_CLI_LOCALTCPFWD 0
#define DROPBEAR_CLI_REMOTETCPFWD 0
#endif
"""
    (build_dir / "localoptions.h").write_text(contents, encoding="utf-8")


def build_dropbear(ctx, force: bool = False, redownload_source: bool = False) -> StepResult:
    runner = CommandRunner(ctx.dry_run)
    for tool in ["make", "file", CC, "mipsel-linux-gnu-readelf"]:
        try:
            require_tool(tool)
        except FileNotFoundError as exc:
            return StepResult.fail("build_dropbear", str(exc))

    download_result = download_dropbear_source(ctx, redownload_source=redownload_source)
    if not download_result.ok:
        return download_result

    extract_result = extract_dropbear_source(ctx, force=force)
    if not extract_result.ok:
        return extract_result

    binary = _dropbear_binary(ctx)
    build_dir = _dropbear_build_dir(ctx)
    source_dir = _dropbear_source_dir(ctx)

    if binary.exists() and not force:
        try:
            verify_dropbear_binary(binary)
            return StepResult.skip("build_dropbear", "Dropbear binary already built and verified", paths=[binary])
        except Exception as exc:
            return StepResult.fail("build_dropbear", str(exc))

    if build_dir.exists():
        if ctx.dry_run:
            print(f"(DRY) Would remove build directory {build_dir}")
        else:
            shutil.rmtree(build_dir)

    if not ctx.dry_run:
        shutil.copytree(source_dir, build_dir, symlinks=True)

    env = os.environ.copy()
    env["CC"] = CC
    env["CFLAGS"] = "-Os"
    env["LDFLAGS"] = "-static"

    try:
        runner.run(
            ["./configure", "--host=mipsel-linux-gnu", "--disable-zlib", "--disable-lastlog", "--disable-utmp", "--disable-utmpx", "--disable-wtmp", "--disable-wtmpx", "--disable-loginfunc", "--enable-bundled-libtom", "--enable-static"],
            cwd=build_dir,
            env=env,
        )
        if not ctx.dry_run:
            _write_localoptions(build_dir)
        runner.run(
            ["make", "-j", str(os.cpu_count() or 1), "PROGRAMS=dropbear dbclient dropbearkey dropbearconvert", "MULTI=1"],
            cwd=build_dir,
            env=env,
        )
        if not ctx.dry_run:
            verify_dropbear_binary(binary)
        return StepResult.done("build_dropbear", f"Built Dropbear binary: {binary}", paths=[binary])
    except Exception as exc:
        return StepResult.fail("build_dropbear", str(exc))


def _write_file(path: Path, contents: str, mode: int) -> None:
    path.write_text(contents, encoding="utf-8")
    path.chmod(mode)


def _safe_symlink(dest: Path, target: Path) -> None:
    if dest.exists() or dest.is_symlink():
        dest.unlink()
    dest.symlink_to(target)


def _template_dir() -> Path:
    return Path(__file__).resolve().parent / "scripts"


def _load_template(name: str) -> str:
    path = _template_dir() / name
    if not path.exists():
        raise FileNotFoundError(f"Missing dropbear script template: {path}")
    return path.read_text(encoding="utf-8")


def create_dropbear_overlay(
    ctx,
    public_key: Optional[str] = None,
    auto_start: bool = True,
    show_indicator: bool = True,
    port: int = 2222,
) -> StepResult:
    overlay_dir = ctx.overlays_dir / "dropbear"
    binary = _dropbear_binary(ctx)

    if not binary.exists():
        return StepResult.fail("create_dropbear_overlay", f"Dropbear binary not found: {binary}")

    if not ctx.dry_run and overlay_dir.exists():
        shutil.rmtree(overlay_dir)
    if not ctx.dry_run:
        overlay_dir.mkdir(parents=True, exist_ok=True)

    usr_bin = overlay_dir / "usr" / "bin"
    etc_init = overlay_dir / "etc" / "init.d"
    etc_dropbear = overlay_dir / "etc" / "dropbear"
    if not ctx.dry_run:
        usr_bin.mkdir(parents=True, exist_ok=True)
        etc_init.mkdir(parents=True, exist_ok=True)
        etc_dropbear.mkdir(parents=True, exist_ok=True)

    # Ensure an overlay entry that makes /root/.ssh a symlink to the
    # persistent dropbear location. This ensures Dropbear's lookup of
    # /root/.ssh/authorized_keys resolves to the persistent storage
    # under /usr/data/dropbear/root/.ssh at runtime.
    root_dir = overlay_dir / "root"
    if not ctx.dry_run:
        root_dir.mkdir(parents=True, exist_ok=True)
        _safe_symlink(root_dir / ".ssh", Path("/usr/data/dropbear/root/.ssh"))

    if not ctx.dry_run:
        shutil.copy2(binary, usr_bin / "dropbearmulti")
        (usr_bin / "dropbearmulti").chmod(0o755)
        for name in ["dropbear", "dropbearkey", "dbclient"]:
            _safe_symlink(usr_bin / name, Path("dropbearmulti"))

    sshon_script = usr_bin / "sshon"
    sshoff_script = usr_bin / "sshoff"
    s95_script = etc_init / "S95dropbear"

    _write_file(sshon_script, _load_template("sshon.sh"), 0o755)
    _write_file(sshoff_script, _load_template("sshoff.sh"), 0o755)

    auto_start_flag = "1" if auto_start else "0"
    show_indicator_flag = "1" if show_indicator else "0"
    s95_contents = Template(_load_template("S95dropbear.sh")).safe_substitute(
        PORT=str(port),
        AUTO_START=auto_start_flag,
        SHOW_INDICATOR=show_indicator_flag,
    )
    _write_file(s95_script, s95_contents, 0o755)

    if public_key:
        public_key_path = Path(public_key).expanduser()
        if not public_key_path.exists():
            return StepResult.fail("create_dropbear_overlay", f"Public key not found: {public_key_path}")
        if not ctx.dry_run:
            with public_key_path.open("r", encoding="utf-8") as pkf:
                key_data = pkf.read().strip()
            if key_data:
                (etc_dropbear / "authorized_keys.default").write_text(key_data + "\n", encoding="utf-8")
                (etc_dropbear / "authorized_keys.default").chmod(0o644)

    # Return the overlay path plus the important files for verification.
    overlay_paths = [overlay_dir, etc_dropbear / "authorized_keys.default", root_dir / ".ssh"]
    return StepResult.done("create_dropbear_overlay", f"Created dropbear overlay at {overlay_dir}", paths=overlay_paths)


def inject_dropbear(
    ctx,
    firmware_name: str,
    public_key: Optional[str] = None,
    auto_start: bool = True,
    show_indicator: bool = True,
    port: int = 2222,
    force: bool = False,
) -> List[StepResult]:
    results: List[StepResult] = []

    build_result = build_dropbear(ctx, force=force, redownload_source=False)
    results.append(build_result)
    if not build_result.ok:
        return results

    overlay_result = create_dropbear_overlay(
        ctx,
        public_key=public_key,
        auto_start=auto_start,
        show_indicator=show_indicator,
        port=port,
    )
    results.append(overlay_result)
    if not overlay_result.ok:
        return results

    inject_result = inject_overlay(ctx, firmware_name, "dropbear", force=force)
    results.append(inject_result)
    return results
