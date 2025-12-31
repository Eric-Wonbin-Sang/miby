
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

# Modifying Firmware

There is a process that the original developers use for turning on ADB functionality, but they disable it before they sell them.

# Bundling Firmware

We more or less do the reverse of extracting the firmware:

- convert the file system into a rootfs.squash file
- split the file into chunks (with MD5 metadata appended to each name)
- update the metadata in ota_update.in to match the new MD5 data
- compress files back into a upt ISO file

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

# Interesting...

We can finally stop using those sites:

```powershell
# from YouTube URLs
yt-dlp.exe -f ba https://www.youtube.com/watch?v=8SZIvzdxcnE

# metadata + thumbnail embedded (artist is annoying)
yt-dlp.exe -f ba --extract-audio --audio-format flac --embed-metadata --embed-thumbnail <YOUTUBE_URL>
```

---

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

# sudo pacman -S binwalk
# sudo rm -rf firmware/r3proii.upt_bundle firmware/r3proii.upt_extracted

# Analyze the rootfs

```bash
# 3) confirm init system + list boot scripts in order

```

# Search for how the stock UI starts:

```bash
cd rootfs_extracted
grep -R "hiby" etc/ usr/ | head -n 50
```
