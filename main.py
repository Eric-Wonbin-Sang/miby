import subprocess
import os
import shutil
from pathlib import Path
from typing import Optional, Tuple, List
import hashlib
from functools import cached_property


def run_command(cmd: str, dry_run: bool=True, **run_kwargs: dict):
    run_kwargs = {"shell": True, "check": True, **(run_kwargs or {})}
    print(("(DRY) "if dry_run else "") + f"Running: \"{cmd}\" with kwargs={run_kwargs}")
    if dry_run:
        return
    return subprocess.run(cmd, **run_kwargs)


class UptUtils:

    @staticmethod
    def extract(filepath: Path, output_dir: Path, dry_run: bool=True):
        if not output_dir.exists():
            output_dir.mkdir()
        return run_command(f"7z x {filepath} -o{output_dir} -y", dry_run=dry_run)
    
    @staticmethod
    def package(content_dir: Path, output_path: Path, dry_run: bool=True):
        return run_command(
            f"genisoimage -o {output_path} -V CDROM -J -r {content_dir}",
            dry_run=dry_run,
        )


class Md5Utils:

    @staticmethod
    def get_file_md5(path: Path, buffer_size: int = 1024 * 1024) -> str:
        """Compute MD5 of a file in a streaming-safe way."""
        h = hashlib.md5()
        with path.open("rb") as f:
            for chunk in iter(lambda: f.read(buffer_size), b""):
                h.update(chunk)
        return h.hexdigest()


