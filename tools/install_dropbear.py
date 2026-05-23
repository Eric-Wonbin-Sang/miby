#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path


DROPBEAR_VERSION = "2026.91"
DROPBEAR_TARBALL = f"dropbear-{DROPBEAR_VERSION}.tar.bz2"
DROPBEAR_URL = f"https://matt.ucc.asn.au/dropbear/releases/{DROPBEAR_TARBALL}"


def run(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    print(f"\n$ {' '.join(cmd)}")
    if cwd:
        print(f"  cwd={cwd}")

    result = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    print(result.stdout)

    if check and result.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(cmd)}")

    return result


def chmod_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def safe_rm(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        print(f"Removing file: {path}")
        path.unlink()
    elif path.is_dir():
        print(f"Removing directory: {path}")
        shutil.rmtree(path)


def require_tool(name: str) -> None:
    if shutil.which(name) is None:
        raise RuntimeError(
            f"Missing required tool: {name}\n\n"
            f"On Ubuntu/WSL, try:\n"
            f"  sudo apt update\n"
            f"  sudo apt install build-essential gcc-mipsel-linux-gnu binutils-mipsel-linux-gnu make wget bzip2\n\n"
            f"On Arch, try:\n"
            f"  sudo pacman -S base-devel mipsel-linux-gnu-gcc mipsel-linux-gnu-binutils wget bzip2\n"
        )


def download_file(url: str, dest: Path) -> bool:
    print(f"Downloading {url}")

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) DropbearBuilder/1.0",
            "Accept": "*/*",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            dest.write_bytes(response.read())
        print(f"Downloaded: {dest}")
        return True
    except Exception as exc:
        print(f"Download failed from {url}: {exc}")
        return False


def download_source(tarball_path: Path, redownload: bool) -> None:
    if redownload and tarball_path.exists():
        safe_rm(tarball_path)

    if tarball_path.exists():
        print(f"Using existing source tarball: {tarball_path}")
        return

    urls = [
        DROPBEAR_URL,
        f"https://mirror.dropbear.nl/mirror/releases/{DROPBEAR_TARBALL}",
        f"https://mirror.dropbear.nl/mirror/{DROPBEAR_TARBALL}",
    ]

    for url in urls:
        if download_file(url, tarball_path):
            return

    raise RuntimeError(
        "Could not download Dropbear source from official site or mirror. "
        "Manually download the tarball and place it here:\n"
        f"  {tarball_path}"
    )


def extract_source(tarball_path: Path, source_dir: Path, redownload: bool) -> None:
    if redownload and source_dir.exists():
        safe_rm(source_dir)

    if source_dir.exists():
        print(f"Using existing source directory: {source_dir}")
        return

    print(f"Extracting {tarball_path}")
    with tarfile.open(tarball_path, "r:bz2") as tf:
        tf.extractall(path=source_dir.parent)

    if not source_dir.exists():
        raise RuntimeError(f"Expected source directory was not created: {source_dir}")


def clean_previous_run(build_dir: Path, overlay_dir: Path) -> None:
    print("\n=== Cleaning previous generated artifacts ===")

    if build_dir.exists():
        safe_rm(build_dir)

    generated_overlay_paths = [
        overlay_dir / "usr/bin/dropbearmulti",
        overlay_dir / "usr/bin/dropbear",
        overlay_dir / "usr/bin/dropbearkey",
        overlay_dir / "usr/bin/dbclient",
        overlay_dir / "usr/bin/scp",
        overlay_dir / "etc/init.d/S95dropbear",
        overlay_dir / "etc/dropbear/authorized_keys.default",
        overlay_dir / "usr/bin/sshon",
        overlay_dir / "usr/bin/sshoff",
    ]

    for path in generated_overlay_paths:
        if path.exists() or path.is_symlink():
            safe_rm(path)


def copy_source_to_build(source_dir: Path, build_dir: Path) -> None:
    print(f"Copying source to clean build dir: {build_dir}")
    shutil.copytree(source_dir, build_dir)


