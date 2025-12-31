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
            run_command(f"sudo rm -rf {output_dir}", dry_run=dry_run)
        return run_command(f"sudo unsquashfs -d {output_dir} {rootfs_path}", dry_run=dry_run)

    @staticmethod
    def convert_file_system_to_file(file_system_dir: Path, output_path: Path, dry_run: bool=True):
        """use RootFsUtils.get_file_info to determine parameters"""
        return run_command(
            f"sudo mksquashfs {file_system_dir} {output_path}"
                + " -comp lzo"      # HiBy firmware uses XZ-compressed SquashFS
                + " -b 131072"      # 128 KiB block size (must match original)
                + " -noappend"      # Prevents modifying an existing image
                # + " -all-root"      # Forces UID/GID = 0 (critical for reproducibility)
                + " -xattrs"        # usually a default
                + " -exports"       # usually a default
                + " -no-tailends",  # matches “Tailends are not packed into fragments”
            dry_run=dry_run,
        )

    @staticmethod
    def convert_file_to_chunks(
        path: Path,
        bytes_per_chunk: int,
        img_md5: str,     # <-- H (anchor value, matches official ota_update + chunk0000 + ota_md5 filename)
        dry_run: bool = True,
    ) -> List[str]:
        """
        Split file into numeric chunks, compute md5(content) per chunk, then:

        chunk0000 suffix = img_md5 (H)
        chunk i suffix   = md5(chunk i-1 content) for i>=1

        Write ota_md5_<name>.<img_md5> with lines = md5(chunk0), md5(chunk1), ... (all chunks)
        Returns list m[i] for all chunks.
        """
        chunk_prefix = f"{path.name}."

        run_command(
            f"split --numeric-suffixes=0 --suffix-length=4 -b {bytes_per_chunk} {path.name} {chunk_prefix}",
            dry_run=dry_run,
            cwd=path.parent,
        )
        if dry_run:
            return []

        numeric_chunks = sorted(path.parent.glob(f"{chunk_prefix}[0-9][0-9][0-9][0-9]"))
        if not numeric_chunks:
            raise FileNotFoundError("No numeric chunks created")

        m = [Md5Utils.get_file_md5(p) for p in numeric_chunks]

        for idx, p in enumerate(numeric_chunks):
            suffix = img_md5 if idx == 0 else m[idx - 1]
            p.rename(p.with_name(f"{p.name}.{suffix}"))

        md5_list_path = path.parent / f"ota_md5_{path.name}.{img_md5}"
        md5_list_path.write_text("\n".join(m) + "\n", encoding="utf-8")

        return m

    @staticmethod
    def update_ota_file_with_new_rootfs_chunks(chunks_dir, ota_update_file, dry_run: bool=True):
        data_dicts, current_dict = [], {}
        for line in ota_update_file.read_text(encoding="utf-8").split("\n"):
            if line.strip() == "":
                if current_dict:
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
        img_size = sum(p.stat().st_size for p in chunks)
        img_md5 = chunks[0].name.split(".")[-1]  # the md5 key used for the first chunk

        ret_str = ""
        for data in data_dicts:
            if data.get("img_type") == "rootfs":
                data["img_size"] = str(img_size)
                data["img_md5"] = str(img_md5)
            for key, value in data.items():
                ret_str += f"{key}={value}\n"
            ret_str += "\n"

        print("(Dry) " if dry_run else "" + f"Updating {ota_update_file.name} with new rootfs info")
        if (dry_run):
            return
        ota_update_file.write_text(ret_str, encoding="utf-8")


class StorageModel:

    ROOTFS_FILENAME            : str = "rootfs.squashfs"
    OTA_MD5_ROOTFS_FILE_PREFIX : str = f"ota_md5_{ROOTFS_FILENAME}."
    CHUNKS_DIR_NAME            : str = "ota_v0"
    OTA_UPDATE_FILENAME        : str = "ota_update.in"

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    @cached_property
    def extracted_chunks_dir(self) -> Path:
        return self.base_dir / self.CHUNKS_DIR_NAME

    @cached_property
    def ota_update_path(self) -> Path:
        return self.extracted_chunks_dir / self.OTA_UPDATE_FILENAME

    @cached_property
    def rootfs_path(self) -> Path:
        return self.extracted_chunks_dir / self.ROOTFS_FILENAME

    @cached_property
    def extracted_rootfs_path(self) -> Path:
        return self.extracted_chunks_dir / f"{self.ROOTFS_FILENAME}_extracted"


