#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


def md5_bytes(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def split_file(src: Path, out_dir: Path, chunk_size: int) -> List[Path]:
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
    out: List[Tuple[Path, str]] = []

    pre_md5: Optional[str] = None
    for idx, p in enumerate(chunks):
        h = md5_bytes(p.read_bytes())
        if idx == 0:
            pre_md5 = h
        new_path = p.with_name(p.name + f".{h}")
        p.replace(new_path)
        out.append((new_path, h))

    assert pre_md5 is not None
    return pre_md5, out


def write_md5_list(ota_v_dir: Path, img_name: str, pre_md5: str, chunk_md5s: List[str]) -> Path:
    md5_file_path = ota_v_dir / f"ota_md5_{img_name}.{pre_md5}"
    md5_file_path.write_text("\n".join(chunk_md5s) + "\n", encoding="utf-8")
    return md5_file_path


def write_ota_update_in(
    ota_v_dir: Path,
    ota_version: int,
    kernel: Optional["KernelConfig"],
    rootfs_name: str,
    rootfs_size: int,
    rootfs_pre_md5: str,
) -> Path:
    lines: List[str] = []
    lines.append(f"ota_version={ota_version}")
    lines.append("")

    if kernel is not None:
        lines += [
            "img_type=kernel",
            f"img_name={kernel.name}",
            f"img_size={kernel.size}",
            f"img_md5={kernel.md5}",
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


def touch_empty(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")


@dataclass(frozen=True)
class KernelDefaults:
    name: str = "xImage"
    size: int = 0
    md5: str = ""


@dataclass(frozen=True)
class KernelConfig:
    name: str
    size: int
    md5: str


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rootfs", required=True, help="Path to rebuilt full rootfs.squashfs")
    ap.add_argument("--out", required=True, help="Output base dir (will create <out>/ota_v0/)")
    ap.add_argument("--chunk-size", type=int, default=512 * 1024, help="Chunk size in bytes (default 524288)")
    ap.add_argument("--ota-version", type=int, default=0, help="ota_version field in ota_update.in (default 0)")

    # Kernel args: NO DEFAULTS here, so we can detect intent.
    ap.add_argument("--kernel-name", default=None, help="Kernel image name (e.g., xImage)")
    ap.add_argument("--kernel-size", type=int, default=None, help="Kernel size in bytes")
    ap.add_argument("--kernel-md5", default=None, help="Kernel md5")

    return ap.parse_args(argv)


def build_kernel_config(
    kernel_name: Optional[str],
    kernel_size: Optional[int],
    kernel_md5: Optional[str],
    defaults: KernelDefaults,
) -> Optional[KernelConfig]:
    """
    Rules:
    - If NONE of the kernel args are provided -> return None (omit kernel block).
    - If ANY kernel arg is provided -> "kernel mode":
        missing ones get filled from defaults.
      (This lets you specify just --kernel-md5 or just --kernel-size, etc.)
    - Safety: after filling, we still require size/md5 to be non-empty/valid.
    """
    any_provided = any(v is not None for v in (kernel_name, kernel_size, kernel_md5))
    if not any_provided:
        return None

    name = kernel_name if kernel_name is not None else defaults.name
    size = kernel_size if kernel_size is not None else defaults.size
    md5 = kernel_md5 if kernel_md5 is not None else defaults.md5

    # Minimal sanity checks so you don't silently generate junk.
    if size <= 0:
        raise SystemExit(
            f"Kernel mode enabled but kernel size is invalid ({size}). "
            f"Provide --kernel-size or set a positive default."
        )
    if not md5 or len(md5) != 32:
        raise SystemExit(
            f"Kernel mode enabled but kernel md5 is invalid ({md5!r}). "
            f"Provide --kernel-md5 (32 hex chars) or set a valid default."
        )

    return KernelConfig(name=name, size=size, md5=md5)


def run(
    rootfs: Path,
    out_base: Path,
    chunk_size: int,
    ota_version: int,
    kernel: Optional[KernelConfig],
) -> None:
    rootfs = rootfs.expanduser().resolve()
    out_base = out_base.expanduser().resolve()
    ota_v_dir = out_base / "ota_v0"

    if not rootfs.exists():
        raise FileNotFoundError(rootfs)

    ota_v_dir.mkdir(parents=True, exist_ok=True)

    raw_chunks = split_file(rootfs, ota_v_dir, chunk_size)
    pre_md5, renamed = rename_chunks_with_md5(raw_chunks)
    chunk_md5s = [h for (_p, h) in renamed]

    rootfs_name = rootfs.name
    write_md5_list(ota_v_dir, rootfs_name, pre_md5, chunk_md5s)

    rootfs_size = rootfs.stat().st_size
    write_ota_update_in(
        ota_v_dir=ota_v_dir,
        ota_version=ota_version,
        kernel=kernel,
        rootfs_name=rootfs_name,
        rootfs_size=rootfs_size,
        rootfs_pre_md5=pre_md5,
    )

    touch_empty(ota_v_dir / "ota_v0.ok")

    print("Done.")
    print(f"Output: {ota_v_dir}")
    print(f"rootfs_size: {rootfs_size}")
    print(f"rootfs_pre_md5 (ota_update.in img_md5): {pre_md5}")
    print(f"Chunks: {len(renamed)}")
    print("Kernel block:", "included" if kernel else "omitted")
    print("Example chunk:", renamed[0][0].name)


def main(argv: Optional[List[str]] = None) -> None:
    args = parse_args(argv)

    # Set your defaults here (these only apply if user supplies *any* kernel arg).
    kernel_defaults = KernelDefaults(
        name="xImage",
        size=3760192,  # <-- set to your usual kernel size default
        md5="4a459b51a152014bfab6c1114f2701e3",  # <-- set to your usual kernel md5 default
    )

    kernel_cfg = build_kernel_config(
        kernel_name=args.kernel_name,
        kernel_size=args.kernel_size,
        kernel_md5=args.kernel_md5,
        defaults=kernel_defaults,
    )

    run(
        rootfs=Path(args.rootfs),
        out_base=Path(args.out),
        chunk_size=args.chunk_size,
        ota_version=args.ota_version,
        kernel=kernel_cfg,
    )


if __name__ == "__main__":
    main()
