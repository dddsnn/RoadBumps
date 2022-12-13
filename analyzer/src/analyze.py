import collections
import dataclasses as dc
import datetime
import functools as ft
import itertools as it
import logging
import math
import re
import sys

import cartopy.crs
import cartopy.io.img_tiles
import cartopy.mpl.geoaxes
import colour
import fitparse
import matplotlib.pyplot as plt
import shapely.geometry

logger = None


def setup_logging():
    logging.basicConfig(level=logging.INFO)


class ParseError(Exception):
    pass


@dc.dataclass
class Position:
    import datetime
    ts: datetime.datetime
    lon: float
    lat: float
    speed: float
    accel: float
    analysis_data: dict = dc.field(default_factory=dict)

    @property
    def speed_kph(self):
        return self._mps_to_kph(self.speed)

    @staticmethod
    def _mps_to_kph(mps):
        return mps * 3.6


class Track:
    EXPECTED_ACCEL_VALUES_PER_MESSAGE = 25

    def __init__(self, positions):
        self._positions = positions

    @classmethod
    def from_path(cls, file_path):
        with open(file_path, 'rb') as file:
            fit_file = fitparse.FitFile(file)
            fit_file.parse()
        positions = []
        for message in fit_file.messages:
            ts = cls._field_value(message, 'timestamp', datetime.datetime)
            lon_semicircles = cls._field_value(message, 'position_long')
            lat_semicircles = cls._field_value(message, 'position_lat')
            speed = cls._field_value(message, 'enhanced_speed')
            accel_fields = sorted((
                field for field in message.fields
                if field.name.startswith('accel')),
                                  key=cls._accel_field_bounds)
            accel_fields = accel_fields or None
            data_fields = [
                lon_semicircles, lat_semicircles, speed, accel_fields]
            if not all(v is not None for v in [ts] + data_fields):
                if any(v is not None for v in data_fields):
                    logger.warning(
                        'Not all expected values were present, but some were '
                        f'({data_fields}).')
                continue
            cls._assert_valid_accel_fields(accel_fields)
            accels = cls._extract_accels(accel_fields)
            for accel in cls._adjusted_accels(accels):
                positions.append(
                    Position(
                        ts, cls._semicircles_to_deg(lon_semicircles),
                        cls._semicircles_to_deg(lat_semicircles), speed,
                        accel))
        cls._check_consecutive_positions(positions)
        return cls(positions)

    @classmethod
    def _field_value(cls, message, name, field_type=None):
        try:
            return next(
                field.value
                for field in message.fields
                if field.name == name and (
                    field_type is None or isinstance(field.value, field_type)))
        except StopIteration:
            return None

    @classmethod
    def _assert_valid_accel_fields(cls, accel_fields):
        if cls._accel_field_bounds(accel_fields[0])[0] != 0:
            raise ParseError('Acceleration fields don\'t start at 0.')
        for f1, f2 in it.pairwise(accel_fields):
            _, end1 = cls._accel_field_bounds(f1)
            start2, _ = cls._accel_field_bounds(f2)
            if start2 != end1:
                raise ParseError('Acceleration fields aren\'t consecutive.')

    @classmethod
    def _accel_field_bounds(cls, field):
        match = re.match(r'accel_z_(\d+)-(\d+)', field.name)
        if not match or len(match.groups()) != 2:
            raise ParseError(f'Invalid acceleration field name {field.name}.')
        return int(match.group(1)), int(match.group(2))

    @classmethod
    def _extract_accels(cls, accel_fields):
        accels = []
        num_out_of_bounds = 0
        reached_end = False
        for f in accel_fields:
            start, end = cls._accel_field_bounds(f)
            if len(f.value) != end - start:
                raise ParseError('Mismatched acceleration value counts.')
            for raw_accel in f.value:
                accel = cls._parse_raw_accel(raw_accel)
                if accel is None:
                    reached_end = True
                    continue
                elif reached_end:
                    raise ParseError(
                        'Encountered acceleration value after first null.')
                if math.isinf(accel):
                    num_out_of_bounds += 1
                accels.append(accel)
        if len(accels) != cls.EXPECTED_ACCEL_VALUES_PER_MESSAGE:
            raise ParseError(
                f'Unexpected number of acceleration values ({len(accels)}).')
        return accels

    @classmethod
    def _parse_raw_accel(cls, raw_accel):
        if raw_accel == -32768:
            return None
        if raw_accel == -32767:
            return float('-inf')
        if raw_accel == 32767:
            return float('inf')
        return raw_accel

    @classmethod
    def _adjusted_accels(cls, accels):
        return [a + 1000 for a in accels]

    @classmethod
    def _semicircles_to_deg(cls, semicircles):
        return math.degrees((semicircles * math.pi) / 0x80000000)

    @classmethod
    def _check_consecutive_positions(cls, positions):
        for p1, p2 in it.pairwise(positions):
            same_ts = p1.ts == p2.ts
            one_second_apart = p1.ts + datetime.timedelta(seconds=1) == p2.ts
            if not same_ts and not one_second_apart:
                logger.warning(
                    'Position timestamps don\'t have equal or consecutive '
                    f'timestamps: {p1.ts} - {p2.ts}.')

    @property
    def positions(self):
        return self._positions

    @property
    @ft.cache
    def bounds(self):
        min_lon = min_lat = float('inf')
        max_lon = max_lat = float('-inf')
        for p in self.positions:
            min_lon, max_lon = min(min_lon, p.lon), max(max_lon, p.lon)
            min_lat, max_lat = min(min_lat, p.lat), max(max_lat, p.lat)
        return min_lon, min_lat, max_lon, max_lat

    @property
    def tss(self):
        return [p.ts for p in self.positions]

    @property
    def accels(self):
        return [p.accel for p in self.positions]

    @property
    def speeds_kph(self):
        return [p.speed_kph for p in self.positions]

    def rolling_average_absolute_accels(
            self, window_duration_seconds, attenuate_by_speed=False):
        self.ensure_rolling_average_absolute_accels(
            window_duration_seconds, attenuate_by_speed)
        key = (
            'rolling_average_absolute_accels', window_duration_seconds,
            attenuate_by_speed)
        return [p.analysis_data[key] for p in self.positions]

    def ensure_rolling_average_absolute_accels(
            self, window_duration_seconds, attenuate_by_speed):
        key = (
            'rolling_average_absolute_accels', window_duration_seconds,
            attenuate_by_speed)
        if not self.positions or key in self.positions[0].analysis_data:
            return
        window_duration = datetime.timedelta(seconds=window_duration_seconds)
        window = collections.deque()
        for position in self.positions:
            window.append(position)
            min_ts = position.ts - window_duration
            while window[0].ts < min_ts:
                window.popleft()
            absolute_accel = sum(abs(p.accel) for p in window) / len(window)
            if attenuate_by_speed:
                absolute_accel = self._attenuate_by_speed(
                    absolute_accel, position.speed_kph)
            position.analysis_data[key] = absolute_accel

    def _attenuate_by_speed(self, accel, speed_kph):
        fraction_on_the_way_to_40 = min(speed_kph, 40) / 40
        factor = 1 - (fraction_on_the_way_to_40**2 * 0.75)
        return factor * accel

    def low_pass_absolute_accels(self, min_accel):
        filtered_accels = []
        for accel in self.accels:
            if accel >= min_accel:
                filtered_accels.append(accel)
            else:
                filtered_accels.append(0)
        return filtered_accels

    def time_slices(self, duration_seconds):
        slice_duration = datetime.timedelta(seconds=duration_seconds)
        positions = iter(self.positions)
        current_slice = []
        while True:
            try:
                current_duration = current_slice[-1].ts - current_slice[0].ts
                if current_duration >= slice_duration:
                    yield current_slice
                    current_slice = []
            except IndexError:
                pass
            try:
                current_slice.append(next(positions))
            except StopIteration:
                if current_slice:
                    yield current_slice
                return


