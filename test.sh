# everything in ota_v0 except rootfs chunks + rootfs md5 file + ota_update
(cd firmware/r3proii.upt_extracted/ota_v0 && \
  find . -maxdepth 1 -type f \
    ! -name 'rootfs.squashfs.*' \
    ! -name 'ota_md5_rootfs.squashfs.*' \
    ! -name 'ota_update.in' \
    -print0 | sort -z | xargs -0 md5sum) > /tmp/orig_nonroot.md5

(cd firmware/r3proii.upt_bundle/ota_v0 && \
  find . -maxdepth 1 -type f \
    ! -name 'rootfs.squashfs.*' \
    ! -name 'ota_md5_rootfs.squashfs.*' \
    ! -name 'ota_update.in' \
    -print0 | sort -z | xargs -0 md5sum) > /tmp/new_nonroot.md5

diff -u /tmp/orig_nonroot.md5 /tmp/new_nonroot.md5