class RootFsUtils:

    @staticmethod
    def get_file_info(path: Path, dry_run: bool=True):
        print("\n\n\n\n")
        return run_command(f"unsquashfs -s {path}", dry_run=dry_run)

    @staticmethod
    def get_fs_xattrs(path: Path, dry_run: bool=True):
        return run_command(f"unsquashfs -lls {path}", dry_run=dry_run)

    @staticmethod
    def convert_chunks_to_file(chunks_dir: Path, chunk_pattern: str, output_path: Path, dry_run: bool=True):
        assert chunks_dir.is_dir(), FileNotFoundError(f"chunks_dir {chunks_dir} is not a dir!")
        run_command(f"cat {chunks_dir / chunk_pattern} > {output_path}", dry_run=dry_run)
        return output_path

    @staticmethod
    def convert_file_to_file_system(rootfs_path: Path, output_dir: Path, dry_run: bool=True):
        # delete the dir if it exists
        if output_dir.is_dir():
            shutil.rmtree(output_dir, ignore_errors=True)
        return run_command(f"unsquashfs -d {output_dir} {rootfs_path}", dry_run=dry_run)

    @staticmethod
    def convert_file_system_to_file(file_system_dir: Path, output_path: Path, dry_run: bool=True):
        """use RootFsUtils.get_file_info to determine parameters"""
        return run_command(
            f"mksquashfs {file_system_dir} {output_path}"
                + " -comp lzo"      # HiBy firmware uses XZ-compressed SquashFS
                + " -b 131072"      # 128 KiB block size (must match original)
                + " -noappend"      # Prevents modifying an existing image
                + " -all-root"      # Forces UID/GID = 0 (critical for reproducibility)
                + " -xattrs"        # usually a default
                + " -exports"       # usually a default
                + " -no-tailends",  # matches “Tailends are not packed into fragments”
            dry_run=dry_run,
        )

    @staticmethod
    def convert_file_to_chunks(
        path: Path,
        bytes_per_chunk: int,
        dry_run: bool = True,
    ) -> Tuple[Optional[str], List[str]]:
        """
        HiBy/official format:

        - Split into numeric chunks: <name>.0000, <name>.0001, ...
        - Compute md5 for each chunk's CONTENT.
        - Rename each chunk to: <name>.<index4>.<md5(chunk_i)>
        - pre_md5 = md5(chunk_0000)
        - Write: ota_md5_<name>.<pre_md5> whose contents are md5s for chunks 0001..end (one per line)

        Returns:
          (pre_md5, chunk_md5s)
            pre_md5 = md5(chunk0) or None if dry_run
            chunk_md5s = [md5(chunk0), md5(chunk1), ...] (empty if dry_run)
        """
        chunk_prefix: str = f"{path.name}."

        run_command(
            f"split --numeric-suffixes=0 --suffix-length=4 -b {bytes_per_chunk} {path.name} {chunk_prefix}",
            dry_run=dry_run,
            cwd=path.parent,
        )

        if dry_run:
            return None, []

        # ONLY grab the numeric stage outputs, not already-renamed files
        numeric_chunks = sorted(path.parent.glob(f"{chunk_prefix}[0-9][0-9][0-9][0-9]"))
        if not numeric_chunks:
            raise FileNotFoundError(
                f"No numeric chunk files found with prefix '{chunk_prefix}' in {path.parent}"
            )

        # md5 each chunk content in order
        chunk_md5s: List[str] = [Md5Utils.get_file_md5(p) for p in numeric_chunks]
        pre_md5: str = chunk_md5s[0]

        # rename each chunk to include its own md5
        renamed_paths: List[Path] = []
        for p, md5 in zip(numeric_chunks, chunk_md5s):
            new_name = f"{p.name}.{md5}"
            new_path = p.with_name(new_name)
            print(f"{p.name} -> {new_name}")
            p.rename(new_path)
            renamed_paths.append(new_path)

        # write ota_md5_<img_name>.<pre_md5> listing md5s for chunks 0001..end
        if not dry_run:
            md5_list_path = path.parent / f"ota_md5_{path.name}.{pre_md5}"
            md5_list_text = "\n".join(chunk_md5s[1:]) + "\n"  # IMPORTANT: skip chunk0
            md5_list_path.write_text(md5_list_text, encoding="utf-8")
            print(f"Wrote {md5_list_path.name} ({len(chunk_md5s) - 1} lines)")

        return pre_md5, chunk_md5s

    @staticmethod
    def update_ota_file_with_new_rootfs_chunks(chunks_dir, ota_update_file, dry_run: bool=True):
        data_dicts, current_dict = [], {}
        for line in ota_update_file.read_text(encoding="utf-8").split("\n"):
            if line.strip() == "":
                data_dicts.append(current_dict)
                current_dict = {}
            else:
                key, value = line.split("=", 1)
                current_dict[key] = value

        def sorted_rootfs_chunks(chunks_dir: Path) -> list[Path]:
            return sorted(
                chunks_dir.glob("rootfs.squashfs.*.*"),
                key=lambda p: int(p.name.split(".")[-2])
            )

        def md5_of_concatenated_chunks(chunks: list[Path]) -> str:
            h = hashlib.md5()
            for chunk in chunks:
                with chunk.open("rb") as f:
                    for buf in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(buf)
            return h.hexdigest()

        chunks = sorted_rootfs_chunks(chunks_dir)
        for c in chunks:
            print(c)
        total_size = sum(p.stat().st_size for p in chunks)
        total_md5 = md5_of_concatenated_chunks(chunks)

        ret_str = ""
        for data in data_dicts:
            if data.get("img_type") == "rootfs":
                data["img_size"] = str(total_size)
                data["img_md5"] = str(total_md5)
            for key, value in data.items():
                ret_str += f"{key}={value}\n"
            ret_str += "\n"

        print("(Dry) " if dry_run else "" + f"Updating {ota_update_file.name} with new rootfs info")
        if (dry_run):
            return
        ota_update_file.write_text(ret_str, encoding="utf-8")



class StorageModel:

    ROOTFS_FILENAME = "rootfs.squashfs"
    OTA_MD5_ROOTFS_FILE_PREFIX = f"ota_md5_{ROOTFS_FILENAME}."

    def __init__(self):
        ...


class FirmwareExtractor:

    ROOTFS_FILENAME = "rootfs.squashfs"
    CHUNKS_DIR_NAME = "ota_v0"

    def __init__(self, firmware_path: Path) -> None:
        assert (firmware_path := firmware_path.absolute()).is_file(), f"{firmware_path} is not a file!"
        self.firmware_path: Path = firmware_path

    @cached_property
    def extract_dir(self) -> Path:
        return (self.firmware_path.parent / f"{self.firmware_path.name}_extracted").absolute()

    @cached_property
    def extracted_chunks_dir(self) -> Path:
        return (self.extract_dir / self.CHUNKS_DIR_NAME).absolute()

    @cached_property
    def concatted_rootfs_file(self) -> Path:
        return self.extracted_chunks_dir / self.ROOTFS_FILENAME

    @cached_property
    def extracted_rootfs_path(self) -> Path:
        return self.extracted_chunks_dir / f"{self.ROOTFS_FILENAME}_extracted"

    def run(self, dry_run=True):
        # unzip the upt archive
        UptUtils.extract(self.firmware_path, self.extract_dir, dry_run)

        # concat all of the chunks into one rootfs file
        rootfs_path = RootFsUtils.convert_chunks_to_file(
            chunks_dir=self.extracted_chunks_dir,
            chunk_pattern=f"{self.ROOTFS_FILENAME}.*",
            output_path=self.extracted_chunks_dir / self.ROOTFS_FILENAME,
            dry_run=dry_run,
        )

        # convert the rootfs file to the read-only filesystem
        RootFsUtils.convert_file_to_file_system(
            rootfs_path=rootfs_path,
            output_dir=self.extracted_rootfs_path,
            dry_run=dry_run,
        )


