#!/bin/bash
set -eu -o pipefail

# Get essential tools from apt repo
apt -y update
apt install -y --no-install-recommends curl xz-utils

dir_name=ffmpeg
mkdir $dir_name
pushd $dir_name

# Download compiled binaries and perform filehash checking
xz_name=$(
    curl -JOL https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz \
        -w "%{filename_effective}"
)
md5_name=$(
    curl -JOL https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz.md5 \
        -w "%{filename_effective}"
)
md5sum -c "$md5_name"

# Extract the archive
mkdir $dir_name
tar xvf "$xz_name" -C "$dir_name" --strip-components 1
cd $dir_name

# Move it to PATH
mv ffmpeg /bin/ffmpeg

popd

# Install Python dependencies
python -m venv /opt/venv
PATH=/opt/venv/bin:$PATH
pip install -r requirements.txt --no-cache-dir

exit 0