class FirmwareExtractor:

    def __init__(self, firmware_path: Path) -> None:
        assert (firmware_path := firmware_path).is_file(), f"{firmware_path} is not a file!"
        self.firmware_path: Path = firmware_path

        self.storage_model = StorageModel(self.firmware_path.parent / f"{self.firmware_path.name}_extracted")

    def run(self, dry_run=True):
        # unzip the upt archive
        UptUtils.extract(self.firmware_path, self.storage_model.base_dir, dry_run)

        # concat all of the chunks into one rootfs file
        rootfs_path = RootFsUtils.convert_chunks_to_file(
            chunks_dir=self.storage_model.extracted_chunks_dir,
            chunk_pattern=f"{StorageModel.ROOTFS_FILENAME}.[0-9][0-9][0-9][0-9].*",
            output_path=self.storage_model.rootfs_path,
            dry_run=dry_run,
        )

        # convert the rootfs file to the read-only filesystem
        RootFsUtils.convert_file_to_file_system(
            rootfs_path=rootfs_path,
            output_dir=self.storage_model.extracted_rootfs_path,
            dry_run=dry_run,
        )


class ExtractedFirmwareBundler:
    
    def __init__(self, firmware_path: Path, extractor: FirmwareExtractor) -> None:
        assert firmware_path.is_file(), f"{firmware_path} is not a file!"
        assert extractor.storage_model.base_dir.is_dir(), f"{extractor.storage_model.base_dir} is not a dir!"
        self.firmware_path = firmware_path
        self.extractor = extractor

        self.storage_model = StorageModel(self.firmware_path.parent / f"{self.firmware_path.name}_bundle")

    def copy_extracted_dir(self, dry_run: bool=True):
        return run_command(f"sudo cp -a {self.extractor.storage_model.base_dir}{os.sep}. {self.storage_model.base_dir}", dry_run=dry_run)

    def remove_rootfs_files(self, dry_run=True):
        bundle_chunks_dir = self.storage_model.extracted_chunks_dir
        print("(DRY) " if dry_run else "" + f"Removing files prefixed with {StorageModel.ROOTFS_FILENAME} in {bundle_chunks_dir}")

        # remove the extracted rootfs dir FIRST (deleting chunks first via prefix finds this dir)
        run_command(f"sudo rm -r {self.storage_model.extracted_rootfs_path}", dry_run=dry_run)
        # remove the ota_md5_rootfs.squashfs.{MD5_KEY} file
        run_command(f"sudo rm {bundle_chunks_dir / f"{StorageModel.OTA_MD5_ROOTFS_FILE_PREFIX}*"}", dry_run=dry_run)
        # remove all of the rootfs chunks
        run_command(f"sudo rm {bundle_chunks_dir / f"{StorageModel.ROOTFS_FILENAME}*"}", dry_run=dry_run)

    def run(self, dry_run=True):
        # make a copy of the extracted dir under "{firmware name}_bundled"
        self.copy_extracted_dir(dry_run=dry_run)
        # remove the rootfs files since we need to "compile" those
        self.remove_rootfs_files(dry_run=dry_run)
    
        # convert the extracted file system to the singular rootfs file  
        rootfs_path = self.storage_model.rootfs_path
        RootFsUtils.convert_file_system_to_file(
            file_system_dir=self.extractor.storage_model.extracted_rootfs_path,
            output_path=rootfs_path,
            dry_run=dry_run
        )
        print(RootFsUtils.get_file_info(rootfs_path, dry_run=dry_run))
        # print(RootFsUtils.get_fs_xattrs(rootfs_path, dry_run=False))
        
        # convert the rootfs file to chunks
        RootFsUtils.convert_file_to_chunks(
            path=rootfs_path,
            bytes_per_chunk=524288,  # 512 KiB
            img_md5=Md5Utils.get_file_md5(rootfs_path),
            dry_run=dry_run
        )
        # remove the mother file
        rootfs_path.unlink()

        # ota_update.in needs to have the correct rootfs info
        RootFsUtils.update_ota_file_with_new_rootfs_chunks(
            chunks_dir=self.storage_model.extracted_chunks_dir,
            ota_update_file=self.storage_model.ota_update_path,
            dry_run=dry_run,
        )
        # bundle everything back into a upt file
        UptUtils.package(
            content_dir=self.storage_model.base_dir,
            output_path=Path(f"{self.firmware_path.name}"),
            dry_run=dry_run,
        )


def main():
    extractor = FirmwareExtractor(
        firmware_path=Path("firmware/r3proii.upt"),
    )
    extractor.run(dry_run=False)
    print(RootFsUtils.get_file_info(extractor.storage_model.rootfs_path, dry_run=False))
    # print(RootFsUtils.get_fs_xattrs(extractor.storage_model.rootfs_path, dry_run=False))

    run_command(
        f"bash scripts/add-adb-init.sh firmware/r3proii.upt_extracted/ota_v0/rootfs.squashfs_extracted",
        dry_run=False
    )

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

# sudo rm -rf firmware/r3proii.upt_bundle firmware/r3proii.upt_extracted

# adb push "C:\path\to\song.flac" /usr/data/mnt/sd_0/Music/
# Verify: adb shell "ls -la /usr/data/mnt/sd_0/Music"
