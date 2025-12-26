import os
import subprocess
import shutil


FIRMWARE_BASE_DIR = "firmware"
FIRMWARE_SOURCE_DIR = os.path.join(FIRMWARE_BASE_DIR, "sources")
FIRMWARE_EXTRACTS_DIR = os.path.join(FIRMWARE_BASE_DIR, "extracts")
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


def extract_firmware(source_dir, extracts_dir):
    if not os.path.exists(extracts_dir):
        os.makedirs(extracts_dir)

    seven_zip_exe = find_seven_zip_executable()
    if not seven_zip_exe:
        raise FileNotFoundError(
            "Couldn't find the '7z' command-line tool. Install 7-Zip and ensure "
            "7z.exe is on your PATH or set SEVEN_ZIP_EXE to its full path."
        )
    print("Using 7-Zip:", seven_zip_exe)

    for firmware_file in os.listdir(source_dir):
        firmware_path = os.path.join(source_dir, firmware_file)
        if os.path.isfile(firmware_path):
            extract_dir = os.path.abspath(
                os.path.join(extracts_dir, os.path.splitext(firmware_file)[0])
            )
            os.makedirs(extract_dir, exist_ok=True)

            firmware_path = os.path.abspath(firmware_path)
            print(f"firmware_path: {firmware_path}")

            subprocess.run(
                [seven_zip_exe, "x", firmware_path, f"-o{extract_dir}", "-y"],
                check=True,
            )


# Concatenate the split SquashFS chunks
def concatenate_squashfs_chunks(extracts_dir):
    # cat rootfs.squashfs.* > rootfs.squashfs
    # unsquashfs -s rootfs.squashfs

    # Found a valid SQUASHFS 4:0 superblock on rootfs.squashfs.
    # Creation or last append time Wed Jul 23 02:28:08 2025
    # Filesystem size 33927877 bytes (33132.69 Kbytes / 32.36 Mbytes)
    # Compression lzo
    # Block size 131072
    # Filesystem is exportable via NFS
    # Inodes are compressed
    # Data is compressed
    # Uids/Gids (Id table) are compressed
    # Fragments are compressed
    # Always-use-fragments option is not specified
    # Xattrs are compressed
    # Duplicates are removed
    # Number of fragments 142
    # Number of inodes 4339
    # Number of ids 3
    # Number of xattr ids 0
    ...

# Extract the SquashFS filesystem
def get_squashfs_filesystem(extracts_dir):
    ...


def get_firmware():

    # Invoke the function with the constants
    extract_firmware(source_dir=FIRMWARE_SOURCE_DIR, extracts_dir=FIRMWARE_EXTRACTS_DIR)

    # https://github.com/onekey-sec/ubi_reader
    # ubireader_extract_files system.ubifs

    ...

def main():

    prepend_paths_to_env(DEFAULT_TOOL_PATHS)

    # https://codecat.nl/2024/06/hiby-r3ii-root/

    firmware = get_firmware()


if __name__ == "__main__":
    main()