def build_dropbear(build_dir: Path, host: str, cc: str) -> Path:
    require_tool(cc)
    require_tool(f"{host}-readelf")
    require_tool("make")

    env = os.environ.copy()
    env["CC"] = cc
    env["CFLAGS"] = env.get("CFLAGS", "") + " -Os"
    env["LDFLAGS"] = env.get("LDFLAGS", "") + " -static"

    configure_cmd = [
        "./configure",
        f"--host={host}",
        "--disable-zlib",
        "--disable-lastlog",
        "--disable-utmp",
        "--disable-utmpx",
        "--disable-wtmp",
        "--disable-wtmpx",
        "--disable-loginfunc",
        "--enable-bundled-libtom",
        "--enable-static",
    ]

    run(configure_cmd, cwd=build_dir, env=env)

    localoptions = build_dir / "localoptions.h"
    localoptions.write_text(
        """
    #ifndef LOCALOPTIONS_H
    #define LOCALOPTIONS_H

    /* Key-only embedded SSH server. No password auth. */
    #define DROPBEAR_SVR_PASSWORD_AUTH 0
    #define DROPBEAR_SVR_PAM_AUTH 0
    #define DROPBEAR_SVR_PUBKEY_AUTH 1

    /* Keep the client usable but avoid password auth pieces where possible. */
    #define DROPBEAR_CLI_PASSWORD_AUTH 0
    #define DROPBEAR_CLI_PUBKEY_AUTH 1

    /* Reduce risky/less-needed features for this device. */
    #define DROPBEAR_X11FWD 0
    #define DROPBEAR_AGENTFWD 0
    #define DROPBEAR_TCP_ACCEPT 0
    #define DROPBEAR_CLI_LOCALTCPFWD 0
    #define DROPBEAR_CLI_REMOTETCPFWD 0

    #endif
    """.strip()
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {localoptions}")

    run(
        [
            "make",
            "-j",
            str(os.cpu_count() or 2),
            "PROGRAMS=dropbear dbclient dropbearkey dropbearconvert scp",
            "MULTI=1",
        ],
        cwd=build_dir,
        env=env,
    )

    binary = build_dir / "dropbearmulti"

    if not binary.exists():
        raise RuntimeError(f"Build finished, but binary was not found: {binary}")

    return binary


def verify_mips_binary(binary: Path, host: str) -> None:
    print("\n=== Verifying binary architecture ===")

    file_result = run(["file", str(binary)], check=True)
    readelf_result = run(
        [f"{host}-readelf", "-h", str(binary)],
        check=True,
    )

    file_out = file_result.stdout.lower()
    readelf_out = readelf_result.stdout.lower()

    if "x86-64" in file_out or "advanced micro devices x86-64" in readelf_out:
        raise RuntimeError(
            "Bad binary: this is x86-64, not MIPS. "
            "Your cross-compile did not happen correctly."
        )

    if "mips" not in file_out and "machine:" in readelf_out and "mips" not in readelf_out:
        raise RuntimeError(
            "Could not verify this as a MIPS binary.\n"
            "Check the `file` and `readelf` output above."
        )

    if "elf 64-bit" in file_out:
        raise RuntimeError(
            "Bad binary: this is 64-bit. The Hiby rootfs expects 32-bit MIPS userspace."
        )

    if "lsb" not in file_out:
        raise RuntimeError(
            "This does not look little-endian. The Hiby needs MIPS little-endian / mipsel."
        )

    print("Binary verification passed.")


def write_text_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")
    chmod_executable(path)


def install_overlay(
    binary: Path,
    overlay_dir: Path,
    public_key: Path | None,
    port: int,
    require_enable_marker: bool,
) -> None:
    print("\n=== Installing Dropbear into overlay ===")

    usr_bin = overlay_dir / "usr/bin"
    init_d = overlay_dir / "etc/init.d"
    etc_dropbear = overlay_dir / "etc/dropbear"

    usr_bin.mkdir(parents=True, exist_ok=True)
    init_d.mkdir(parents=True, exist_ok=True)
    etc_dropbear.mkdir(parents=True, exist_ok=True)

    target_binary = usr_bin / "dropbearmulti"
    shutil.copy2(binary, target_binary)
    target_binary.chmod(0o755)

    for name in ["dropbear", "dropbearkey", "dbclient", "scp"]:
        link = usr_bin / name
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to("dropbearmulti")

    if public_key:
        if not public_key.exists():
            raise RuntimeError(f"Public key does not exist: {public_key}")

        key_text = public_key.read_text(encoding="utf-8").strip() + "\n"
        default_key = etc_dropbear / "authorized_keys.default"
        default_key.write_text(key_text, encoding="utf-8", newline="\n")
        default_key.chmod(0o644)
        print(f"Installed default authorized_keys: {default_key}")

    enable_gate_block = """
    # Optional safety gate:
    # SSH only starts if this marker exists.
    if [ ! -f "$BASE/enable_ssh" ]; then
      echo "[dropbear] $BASE/enable_ssh not found; not starting"
      exit 0
    fi
""" if require_enable_marker else """
    echo "[dropbear] enable marker gate disabled; starting whenever init script runs"
"""

    init_script = f"""#!/bin/sh

# /etc/init.d/S95dropbear
# Generated by install_dropbear_overlay.py

PATH=/sbin:/bin:/usr/sbin:/usr/bin

DROPBEAR=/usr/bin/dropbear
DROPBEARKEY=/usr/bin/dropbearkey

BASE=/usr/data/dropbear
ROOT_HOME="$BASE/root"
SSH_DIR="$ROOT_HOME/.ssh"

HOST_ED25519="$BASE/dropbear_ed25519_host_key"
HOST_RSA="$BASE/dropbear_rsa_host_key"

PIDFILE=/var/run/dropbear.pid
PORT={port}

case "$1" in
  start)
    echo "[dropbear] preparing directories"

    mkdir -p "$BASE" "$ROOT_HOME" "$SSH_DIR" /var/run
    chmod 700 "$BASE" "$ROOT_HOME" "$SSH_DIR"

{enable_gate_block}
    if [ ! -f "$SSH_DIR/authorized_keys" ] && [ -f /etc/dropbear/authorized_keys.default ]; then
      echo "[dropbear] installing default authorized_keys"
      cp /etc/dropbear/authorized_keys.default "$SSH_DIR/authorized_keys"
    fi

    if [ ! -f "$SSH_DIR/authorized_keys" ]; then
      echo "[dropbear] no authorized_keys found; refusing to start"
      exit 1
    fi

    chmod 600 "$SSH_DIR/authorized_keys"

    if [ ! -f "$HOST_ED25519" ]; then
      echo "[dropbear] generating ed25519 host key"
      "$DROPBEARKEY" -t ed25519 -f "$HOST_ED25519"
      chmod 600 "$HOST_ED25519"
    fi

    if [ ! -f "$HOST_RSA" ]; then
      echo "[dropbear] generating rsa host key"
      "$DROPBEARKEY" -t rsa -s 2048 -f "$HOST_RSA"
      chmod 600 "$HOST_RSA"
    fi

    if [ ! -d /root ]; then
      mkdir -p /root
    fi

    if [ ! -e /root/.ssh ]; then
      ln -s "$SSH_DIR" /root/.ssh
    fi

    echo "[dropbear] starting on port $PORT"

    "$DROPBEAR" \\
      -p "$PORT" \\
      -P "$PIDFILE" \\
      -r "$HOST_ED25519" \\
      -r "$HOST_RSA" \\
      -s \\
      -g \\
      -j \\
      -k

    ;;

  stop)
    echo "[dropbear] stopping"
    if [ -f "$PIDFILE" ]; then
      kill "$(cat "$PIDFILE")" 2>/dev/null
      rm -f "$PIDFILE"
    else
      killall dropbear 2>/dev/null
    fi
    ;;

  restart)
    "$0" stop
    sleep 1
    "$0" start
    ;;

  *)
    echo "Usage: $0 {{start|stop|restart}}"
    exit 1
    ;;
esac

exit 0
"""

    write_text_executable(init_d / "S95dropbear", init_script)

    sshon = """#!/bin/sh
mkdir -p /usr/data/dropbear
touch /usr/data/dropbear/enable_ssh
/etc/init.d/S95dropbear start
"""

    sshoff = """#!/bin/sh
rm -f /usr/data/dropbear/enable_ssh
/etc/init.d/S95dropbear stop
"""

    write_text_executable(usr_bin / "sshon", sshon)
    write_text_executable(usr_bin / "sshoff", sshoff)

    print(f"Installed overlay files under: {overlay_dir}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Dropbear for Hiby R3 Pro II and install it into the firmware overlay."
    )

    parser.add_argument(
        "--overlay-dir",
        type=Path,
        default=Path("scripts"),
        help="Overlay directory that your firmware tool injects into the extracted rootfs. Default: scripts",
    )

    parser.add_argument(
        "--work-dir",
        type=Path,
        default=Path(".dropbear-work"),
        help="Working directory for source tarball/source/build dirs. Default: .dropbear-work",
    )

    parser.add_argument(
        "--redownload-source",
        action="store_true",
        help="Delete and redownload the Dropbear tarball/source directory.",
    )

    parser.add_argument(
        "--host",
        default="mipsel-linux-gnu",
        help="Cross compile host triplet. Default: mipsel-linux-gnu",
    )

    parser.add_argument(
        "--cc",
        default="mipsel-linux-gnu-gcc",
        help="Cross compiler. Default: mipsel-linux-gnu-gcc",
    )

    parser.add_argument(
        "--public-key",
        type=Path,
        default=None,
        help="Path to your SSH public key, e.g. ~/.ssh/id_ed25519.pub",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=2222,
        help="SSH port for Dropbear. Default: 2222",
    )

    parser.add_argument(
        "--no-enable-marker",
        action="store_true",
        help="Start SSH automatically at boot without requiring /usr/data/dropbear/enable_ssh.",
    )

    return parser.parse_args()


def main() -> int:
    args = parse_args()

    repo_root = Path.cwd()
    overlay_dir = args.overlay_dir.expanduser()
    work_dir = args.work_dir.expanduser()

    if not overlay_dir.is_absolute():
        overlay_dir = repo_root / overlay_dir

    if not work_dir.is_absolute():
        work_dir = repo_root / work_dir

    tarball_path = work_dir / DROPBEAR_TARBALL
    source_dir = work_dir / f"dropbear-{DROPBEAR_VERSION}"
    build_dir = work_dir / f"build-dropbear-{args.host}"

    print("=== Dropbear Hiby overlay installer ===")
    print(f"Repo/current dir: {repo_root}")
    print(f"Overlay dir:      {overlay_dir}")
    print(f"Work dir:         {work_dir}")
    print(f"Host:             {args.host}")
    print(f"CC:               {args.cc}")
    print(f"Port:             {args.port}")
    print(f"Enable marker:    {not args.no_enable_marker}")

    work_dir.mkdir(parents=True, exist_ok=True)

    clean_previous_run(build_dir=build_dir, overlay_dir=overlay_dir)

    download_source(tarball_path=tarball_path, redownload=args.redownload_source)
    extract_source(tarball_path=tarball_path, source_dir=source_dir, redownload=args.redownload_source)

    copy_source_to_build(source_dir=source_dir, build_dir=build_dir)

    binary = build_dropbear(build_dir=build_dir, host=args.host, cc=args.cc)

    verify_mips_binary(binary=binary, host=args.host)

    install_overlay(
        binary=binary,
        overlay_dir=overlay_dir,
        public_key=args.public_key.expanduser() if args.public_key else None,
        port=args.port,
        require_enable_marker=not args.no_enable_marker,
    )

    print("\n=== Done ===")
    print("Next steps:")
    print("  1. Run your normal firmware repack script.")
    print("  2. Flash the firmware.")
    print("  3. Enable SSH from ADB:")
    print("       adb shell 'sshon'")
    print("  4. Connect:")
    print(f"       ssh -p {args.port} root@HIBY_IP")
    print("\nIf the device does not boot or SSH fails, use ADB first and run:")
    print("       adb shell '/usr/bin/dropbear -V'")
    print("       adb shell '/etc/init.d/S95dropbear start'")

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)