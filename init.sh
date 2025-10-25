#!/bin/bash
set -eu -o pipefail

# Get essential tools from apt repo
apt -y update
apt install -y --no-install-recommends curl xz-utils

dir_name=ffmpeg
mkdir ../$dir_name
pushd ../$dir_name

# Download compiled FFMPEG binary and perform filehash checking
# TODO: Build a static FFMPEG instead of downloading
xz_name=$(
    curl -JOL https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz \
        -w "%{filename_effective}" --retry 3 --retry-all-errors
)
md5_name=$(
    curl -JOL https://johnvansickle.com/ffmpeg/builds/ffmpeg-git-amd64-static.tar.xz.md5 \
        -w "%{filename_effective}" --retry 3 --retry-all-errors
)
md5sum -c "$md5_name"

# Extract the archive and move FFMPEG to PATH
tar xvf "$xz_name" --strip-components 1
mv ffmpeg /bin/ffmpeg

popd

# Install Python dependencies
uv sync

# Use `chmod 777` here instead of `chown nonroot` in case user wants to use their own docker user
chmod -R 777 ./

exit 0