def main():
    if len(sys.argv) != 2:
        raise ValueError('Specify one file to process.')
    analyze_files(sys.argv[1])


def analyze_files(file_path):
    if not file_path.endswith('.fit'):
        raise ValueError(f'{file_path} doesn\'t look like a .fit file.')
    file_base_path = file_path[:-4]
    track = Track.from_path(file_path)
    plot_track(track)


def plot_track(track):
    figure = plt.figure()
    gridspec = figure.add_gridspec(
        3, 2, figure=figure, height_ratios=[2, 1, 2])
    add_dynamics_subplots(
        track, figure, [gridspec[0, 0:1], gridspec[1, 0:1], gridspec[2, 0:1]],
        min_spike_millig=3000)
    map_subplot = MapSubplot(figure, gridspec[0:, 1], min_spike_millig=3000)
    map_subplot.plot(track)
    plt.show()


def add_dynamics_subplots(track, figure, gridspecs, min_spike_millig=3000):
    assert len(gridspecs) == 3
    accel_axes = figure.add_subplot(gridspecs[0])
    speed_axes = figure.add_subplot(gridspecs[1], sharex=accel_axes)
    accel_analysis_axes = figure.add_subplot(gridspecs[2], sharex=accel_axes)
    accel_axes.plot(track.tss, track.accels, color='black')
    accel_axes.yaxis.set_label_text('mg')
    speed_axes.plot(track.tss, track.speeds_kph, color='black')
    speed_axes.yaxis.set_label_text('km/h')
    accel_analysis_axes.plot(
        track.tss, track.rolling_average_absolute_accels(10), color='black')
    accel_analysis_axes.plot(
        track.tss,
        track.rolling_average_absolute_accels(10, attenuate_by_speed=True),
        color='blue')
    # TODO give low pass its own y axis so it doesn't mess up the scale of the average data++++++++++
    accel_analysis_axes.plot(
        track.tss, track.low_pass_absolute_accels(min_spike_millig),
        color='red')
    accel_analysis_axes.yaxis.set_label_text('mg')


