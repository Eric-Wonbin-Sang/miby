

Very early days, take everything with a grain of salt.


This blog was what inspired me to take this challenge on:
https://codecat.nl/2024/06/hiby-r3ii-root/


Hiby firware page
- https://store.hiby.com/apps/help-center#hc-r3pro-ii-firmware-v12-update
specific google drive link of my current firmware version
- https://drive.google.com/drive/folders/1RcQ5gP0QnEpLH2rb1XABnSkVBsYx7giz


There is a way to download and upload files to your dap via this thttpd service that runs (sd card must be in the device)
https://www.acme.com/software/thttpd/



## Dependencies

Install the 7-Zip command-line utilities so this project can call `7z.exe` to unpack the
`.upt` firmware archives.

Download: https://www.7-zip.org/download.html

The script automatically prepends a few common folders (cargo's bin directory plus the 7-Zip
install directories) to `PATH`, but you can override detection by setting `SEVEN_ZIP_EXE`
to the full path of `7z.exe` before running `python main.py`.


The firmware


## Manual Steps

On Windows

It's easy to do this in WSL:

C drive dir: /mnt/c/LocalCodingProjects/miby/firmware/extracts/r3proii
WSL dir: ~/projects/hiby

```bash
cd /mnt/c/LocalCodingProjects/miby/firmware/extracts/r3proii
```

# Extract the firmware from the .upt file

```bash
# I used 7zip
```

# Taking the extracted firmware and converting it to the rootfs

```bash
# make some place to put our work
mkdir -p ~/projects/hiby
# copy the extracted files from your Windows files to the WSL location
cp -r ota_v0 ~/projects/hiby/
# go to the copied dir
cd ~/projects/hiby/ota_v0
# create the concatenated file and put it in the hiby dir
cat rootfs.squashfs.* > ../rootfs.squashfs
# convert the full file into the actual filesystem the device uses
unsquashfs -d rootfs_extracted rootfs.squashfs
```

# Analyze the rootfs

```bash
# 3) confirm init system + list boot scripts in order
cd rootfs_extracted
ls -la etc/init.d
ls -la etc/init.d/S* 2>/dev/null | head -n 50
ls -la etc/init.d/S* 2>/dev/null | tail -n 50

# 4) read the boot/shutdown dispatchers
sed -n '1,260p' etc/init.d/rcS
sed -n '1,260p' etc/init.d/rcK

```




ls -la usr/bin/adbon usr/bin/adboff sbin/adbserver.sh sbin/kill_adbserver.sh 2>/dev/null
file usr/bin/adbon usr/bin/adboff sbin/adbserver.sh sbin/kill_adbserver.sh 2>/dev/null



# Repackage the modified rootfs file

```bash

python3 make_ota.py --rootfs firmware/rootfs.squashfs --out firmware/extracts/ota_output

python3 make_ota.py \
  --version 0 \
  --rootfs /home/ericw/projects/hiby/build/rootfs.squashfs \
  --out firmware/extracts/ota_output \
  --kernel-name xImage \
  --kernel-size 3760192 \
  --kernel-md5 4a459b51a152014bfab6c1114f2701e3
```


# Search for how the stock UI starts:

```bash
cd rootfs_extracted
grep -R "hiby" etc/ usr/ | head -n 50
```

# Check the things that start up with the files in this dir:

```bash
ls etc/init.d
```

```bash
cat etc/inittab 2>/dev/null
```

If inittab exists → you’ll see boot/runlevel configuration
If it doesn’t → nothing prints (error is suppressed by 2>/dev/null)
This is not an error — many embedded systems don’t use inittab.

# Downloading music from YouTube URLs

yt-dlp.exe -f ba https://www.youtube.com/watch?v=InCadnlRoe4&list=RDInCadnlRoe4&start_radio=1

metadata + thumbnail embedded (nice for music libraries)
yt-dlp.exe -f ba --extract-audio --audio-format flac --embed-metadata --embed-thumbnail <YOUTUBE_URL>





https://developer.android.com/studio/run/win-usb