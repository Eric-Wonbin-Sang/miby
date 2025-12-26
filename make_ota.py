#!/usr/bin/env python3
"""
Generate HiBy-style OTA 'ota_v0' directory for a rebuilt rootfs.squashfs.

What it creates inside OUT_DIR/ota_v0/:
- rootfs.squashfs.0000.<md5>
- rootfs.squashfs.0001.<md5>
- ...
- ota_md5_rootfs.squashfs.<pre_md5>   (pre_md5 = md5 of chunk 0000)
- ota_update.in                      (rootfs section filled; kernel optional)
- ota_v0.ok                          (empty)

Optionally also includes kernel/xImage info if you pass it (it won't split kernel;
this script only packages rootfs in the OTA style).
"""

from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
from typing import List, Optional, Tuple


def md5_file(path: Path, buf_size: int = 1024 * 1024) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            b = f.read(buf_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def split_file(src: Path, out_dir: Path, chunk_size: int) -> List[Path]:
    """
    Split src into fixed-size chunks:
      out_dir/<src.name>.0000
      out_dir/<src.name>.0001
      ...
    Returns list of chunk paths in order.
    """
    chunks: List[Path] = []
    base = src.name
    out_dir.mkdir(parents=True, exist_ok=True)

    i = 0
    with src.open("rb") as f:
        while True:
            data = f.read(chunk_size)
            if not data:
                break
            chunk_path = out_dir / f"{base}.{i:04d}"
            chunk_path.write_bytes(data)
            chunks.append(chunk_path)
            i += 1

    if not chunks:
        raise RuntimeError(f"No data read from {src} (empty file?)")

    return chunks


def rename_chunks_with_md5(chunks: List[Path]) -> Tuple[str, List[Tuple[Path, str]]]:
    """
    For each chunk file, compute md5 and rename to: <orig>.<md5>
    Returns:
      pre_md5 (md5 of first chunk)
      list of (new_path, md5) in order
    """
    out: List[Tuple[Path, str]] = []

    pre_md5: Optional[str] = None
    for idx, p in enumerate(chunks):
        data = p.read_bytes()
        h = md5_bytes(data)
        if idx == 0:
            pre_md5 = h
        new_path = p.with_name(p.name + f".{h}")
        p.replace(new_path)
        out.append((new_path, h))

    assert pre_md5 is not None
    return pre_md5, out


def write_md5_list(ota_v_dir: Path, img_name: str, pre_md5: str, chunk_md5s: List[str]) -> Path:
    """
    Writes: ota_md5_<img_name>.<pre_md5>
    Each line i is md5 for chunk i+1 (matches script behavior: sed -n "${num}p")
    """
    md5_file_path = ota_v_dir / f"ota_md5_{img_name}.{pre_md5}"
    md5_file_path.write_text("\n".join(chunk_md5s) + "\n", encoding="utf-8")
    return md5_file_path


def write_ota_update_in(
    ota_v_dir: Path,
    ota_version: int,
    kernel_name: Optional[str],
    kernel_size: Optional[int],
    kernel_md5: Optional[str],
    rootfs_name: str,
    rootfs_size: int,
    rootfs_pre_md5: str,
) -> Path:
    """
    Writes ota_update.in with kernel block (if provided) + rootfs block.
    Note: For rootfs, HiBy's script treats img_md5 as the "pre_md5" used to find ota_md5_* file.
    """
    lines = []
    lines.append(f"ota_version={ota_version}")
    lines.append("")

    if kernel_name and kernel_size is not None and kernel_md5:
        lines += [
            "img_type=kernel",
            f"img_name={kernel_name}",
            f"img_size={kernel_size}",
            f"img_md5={kernel_md5}",
            "",
        ]

    lines += [
        "img_type=rootfs",
        f"img_name={rootfs_name}",
        f"img_size={rootfs_size}",
        f"img_md5={rootfs_pre_md5}",
        "",
    ]

    p = ota_v_dir / "ota_update.in"
    p.write_text("\n".join(lines), encoding="utf-8")
    return p


def touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(b"")
    else:
        # keep it empty
        path.write_bytes(b"")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rootfs", required=True, help="Path to rebuilt full rootfs.squashfs")
    ap.add_argument("--out", required=True, help="Output base dir (will create <out>/ota_v0/)")
    ap.add_argument("--chunk-size", type=int, default=512 * 1024, help="Chunk size in bytes (default 524288)")
    ap.add_argument("--ota-version", type=int, default=0, help="ota_version field in ota_update.in (default 0)")

    # Optional kernel info passthrough (not generated/split by this script)
    ap.add_argument("--kernel-name", default=None, help="Kernel image name in ota_update.in (e.g., xImage)")
    ap.add_argument("--kernel-size", type=int, default=None, help="Kernel size in bytes (as in original ota_update.in)")
    ap.add_argument("--kernel-md5", default=None, help="Kernel md5 (as in original ota_update.in)")

    args = ap.parse_args()

    rootfs_path = Path(args.rootfs).expanduser().resolve()
    out_base = Path(args.out).expanduser().resolve()
    ota_v_dir = out_base / "ota_v0"

    if not rootfs_path.exists():
        raise FileNotFoundError(rootfs_path)

    ota_v_dir.mkdir(parents=True, exist_ok=True)

    # 1) Split into raw chunks: rootfs.squashfs.0000, 0001, ...
    raw_chunks = split_file(rootfs_path, ota_v_dir, args.chunk_size)

    # 2) Rename chunks to rootfs.squashfs.000N.<md5> and collect md5 list
    pre_md5, renamed = rename_chunks_with_md5(raw_chunks)
    chunk_md5s = [h for (_p, h) in renamed]

    # 3) Write ota_md5_rootfs.squashfs.<pre_md5>
    rootfs_name = rootfs_path.name  # should be "rootfs.squashfs"
    write_md5_list(ota_v_dir, rootfs_name, pre_md5, chunk_md5s)

    # 4) Write ota_update.in
    rootfs_size = rootfs_path.stat().st_size
    write_ota_update_in(
        ota_v_dir=ota_v_dir,
        ota_version=args.ota_version,
        kernel_name=args.kernel_name,
        kernel_size=args.kernel_size,
        kernel_md5=args.kernel_md5,
        rootfs_name=rootfs_name,
        rootfs_size=rootfs_size,
        rootfs_pre_md5=pre_md5,
    )

    # 5) Write ota_v0.ok (empty)
    touch(ota_v_dir / "ota_v0.ok")

    print("Done.")
    print(f"Output: {ota_v_dir}")
    print(f"rootfs_size: {rootfs_size}")
    print(f"rootfs_pre_md5 (ota_update.in img_md5): {pre_md5}")
    print(f"Chunks: {len(renamed)}")
    print("Example chunk:", renamed[0][0].name)


if __name__ == "__main__":
    main()