class MapSubplot:
    TRACK_TIME_SLICE_SECONDS = 10
    SPIKE_TIME_SLICE_SECONDS = 1

    def __init__(
            self, figure, gridspec, rolling_average_window_duration_seconds=10,
            red_limit_millig=400, min_spike_millig=3000):
        self.figure = figure
        self.gridspec = gridspec
        self.rolling_average_window_duration_seconds = (
            rolling_average_window_duration_seconds)
        self.red_limit_millig = red_limit_millig
        self.min_spike_millig = min_spike_millig
        self._axes = None
        self.projection = cartopy.crs.Mercator()
        self.color_gradient = list(
            colour.Color('green').range_to(colour.Color('red'), 101))

    def plot(self, track):
        self._axes = self.figure.add_subplot(
            self.gridspec, axes_class=self._geo_axes_class_with_projection())
        extent = self._buffered_bounds(track.bounds, 0.1)
        self._axes.set_extent(extent, crs=self.projection.as_geodetic())
        self._axes.add_image(
            cartopy.io.img_tiles.OSM(desired_tile_form='L'),
            self._zoom_level_for_extent(*extent), cmap='gray')
        self._plot_track(track)
        self._plot_spikes(track)

    def _plot_track(self, track):
        track.ensure_rolling_average_absolute_accels(
            self.rolling_average_window_duration_seconds, True)
        for slice in track.time_slices(self.TRACK_TIME_SLICE_SECONDS):
            line = shapely.geometry.LineString((p.lon, p.lat) for p in slice)
            att_abs_accels = [
                p.analysis_data[(
                    'rolling_average_absolute_accels',
                    self.rolling_average_window_duration_seconds, True)]
                for p in slice]
            avg_att_abs_accel = sum(att_abs_accels) / len(att_abs_accels)
            self._axes.add_geometries(
                [line], self.projection.as_geodetic(), linewidth=3,
                edgecolor=self._color_for_accel(avg_att_abs_accel),
                facecolor='none')

    def _plot_spikes(self, track):
        xs, ys = [], []
        for slice in track.time_slices(self.SPIKE_TIME_SLICE_SECONDS):
            if any(abs(p.accel) >= self.min_spike_millig for p in slice):
                mid = slice[len(slice) // 2]
                xs.append(mid.lon)
                ys.append(mid.lat)
        if xs:
            self._axes.scatter(
                x=xs, y=ys, s=100, facecolor='purple',
                transform=self.projection.as_geodetic())

    def _geo_axes_class_with_projection(self):
        projection = self.projection

        class GeoAxes(cartopy.mpl.geoaxes.GeoAxes):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs, projection=projection)

        return GeoAxes

    @staticmethod
    def _zoom_level_for_extent(min_lon, max_lon, min_lat, max_lat):
        lon_fraction = (max_lon - min_lon) / 90
        lat_fraction = (max_lat - min_lat) / 180
        doublings = math.log2(1 / max(lon_fraction, lat_fraction))
        # Zoom level 2 as base for the entire world.
        return 2 + math.ceil(doublings)

    @staticmethod
    def _buffered_bounds(bounds, buffer_fraction):
        min_x, min_y, max_x, max_y = bounds
        width = max_x - min_x
        height = max_y - min_y
        buffer_x = width * buffer_fraction
        buffer_y = height * buffer_fraction
        return (
            min_x - buffer_x, max_x + buffer_x, min_y - buffer_y,
            max_y + buffer_y)

    def _color_for_accel(self, abs_accel_millig):
        fraction_to_max = min(1, abs_accel_millig / self.red_limit_millig)
        percent_to_max = int(fraction_to_max * 100)
        return self.color_gradient[percent_to_max].hex


if __name__ == '__main__':
    setup_logging()
    logger = logging.getLogger(__name__)
    main()
