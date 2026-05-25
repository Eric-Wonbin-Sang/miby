
# Miby

Very early days, take everything with a grain of salt. Also, I want to make a video on this, so I'll link to it when I make it!

---

# What Is This

written on: 2025.12.31 01:32 EST AM

I used to an ipod a lot when I was younger. Spotify quickly replaced it after I got a phone and a job. I've been using premium for almost 8 years and actually look for new music maybe every 6 months, but I usually listen to the same stuff a lot of the time. Recently, I've started getting annoyed about some things:

- it used so much of my phone storage for music
- my phone (and bluetooth headphones) battery didn't last that long
- I felt like my music was managed poorly with the spotify app
- after all this time, I've paid close to a thousand dollars and own nothing

I like tech and retro-things, and I eventually started seeing posts about people modding the shit out of old ipods. While I think it's super cool, I didn't want to spend too much money because I know I would've maxed out the ipod if I went that route (rare self-regulation W), but I also wanted more features out of the box and I wanted to write my own software.

> Note - about RockBox:
>
>   I never really gave rockbox a chance because I vaguely saw some negative things 
>   about the learning experience and I thought I should be able to make what I want
>   if I wanted to. I think the software's ability to heavily theme the device is
>   incredible, as every user craves the ability to bend tools. Actually, on the
>   second day attempting to create custom firmware, I found out that [some people were
>   adding compatibility to the device I chose.](https://github.com/Rockbox/rockbox/commits/a8ff5597bdf82d2ce38c3a1b8857eb45ed93a0e4/firmware/target/hosted/hiby/r3proii/led-r3proii.c)
>
> I wish you guys the best of luck, this shit feels so annoying to deal with and
> I'm assuming you guys actually know what you're doing.

I just realized that the work was done a couple months ago, but the project is on hold now.

https://git.rockbox.org/cgit/rockbox.git/commit/?id=1183b1ab1b1166c986ce72e47942b75172cd96d7
https://codeberg.org/oopsallnaps/rockbox-hibyos
https://codeberg.org/oopsallnaps/rockbox-hibyos/issues/18

## Criteria

I liked the idea of the click wheel or some type of knob, but my main things were:

- small - I don't want it to feel like a phone, but I want enough space to type if you needed to
- battery life - I don't want to charge this too often
- bluetooth - while I'd use wired earbuds, I'd want the flexibility
- wifi - network connectivity for my own shenanigans

I watched a lot of videos on devices that looked a lot cooler than what I chose: the Hiby R3 Pro II. In my eyes, this was my best option. A big battery with a linux machine attached to it. It's ok, I can design and 3d print a case for it. I could even give it a dial that way.

I also found [this blog post from 2024-06-15 by Codecat.nl](https://codecat.nl/2024/06/hiby-r3ii-root/), which solidified my choice to get a Hiby product and attempt this.

They explained how the Hiby R3 II has a service that lets users upload and download files to your device via wifi, which has no access restrictions and would let you access any directories you wanted. There was also a way to just put a file called ota in the device's sd card which would execute it with root, so you could just arbitrarily execute anything. As someone who has never done any "hacking" before, this is a great reminder that you can make code do anything.

After seeing this work, I thought surely, this would be a piece of cake! I bought the device and none of the exploits worked anymore! Why patch these features when you've already released them to prod, who knows. Oh well, the blog does say this:

```
It would be pretty straight forward to build your own ISO update image and push that to the device, but I didn't feel like doing the work, so instead I looked through the executables on the device.
```

With my arch linux laptop in hand and a chatgpt subscription, anything is possible. After 5 days, I have figured out how to create custom firmware for the Hiby R3 Pro II.

## How does this work?

The wifi download/upload feature is actually a thttpd service:
https://www.acme.com/software/thttpd/

# Downloading Firmware

Hiby has its official firware on its site:
- [Hiby's firware page](https://store.hiby.com/apps/help-center#hc-r3pro-ii-firmware-v12-update)
- [specific google drive link of my current firmware version (1.3)](https://drive.google.com/drive/folders/1RcQ5gP0QnEpLH2rb1XABnSkVBsYx7giz)

# Extracting Firmware

There are a some steps we have to do to the upt file:

- uncompress the ISO file
- concatenate the rootfs.squash chunks into one file
- extract the file system from the rootfs.squash

## Dependencies

| item                 | command                         |
| -------------------- | ------------------------------- |
| 7-Zip                | `sudo pacman -S 7zip`           |
| unsquash / mksquash  | `sudo pacman -S squashfs-tools` |

# Understanding Firmware

bootloader -> linux -> busybox setup -> processes -> ui

On startup and shutdown, a group of scripts are run here:

```
> cd firmware/r3proii.upt_extracted/ota_v0/rootfs.squashfs_extracted
> ls -la etc/init.d
total 80
drwxr-xr-x  3 root root 4096 Dec 30 19:00 ./
drwxr-xr-x 11 root root 4096 Aug 30 05:49 ../
drwxr-xr-x  2 root root 4096 Aug 30 05:49 adb/
-rwxr-xr-x  1 root root  423 Jul 13  2024 rcK*  <-- shutdown scripts
-rwxr-xr-x  1 root root  428 Aug 30 05:49 rcS*  <-- startup scripts
-rwxr-xr-x  1 root root  493 Aug 30 05:49 S10mdev*
-rwxr-xr-x  1 root root  697 Aug 30 05:49 S11jpeg_display_shell*
-rwxrwxr-x  1 root root  125 Aug 30 05:47 S11module_driver_default*
-rwxr-xr-x  1 root root 1684 Jul 13  2024 S20urandom*
-rwxr-xr-x  1 root root  175 Aug 30 05:49 S21mount_ubifs*
-rwxr-xr-x  1 root root 1635 Jul 13  2024 S30dbus*
-rwxrwxr-x  1 root root  577 Jun  3  2024 S39_recovery.recovery*
-rwxr-xr-x  1 root root  438 Jul 13  2024 S40network*
-rwxrwxr-x  1 root root 2617 Aug 30 05:47 S43wifi_bcm_init_config*
-rwxrwxr-x  1 root root  268 Jun  3  2024 S50sys_server*
-rwxrwxr-x  1 root root  350 Jun  3  2024 S80_bt_init*
-rwxrwxr-x  1 root root  357 Jun  3  2024 S92_03_start_music_player*
-rwxr-xr-x  1 root root 1165 Dec 30 19:00 S92adb_postmount*
-rwxr-xr-x  1 root root  514 Aug 30 05:49 T90adb*
```
## Extracted firmware layout
The extraction process creates a workspace under `work/r3proii.upt_extracted/ota_v0`.

Key pieces of the extracted firmware are:

- `rootfs.squashfs`: the joined SquashFS image built from the original chunk files.
- `rootfs.squashfs_extracted`: the unpacked root filesystem tree where overlays are merged.
- `ota_update.in`: the update manifest with metadata for the device's OTA update process.
- `etc/init.d/`: the main startup/shutdown script directory; custom overlays inject new `S*` scripts here.
- `etc/dropbear/`, `root/.ssh`, and other overlay paths added by plugins like `dropbear` and `adb`.

The extracted rootfs is a standard Linux-style filesystem layout with some device-specific paths:

- `bin/`: essential user commands and busybox utilities used during boot and maintenance.
- `sbin/`: system administration binaries used by init scripts and system startup.
- `usr/bin/`, `usr/sbin/`, `usr/lib/`: the bulk of user programs, helper utilities, and shared libraries.
- `etc/`: configuration files, service definitions, network settings, and startup scripts.
- `lib/`: runtime libraries and firmware blobs required by the system.
- `root/`: root user home directory and SSH/Dropbear config hooks created by overlays.
- `mnt/sd_0/` and `mnt/udisk_0/`: mounted storage locations on the device where media and external files appear.
- `usr/data/`: device-specific writable data storage used by apps and services.
- `var/`: runtime state, logs, and webserver files like `var/www`.

Overlay injection works by copying overlay package contents into `rootfs.squashfs_extracted`, preserving permissions and symlinks. The rebuild process then re-compresses this tree into a new `rootfs.squashfs`, splits it into numbered chunks, updates `ota_update.in`, and packages the result back into a `.upt` ISO.

This means the files you want to modify should be present in the extracted rootfs tree before packing, and injected overlay scripts must be visible under `etc/init.d/` in `rootfs.squashfs_extracted`.

### Extracted filesystem contents
The unpacked rootfs is a full Linux-style filesystem tree with a few device-specific areas worth understanding:

- `bin/` and `sbin/`: core BusyBox/userland binaries and low-level system utilities used during boot and service startup.
- `etc/`: configuration, service startup scripts, network interface hooks, Dropbear config, and runtime environment settings.
  - `etc/init.d/`: the main boot/shutdown script directory.
  - `etc/network/`: network interface configuration and if-up/if-down hooks.
  - `etc/dropbear/`: SSH auth keys and Dropbear configuration added by the overlay.
- `lib/` and `usr/lib/`: shared libraries and firmware blobs used by services and hardware drivers.
- `usr/bin/` and `usr/sbin/`: additional user and system binaries beyond the core BusyBox set.
- `usr/resource/`: UI resources, fonts, layouts, strings, and app assets used by the device firmware.
- `usr/data/`: writable device data storage, including configuration overlays and persistent state.
- `root/`: root user home, which may be a symlink into `usr/data/` for persistent SSH files.
- `mnt/sd_0/` and `mnt/udisk_0/`: mounted storage locations for the device's SD card and USB/USB storage.
- `var/`: runtime state, logs, and webserver files such as `var/www`.

### The `etc/init.d` script flow
The device uses a simple init.d-style startup sequence:

- `rcS` is the general startup entrypoint.
- `rcK` is the shutdown entrypoint.
- `S*` scripts are run in numeric order during boot.
- `T*` scripts typically run at a later startup phase or as part of ADB-related service initialization.

In the extracted firmware, the present init scripts include:

- `S10mdev` – early device/driver initialization.
- `S11jpeg_display_shell` – display subsystem startup.
- `S11module_driver_default` – default module driver setup.
- `S20urandom` – random seed/hardware RNG initialization.
- `S21mount_ubifs` – mounting UBIFS storage.
- `S30dbus` – D-Bus service startup.
- `S40network` – network stack bring-up.
- `S43wifi_bcm_init_config` – Wi-Fi driver/config initialization.
- `S50sys_server` – system server process.
- `S80_bt_init` – Bluetooth stack startup.
- `T90adb` – ADB-related startup actions.

Overlay scripts add additional entries such as:

- `S91adb_enable` – enables ADB at boot.
- `S94miby_diag_predropbear` / `S99miby_diag_flush` – debug overlay hooks inserted by the debug plugins.
- `S95dropbear` – starts Dropbear SSH.

There is also an `etc/init.d/adb/` directory containing helper scripts used by the ADB service.

### What can be modified
If you want to change behavior on the device, these are the most useful places:

- `etc/init.d/` for startup/shutdown hooks and service launch scripts.
- `etc/network/interfaces` and `etc/network/if-*.d/` for network configuration and interface event handling.
- `etc/dropbear/authorized_keys.default` for SSH key-based login.
- `root/.ssh` / `usr/data/dropbear/root/.ssh` for persistent root SSH state.
- `usr/resource/` for UI assets, layouts, text translations, and device-specific resources.
- `mnt/sd_0/` and `mnt/udisk_0/` for placing files to be accessed by the device at runtime.

Because the firmware rebuild process preserves the extracted tree, you can experiment by placing or editing files in `rootfs.squashfs_extracted` and then repacking with `pack`. If you want changes to survive a fresh extract/build, create overlays that mirror the desired rootfs paths and inject them through the CLI.

# Modifying Firmware

There is a process that the original developers use for turning on ADB functionality, but they disable it before they sell them.

The scripts dir is where I put the scripts that I want added into the rootfs before bundling. The 

adb push /home/sang/local_coding_projects/miby/r3proii.upt ./
adb shell "ls -la /usr/data/mnt/sd_0/"
/data/mnt/sd_0

adb push r3proii.upt /usr/data/mnt/sd_0
adb shell "ls -la /usr/data/mnt/sd_0"

# Bundling Firmware

We more or less do the reverse of extracting the firmware:

- convert the file system into a rootfs.squash file
- split the file into chunks (with MD5 metadata appended to each name)
- update the metadata in ota_update.in to match the new MD5 data
- compress files back into a upt ISO file

## CLI Usage

The repository provides a CLI entrypoint at `tools/miby_build.py`.

### Global options

- `--root <path>`: repository root directory (defaults to current working directory)
- `--dry-run`: show actions without executing them
- `--status`: print the current project status and exit

### Commands

- `status`: show current project and Dropbear build status
- `extract <firmware_name> [--force]`: extract a source `.upt`, join rootfs chunks, and unpack the rootfs
- `dropbear-build [--force] [--redownload-source]`: download and build Dropbear for `mipsel`
- `dropbear-overlay [--public-key <path>] [--auto-start|--manual-start] [--show-indicator|--no-show-indicator] [--port <port>]`: create a Dropbear overlay package
- `inject-overlay <firmware_name> <overlay> [--force]`: apply an overlay into an extracted firmware rootfs
- `inject-dropbear <firmware_name> [--public-key <path>] [--auto-start|--manual-start] [--show-indicator|--no-show-indicator] [--port <port>] [--force]`: build Dropbear, create the overlay, and inject it
- `adb-overlay`: create an ADB overlay
- `adb-inject <firmware_name> [--force]`: create and inject the ADB overlay
- `pack <firmware_name> [--output <name>] [--force]`: package modified firmware into a new `.upt`
- `full <firmware_name> [--dropbear] [--adb] [--public-key <path>] [--output <name>] [--force]`: run extract, optional overlays, and pack

### Example usage

```bash
python3 tools/miby_build.py --status
python3 tools/miby_build.py status
python3 tools/miby_build.py extract r3proii.upt --force
python3 tools/miby_build.py dropbear-build --force
python3 tools/miby_build.py dropbear-overlay --public-key /path/to/key.pub --port 2222
python3 tools/miby_build.py adb-overlay
python3 tools/miby_build.py inject-dropbear r3proii.upt --force
python3 tools/miby_build.py inject-adb r3proii.upt --force
python3 tools/miby_build.py pack r3proii.upt --output r3proii_miby.upt
python3 tools/miby_build.py full r3proii.upt --dropbear --output r3proii_dropbear_miby.upt
python3 tools/miby_build.py full r3proii.upt --adb --output r3proii_adb_miby.upt
python3 tools/miby_build.py full r3proii.upt --dropbear --adb --output r3proii_full_miby.upt

# for a full run with public key injection
cd /mnt/c/Users/ericw/local-coding-projects/miby && python3 tools/miby_build.py full r3proii.upt --dropbear --adb --public-key /home/ericw/.ssh/id_ed25519.pub --output r3proii_full_miby.upt --force && ls -la output/r3proii_full_miby.upt && du -h output/r3proii_full_miby.upt

# step by step
python3 tools/miby_build.py overlays

# build
python3 tools/miby_build.py overlay-build dropbear --public-key /home/ericw/.ssh/id_ed25519.pub
# or
python3 tools/miby_build.py overlay-build --all --public-key /home/ericw/.ssh/id_ed25519.pub

# inject
python3 tools/miby_build.py extract r3proii.upt --force

python3 tools/miby_build.py inject-overlays r3proii.upt \
  dropbear adb debug_predropbear debug_log_flush \
  --public-key /home/ericw/.ssh/id_ed25519.pub \
  --force

python3 tools/miby_build.py pack r3proii.upt \
  --force \
  --output r3proii_full_miby.upt

# ---- full build ----

python3 tools/miby_build.py full r3proii.upt \
  --overlays dropbear adb debug_predropbear debug_log_flush \
  --public-key /home/ericw/.ssh/id_ed25519.pub \
  --force \
  --output r3proii_full_miby.upt
```

# Flashing Firmware

## Dependencies

| item                 | command                         |
| -------------------- | ------------------------------- |
| Android Debug Bridge | `sudo pacman -S android-tools`  |

## For Accessing the Device's Shell

With adb enabled on the device (see "Modifying Firmware"), you can access the device shell. Plug your device into your machine and run:

```bash
adb start-server

# this is easier when troubleshooting
adb kill-server && adb devices
```

If your device is detected:

```bash
> adb devices
List of devices attached
ingenic_2233	device
```

You should be able to access its shell with the root user:

```bash
# open the device's interactive shell
adb shell
# run arbitrary commands
adb shell "ls -la /data/mnt/sd_0"
# upload files from your machine to the device
adb push /my/legal/media /usr/data/mnt/sd_0/
# download files from the device to your machine
adb pull /usr/data/mnt/sd_0/file /my/new/pit/
```

Do you need this?
https://developer.android.com/studio/run/win-usb

# Enabling SSH

2026.05.22

The device can connect to wifi. I want to enable ssh so I can interact with it without a cable. 


# Music Discovery

We can finally stop using those sites:

```powershell
# from YouTube URLs
yt-dlp.exe -f ba https://www.youtube.com/watch?v=8SZIvzdxcnE

# metadata + thumbnail embedded (artist is annoying)
yt-dlp.exe -f ba --extract-audio --audio-format flac --embed-metadata --embed-thumbnail <YOUTUBE_URL>
```

---

# New Build System Layout

This repository now includes a small reusable firmware build system under `tools/miby_core`.

- `firmware/sources/` holds all source `.upt` firmware files.
- `work/` holds extracted firmware workspaces and tool artifacts.
- `overlays/` contains filesystem overlays that map host paths into the extracted rootfs.
- `output/` is where custom firmware packages are written.
- `tools/miby_build.py` is the CLI entrypoint.
- `tools/miby_core/` contains the reusable build logic.

The CLI supports these workflows:

- `status` — inspect available firmware, workspaces, and dropbear build state.
- `extract <firmware>` — extract a `.upt`, join rootfs chunks, and unpack the SquashFS rootfs.
- `dropbear-build` — download and build the mipsel Dropbear toolchain.
- `dropbear-overlay` — create an overlay that installs Dropbear and startup scripts.
- `inject-overlay <firmware> <overlay>` — apply an overlay into the extracted rootfs.
- `inject-dropbear <firmware>` — build Dropbear, create the overlay, and inject it.
- `pack <firmware>` — rebuild a custom `.upt` from the modified workspace.
- `full <firmware>` — run extract, optional Dropbear injection, and pack in one command.

## Directory layout for custom firmware

```
firmware/
  sources/
    r3proii.upt
work/
  tools/
    dropbear/
  r3proii.upt_extracted/
  r3proii.upt_bundle/
overlays/
  dropbear/
output/
tools/
  miby_build.py
  miby_core/
    __init__.py
    context.py
    command.py
    status.py
    firmware.py
    rootfs.py
    overlay.py
    dropbear.py
    cli.py
```

This structure keeps multiple firmware versions independent, and lets the UI call the same build logic later.

---

## Overlays

Overlays are now modular and discovered from `tools/overlays/<name>/`.

- Place static files in `tools/overlays/<name>/files/` mirroring the target rootfs layout (for example `files/etc/init.d/S95dropbear`).
- Implement optional overlay build logic in `tools/overlays/<name>/overlay.py` by subclassing the provided `FirmwareOverlay` base class.
- Use the CLI to list, build, and inject overlays:

```bash
python3 tools/miby_build.py overlays
python3 tools/miby_build.py overlay-build --all --public-key /path/to/key.pub
python3 tools/miby_build.py inject-overlays r3proii.upt dropbear adb debug_predropbear debug_log_flush --force
```

Generated overlays are written to `overlays/<name>/` and are injected into the extracted rootfs before packaging.

TODO

# Custom Device UI

# Custom Case

Retro Inspired Case

# Custom Desktop App

Emulate the device UI (and more) by pointing to your local files.

# Music Indexing

Songs and siblings have their relationships with playlists, albums, and artists shown.

# Device to Desktop Syncing

Control music via my machine while having the device connected to my audio interface.
Syncing music with my machine.

# Music Search

youtube, soulseek, bandcamp, spotify, soundcloud

# Spotify Metadata Inclusion

Times like these make me question our reality.

---

# Put these somewhere

sudo pacman -S binwalk
sudo rm -rf firmware/r3proii.upt_bundle firmware/r3proii.upt_extracted

Analyze the rootfs

```bash
# 3) confirm init system + list boot scripts in order

```

Search for how the stock UI starts:

```bash
cd rootfs_extracted
grep -R "hiby" etc/ usr/ | head -n 50
```