class ExtractedFirmwareBundler:

    OTA_UPDATE_FILENAME: str = "ota_update.in"
    
    def __init__(self, firmware_path: Path, extractor: FirmwareExtractor) -> None:
        assert firmware_path.is_file(), f"{firmware_path} is not a file!"
        assert extractor.extract_dir.is_dir(), f"{extractor.extract_dir} is not a dir!"
        self.firmware_path = firmware_path
        self.extractor = extractor

    @cached_property
    def bundler_dir(self) -> Path:
        return (self.firmware_path.parent / f"{self.firmware_path.name}_bundle")

    @cached_property
    def rootfs_chunks_dir(self) -> Path:
        return self.bundler_dir / self.extractor.CHUNKS_DIR_NAME

    def copy_extracted_dir(self, dry_run: bool=True):
        return run_command(f"cp -a {self.extractor.extract_dir}{os.sep}. {self.bundler_dir}", dry_run=dry_run)

    def remove_rootfs_files(self, dry_run=True):
        bundle_chunks_dir = self.rootfs_chunks_dir
        print("(DRY) " if dry_run else "" + f"Removing files prefixed with {self.extractor.ROOTFS_FILENAME} in {bundle_chunks_dir}")
        for p in bundle_chunks_dir.iterdir():
            if not p.name.startswith(self.extractor.ROOTFS_FILENAME) and not p.name.startswith(StorageModel.OTA_MD5_ROOTFS_FILE_PREFIX):
                continue
            if dry_run:
                continue
            if p.is_file():
                p.unlink(missing_ok=True)
            else:
                shutil.rmtree(p, ignore_errors=True)

    def run(self, dry_run=True):
        # make a copy of the extracted dir under "{firmware name}_bundled"
        self.copy_extracted_dir(dry_run=dry_run)
        # remove the rootfs files since we need to "compile" those
        self.remove_rootfs_files(dry_run=dry_run)
    
        # convert the extracted file system to the singular rootfs file  
        rootfs_path = self.rootfs_chunks_dir / FirmwareExtractor.ROOTFS_FILENAME
        RootFsUtils.convert_file_system_to_file(
            file_system_dir=self.extractor.extracted_rootfs_path,
            output_path=rootfs_path,
            dry_run=dry_run
        )
        print(RootFsUtils.get_file_info(rootfs_path, dry_run=dry_run))
        # print(RootFsUtils.get_fs_xattrs(rootfs_path, dry_run=False))
        
        # convert the rootfs file to chunks
        RootFsUtils.convert_file_to_chunks(
            path=rootfs_path,
            bytes_per_chunk=524288,  # 512 KiB
            dry_run=dry_run
        )
        # remove the mother file
        rootfs_path.unlink()

        # ota_update.in needs to have the correct rootfs info
        RootFsUtils.update_ota_file_with_new_rootfs_chunks(
            chunks_dir=self.rootfs_chunks_dir,
            ota_update_file=self.rootfs_chunks_dir / self.OTA_UPDATE_FILENAME,
            dry_run=dry_run,
        )
        # bundle everything back into a upt file
        UptUtils.package(
            content_dir=self.bundler_dir,
            output_path=Path(f"{self.firmware_path.name}"),
            dry_run=dry_run,
        )

def main():
    extractor = FirmwareExtractor(
        firmware_path=Path("firmware/r3proii.upt"),
    )
    extractor.run(dry_run=False)
    print(RootFsUtils.get_file_info(extractor.concatted_rootfs_file, dry_run=False))
    # print(RootFsUtils.get_fs_xattrs(extractor.concatted_rootfs_file, dry_run=False))
    
    bundler = ExtractedFirmwareBundler(
        firmware_path=extractor.firmware_path,
        extractor=extractor
    )
    bundler.run(dry_run=False)


if __name__ == "__main__":
    main()


# sudo pacman -S squashfs-tools
# sudo pacman -S 7zip
# sudo pacman -S binwalk