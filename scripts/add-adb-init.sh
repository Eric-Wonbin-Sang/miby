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

if [[ -f "$INITD/S90adb" ]]; then
  ts=$(date +%s)
  echo "[i] Backing up existing S90adb to S90adb.bak.$ts"
  sudo cp -a "$INITD/S90adb" "$INITD/S90adb.bak.$ts"
fi

# Create the improved init script with robust logging and UDC binding
sudo tee "$INITD/S90adb" >/dev/null <<'EOF'
#!/bin/sh

LOG="/usr/data/adb_boot.log"
TMPLOG="/tmp/adb_boot.log"
SDLOG="/mnt/sd0/adb_boot.log"

log() {
  echo "[S90adb] $*" >> "$TMPLOG"
  # Mirror to kernel log so we can see it via dmesg/serial
  echo "[S90adb] $*" > /dev/kmsg 2>/dev/null || true
}

bind_udc() {
  # Bind the gadget to the first available UDC
  UDC_NAME=$(ls /sys/class/udc/ 2>/dev/null | head -n1)
  if [ -n "$UDC_NAME" ] && [ -e /sys/kernel/config/usb_gadget/adb_demo/UDC ]; then
    echo "$UDC_NAME" > /sys/kernel/config/usb_gadget/adb_demo/UDC 2>>"$TMPLOG" || true
    log "UDC bind attempted: $UDC_NAME"
    sleep 1
    if [ -s /sys/kernel/config/usb_gadget/adb_demo/UDC ]; then
      log "UDC bound: $(cat /sys/kernel/config/usb_gadget/adb_demo/UDC 2>/dev/null)"
    else
      log "UDC binding not confirmed"
    fi
  else
    log "UDC path or name not available"
  fi
}

case "$1" in
  start)
    : > "$TMPLOG" 2>/dev/null || true
    log "=== S90adb start ==="
    date >> "$TMPLOG" 2>/dev/null || true

    # Enable ADB using vendor helper (stops mass storage, sets up gadget, starts adbd)
    /usr/bin/adbon >>"$TMPLOG" 2>&1 || true

    # Wait briefly for configfs gadget path to appear, then bind UDC
    for i in 1 2 3 4 5; do
      if [ -e /sys/kernel/config/usb_gadget/adb_demo/UDC ]; then
        log "adb_demo gadget present"
        break
      fi
      sleep 0.5
    done

    # Use vendor helper if present, otherwise bind directly
    if [ -e /sys/kernel/config/usb_gadget/adb_demo/UDC ]; then
      if [ -x /sbin/usb_adb_enable.sh ]; then
        /sbin/usb_adb_enable.sh >>"$TMPLOG" 2>&1 || true
        log "usb_adb_enable.sh invoked"
      fi
      bind_udc
    else
      log "adb_demo gadget path missing; skipping UDC bind"
    fi

    # Verify adbd is running
    if pidof adbd >/dev/null 2>&1; then
      log "adbd running (pid $(pidof adbd))"
    else
      log "adbd not running"
    fi

    # Try to persist log to /usr/data if available
    if [ -d /usr/data ] && touch "$LOG" 2>/dev/null; then
      cat "$TMPLOG" >> "$LOG" 2>/dev/null || true
      log "Log persisted to $LOG"
    fi

    # Also attempt to copy to SD card once it mounts (background retry)
    (
      for i in 1 2 3 4 5 6 7 8 9 10; do
        if mount | grep -q " /mnt/sd0 "; then
          cp "$TMPLOG" "$SDLOG" 2>/dev/null && log "Copied log to $SDLOG" && break
        fi
        sleep 1
      done
    ) &
    ;;
  stop)
    echo "=== S90adb stop ===" >> "$TMPLOG" 2>/dev/null || true
    [ -x /usr/bin/adboff ] && /usr/bin/adboff >>"$TMPLOG" 2>&1 || true
    ;;
esac

exit 0
EOF

# Set executable bit
sudo chmod 0755 "$INITD/S90adb"

echo "[✓] S90adb installed successfully"

# Also install a post-mount helper to copy logs to SD after it mounts
POSTMOUNT="$INITD/S92adb_postmount"
echo "[*] Installing S92adb_postmount into: $INITD"

sudo tee "$POSTMOUNT" >/dev/null <<'EOF'
#!/bin/sh

# Wait for the SD card to be mounted by sys_server, then persist logs there.
# sys_server mounts under /data/mnt/sd_0 (which is symlinked from /usr/data)

TMPLOG="/tmp/adb_boot.log"
USRLOG="/usr/data/adb_boot.log"
SD_DIRS="/data/mnt/sd_0 /usr/data/mnt/sd_0"

case "$1" in
  start)
    # Poll up to ~60s for SD to mount, then copy logs
    for i in 1 2 3 4 5 6 7 8 9 10 \
             11 12 13 14 15 16 17 18 19 20 \
             21 22 23 24 25 26 27 28 29 30 \
             31 32 33 34 35 36 37 38 39 40 \
             41 42 43 44 45 46 47 48 49 50 \
             51 52 53 54 55 56 57 58 59 60; do
      for d in $SD_DIRS; do
        if [ -d "$d" ] && mount | grep -q " $d "; then
          # Copy both temp and persisted logs if present
          [ -f "$TMPLOG" ] && cp "$TMPLOG" "$d/adb_boot.tmp.log" 2>/dev/null || true
          [ -f "$USRLOG" ] && cp "$USRLOG" "$d/adb_boot.log" 2>/dev/null || true
          # Leave a marker for debugging
          echo "S92adb_postmount copied logs at $(date)" >> "$d/adb_postmount_marker.txt" 2>/dev/null || true
          exit 0
        fi
      done
      sleep 1
    done &
    ;;
  stop)
    ;;
esac

exit 0
EOF

sudo chmod 0755 "$POSTMOUNT"
echo "[✓] S92adb_postmount installed successfully"
