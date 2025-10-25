#!/bin/bash
set -eu -o pipefail

apt-get -y update
apt-get install -y --no-install-recommends curl xz-utils

# https://serverfault.com/a/984599
# Allow users to run the container with arbitary user ID
mkdir -m 777 gallery-dl
mkdir -m 777 volume

dir_name=ffmpeg
mkdir ../$dir_name

pushd ../$dir_name

# TODO: Build a static FFMPEG instead of downloading
xz_name=$(
    curl -JOL https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linux64-gpl.tar.xz \
        -w "%{filename_effective}" --retry 3 --retry-all-errors
)
sha256_name=$(
    curl -JOL https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/checksums.sha256 \
        -w "%{filename_effective}" --retry 3 --retry-all-errors
)
sha256sum -c "$sha256_name" --ignore-missing

# Extract the archive and move FFMPEG to a fixed path
tar xvf "$xz_name" --strip-components 1
mv ./bin/ffmpeg /bin/ffmpeg

popd

# Install Python dependencies
uv sync

exit 0
