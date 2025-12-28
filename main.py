import os
import subprocess
import shutil


FIRMWARE_BASE_DIR = "firmware"
FIRMWARE_SOURCE_DIR = os.path.join(FIRMWARE_BASE_DIR, "sources")
FIRMWARE_EXTRACTS_DIR = os.path.join(FIRMWARE_BASE_DIR, "extracts")
FIRMWARE_BUILDS_DIR = os.path.join(FIRMWARE_BASE_DIR, "builds")
# Default search path for locally installed CLI tools (cargo-installed binaries, 7-Zip, etc.)
DEFAULT_TOOL_PATHS = [
    r"C:\Users\ericw\.cargo\bin",
    r"C:\Program Files\7-Zip",
    r"C:\Program Files (x86)\7-Zip",
]


def prepend_paths_to_env(paths):
    if not paths:
        return

    current = os.environ.get("PATH", "")
    current_parts = [part for part in current.split(os.pathsep) if part]
    new_parts = []

    for path in paths:
        expanded = os.path.normpath(os.path.expandvars(os.path.expanduser(path)))
        if expanded and expanded not in current_parts and expanded not in new_parts:
            new_parts.append(expanded)

    if new_parts:
        os.environ["PATH"] = os.pathsep.join(new_parts + current_parts)


def find_seven_zip_executable():
    candidates = [
        os.environ.get("SEVEN_ZIP_EXE"),
        r"C:\Program Files\7-Zip\7z.exe",
        r"C:\Program Files (x86)\7-Zip\7z.exe",
        "7z",
        "7z.exe",
        "7za",
        "7za.exe",
    ]

    for candidate in candidates:
        if not candidate:
            continue

        resolved = shutil.which(candidate)
        if resolved:
            return resolved

    return None


def extract_firmware(firmware_path, extracts_dir, dry_run=True):
    if not (seven_zip_script := find_seven_zip_executable()):
        raise FileNotFoundError(
            "Couldn't find the '7z' command-line tool. Install 7-Zip and ensure "
            "7z.exe is on your PATH or set SEVEN_ZIP_EXE to its full path."
        )
    print("Using 7-Zip:", seven_zip_script)

    if not os.path.isfile(firmware_path := os.path.abspath(firmware_path)):
        raise FileNotFoundError(f"Firmware file not found: {firmware_path}")
    print(f"firmware_path: {firmware_path}")

    if not os.path.exists(extracts_dir):
        os.makedirs(extracts_dir)
    print(f"extracts_dir: {extracts_dir}")

    filename = os.path.basename(firmware_path)
    extract_dir = os.path.abspath(
        os.path.join(extracts_dir, os.path.splitext(filename)[0])
    )

    if dry_run:
        print(f"DRY RUN: Extract {firmware_path} to {extract_dir}")
        return

    os.makedirs(extract_dir, exist_ok=True)

    subprocess.run(
        [seven_zip_script, "x", firmware_path, f"-o{extract_dir}", "-y"],
        check=True,
    )


# Concatenate the split SquashFS chunks
def concatenate_squashfs_chunks(rootfs_chunks_dir, output_dir, dry_run=True):
    if not os.path.isdir(rootfs_chunks_dir):
        raise FileNotFoundError(f"Rootfs chunks dir not found: {rootfs_chunks_dir}")
    print(f"rootfs_chunks_dir: {rootfs_chunks_dir}")

    if not os.path.exists(output_dir := os.path.abspath(output_dir)) and not dry_run:
        os.makedirs(output_dir, exist_ok=True)
    print(f"output_dir: {output_dir}")

    # Concatenate split SquashFS chunks into ../rootfs.squashfs using the shell cat+redirect
    cmd = f"cat rootfs.squashfs.* > {output_dir}/rootfs.squashfs"

    if dry_run:
        print(f"DRY RUN: {cmd} (in {rootfs_chunks_dir})")
    else:
        print(f"Running: {cmd} (in {rootfs_chunks_dir})")
        subprocess.run(cmd, shell=True, check=True, cwd=rootfs_chunks_dir)

    return os.path.abspath(os.path.join(rootfs_chunks_dir, "..", "rootfs.squashfs"))


def convert_squashfs_to_fs(squashfs_filepath, output_dir, dry_run=True):
    cmd = f"unsquashfs -d {output_dir} {squashfs_filepath}"

    if dry_run:
        print(f"DRY RUN: {cmd}")
    else:
        print(f"Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)


def main():

    # prepend_paths_to_env(DEFAULT_TOOL_PATHS)

    extract_firmware(
        firmware_path=os.path.join(FIRMWARE_SOURCE_DIR, "r3proii.upt"),
        extracts_dir=FIRMWARE_EXTRACTS_DIR,
        dry_run=True,
        # dry_run=False,
    )

    concatenate_squashfs_chunks(
        rootfs_chunks_dir=os.path.join(FIRMWARE_EXTRACTS_DIR, "r3proii", "ota_v0"),
        output_dir=os.path.join(FIRMWARE_BUILDS_DIR, "r3proii"),
        dry_run=True,
        # dry_run=False,
    )

    convert_squashfs_to_fs(
        squashfs_filepath=os.path.join(FIRMWARE_BUILDS_DIR, "r3proii", "rootfs.squashfs"),
        output_dir=os.path.join(FIRMWARE_BUILDS_DIR, "r3proii", "rootfs_extracted"),
        # dry_run=True,
        dry_run=False,
    )


if __name__ == "__main__":
    main()
