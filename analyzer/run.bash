#!/bin/bash

. ~/.bashrc
pyenv activate garmin

attenuation=$1
track_lower_limit=$2
track_upper_limit=$3
spike_lower_limit=$4
spike_upper_limit=$5
if [[ -n $spike_lower_limit ]] ; then
    spike_args="--spike-lower-limit=$spike_lower_limit \
        --spike-upper-limit=$spike_upper_limit"
else
    spike_args="--no-spikes"
fi
config_description="attenuation:${attenuation}_\
track_range:${track_lower_limit}-${track_upper_limit}_\
spike_range:${spike_lower_limit}-${spike_upper_limit}"

rm -f fit/*.png

python src/analyze.py --save --save-suffix "${config_description}" \
    --track-time-slice=20 --spike-time-slice=5 \
    --attenuation=$attenuation --track-lower-limit=$track_lower_limit \
    --track-upper-limit=$track_upper_limit $spike_args fit/to* fit/from*

mkdir -p "out/${config_description}"
mv fit/*.png "out/${config_description}"
