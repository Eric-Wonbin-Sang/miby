#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   bash add-adb-init.sh /path/to/rootfs.squashfs_extracted
#   bash scripts/add-adb-init.sh firmware/r3proii.upt_extracted/ota_v0/rootfs.squashfs_extracted

ROOTFS="${1:-}"

if [[ -z "$ROOTFS" ]]; then
  echo "Usage: $0 <rootfs_extracted_path>"
  exit 1
fi

INITD="$ROOTFS/etc/init.d"

echo "[*] Installing S90adb into: $INITD"

# Ensure init.d exists with correct perms
sudo install -d -m 0755 "$INITD"

# Create the init script
sudo tee "$INITD/S90adb" >/dev/null <<'EOF'
#!/bin/sh

LOG="/usr/data/adb_boot.log"
SDLOG="/mnt/sd0/adb_boot.log"

case "$1" in
  start)
    {
      echo "=== S90adb start ==="
      date
      echo "--- ls -la /usr/data ---"
      ls -la /usr/data
      echo
    } >> "$LOG" 2>&1

    # Enable ADB using vendor helper
    /usr/bin/adbon

    if [ -e /sys/kernel/config/usb_gadget/adb_demo/UDC ]; then
      /sbin/usb_adb_enable.sh
    fi

    # If SD card is mounted, also write there
    if mount | grep -q " /mnt/sd0 "; then
      cp "$LOG" "$SDLOG"
    fi
    ;;
  stop)
    echo "=== S90adb stop ===" >> "$LOG"
    [ -x /usr/bin/adboff ] && /usr/bin/adboff
    ;;
esac

exit 0
EOF

# Set executable bit
sudo chmod 0755 "$INITD/S90adb"

echo "[✓] S90adb installed successfully"