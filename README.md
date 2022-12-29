# Road surface quality analysis via Garmin bike computers

This repository contains software to record acceleration sensor data on a
Garmin Edge bike computer, and to analyze this data in order to deduce the
surface quality of roads along a ride.

## BumpVisualizer

`BumpVisualizer` is a ConnectIQ (fullscreen) app that displays the latest
acceleration sensor data and has the ability to record rides that include this
data. `BumpTools` is a library used by it. It has only been tested on the Edge
530.

### Usage

Once started, the app shows a simple graph with the latest raw acceleration
sensor data along the z axis scrolling from right to left, updating every
second. The sample rate is displayed at the top. The escape button exits the
app.

The activity start/pause button starts/stops an activity recording that
includes fit file fields for position, speed, and all raw acceleration values
(z axis). An active recording is indicated at the top ("rec", under the sample
rate). The app must stay running (i.e. remain fullscreen) during recording.

The device must be set to 1s recording rather than smart recording. This is
important, because the app has to fit all samples (25 per second) into limited
space available in .fit file data fields. Smart recording only writes data
fields at irregular intervals, and the app doesn't know which data has already
been written. It also can't check which recording mode is used, but using smart
recording will lead to unusable or at least highly discontinuous data.

### Data format

When recording, the app adds data fields for position (longitude/latitude) and
speed (in the end result, these seem to be duplicated, once set by the app,
once natively by the SDK).

It also adds several fields to hold all raw acceleration values along the z
axis. This is necessary because it only gets to write data once per second, but
25 32-bit sensor samples (in milli-g) arrive in that time.

First, each sample is fit into 16 bits: all values are capped to the range
[-32767, 32768]. The value -32768 is used to represent a null value.

A fit file field can hold an array of 8 16-bit signed ints, so 4 such fields
are created, with names `accel_z_0-8`, `accel_z_8-16`, `accel_z_16-24`, and
`accel_z_24-32`. When new sensor data arrives once per second, the arrays are
filled with it in order, i.e. the earliest sample is the first element in
`accel_z_0-8`, the latest sample is the first and also the last element in
`accel_z_24-32`. All other values in the last field are set to null (i.e.
-32768). The app then relies on the 1s recording mode to write the current
values of these fields before the next batch of data arrives from the sensor.
