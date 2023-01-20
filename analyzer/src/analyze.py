import argparse
import collections
import dataclasses as dc
import datetime
import functools as ft
import itertools as it
import logging
import math
import pathlib
import re

import cartopy
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


def capped_fraction(value, reference):
    return min(1, value / reference)


class ParseError(Exception):
    pass


class IncompletePositionData(Exception):
    """
    Raised during message parsing if necessary position data is missing.

    This can be the case simply if the message is not a position message, or if
    some fields are missing (usually if there is no GNSS fix yet, but the
    acceleration sensor already works).
    """


@dc.dataclass
class Position:
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


class Attenuator:
    """
    A method of attenuating acceleration by speed.

    Attenuates a given acceleration a at speed v to a_att as

    a_att = (1 - (min(1, v / v_cap) ** exp) * att) * a

    Here, v_cap is the speed at which maximum attenuation is applied (i.e.
    higher speeds get the same attenuation), exp is an exponent for nonlinear
    attenuation, and att is the amount of attenuation to apply at the speed
    cap.

    Specify an attenation as a string with format
    "(linear|quadratic|cubic),<v_cap>,<att>", where the first argument
    determines exp.
    """
    _exponents = (('linear', 1), ('quadratic', 2), ('cubic', 3))

    def __init__(self, spec):
        try:
            args = spec.split(',')
            self.exponent = next(e for m, e in self._exponents if m == args[0])
            self.speed_cap = float(args[1])
            self.attenuation_at_max_speed = float(args[2])
            assert 0 <= self.attenuation_at_max_speed <= 1
        except Exception as e:
            raise ValueError(
                'Invalid attenation specification, must be '
                '"(linear|quadratic|cubic),<v_cap>,<att>" with 0 <= att <= 1.'
            ) from e

    @property
    def spec(self):
        method = next(m for m, e in self._exponents if e == self.exponent)
        return f'{method},{self.speed_cap},{self.attenuation_at_max_speed}'

    def __eq__(self, other):
        return self.spec == other.spec

    def __hash__(self):
        return hash(self.spec)

    def attenuate(self, accel, speed_kph):
        fraction_of_max_speed = capped_fraction(speed_kph, self.speed_cap)
        attenuation = ((fraction_of_max_speed**self.exponent)
                       * self.attenuation_at_max_speed)
        return (1 - attenuation) * accel


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
            try:
                ts, lon_semicircles, lat_semicircles, speed, accels = (
                    cls._extract_position_data(message))
            except IncompletePositionData:
                continue
            seconds_per_accel = datetime.timedelta(seconds=1 / len(accels))
            for i, accel in enumerate(accels):
                positions.append(
                    Position(
                        ts + i * seconds_per_accel,
                        cls._semicircles_to_deg(lon_semicircles),
                        cls._semicircles_to_deg(lat_semicircles), speed,
                        cls._adjusted_accel(accel)))
        cls._check_position_continuity(fit_file.messages, positions)
        return cls(positions)

    @classmethod
    def _extract_position_data(cls, message):
        ts = cls._field_value(message, 'timestamp', datetime.datetime)
        lon_semicircles = cls._field_value(message, 'position_long')
        lat_semicircles = cls._field_value(message, 'position_lat')
        speed = cls._field_value(message, 'enhanced_speed')
        accel_fields = sorted((
            field for field in message.fields
            if field.name.startswith('accel')), key=cls._accel_field_bounds)
        accel_fields = accel_fields or None
        data_fields = [lon_semicircles, lat_semicircles, speed, accel_fields]
        if not all(v is not None for v in [ts] + data_fields):
            if any(v is not None for v in data_fields):
                raise IncompletePositionData(
                    'Not all expected values were present, but some were.')
            else:
                raise IncompletePositionData('Not a position message.')
        cls._assert_valid_accel_fields(accel_fields)
        accels = cls._extract_accels(accel_fields)
        return ts, lon_semicircles, lat_semicircles, speed, accels

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
            raise IncompletePositionData(
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
    def _adjusted_accel(cls, accel):
        # The sensor will show -1g in idle. Add 1g to make 0 the baseline.
        return accel + 1000

    @classmethod
    def _semicircles_to_deg(cls, semicircles):
        return math.degrees((semicircles * math.pi) / 0x80000000)

    @classmethod
    def _check_position_continuity(cls, messages, positions):
        start_ts, end_ts = cls._check_start_end_offsets(messages, positions)
        intervals = []
        interval_start_ts = None
        for p1, p2 in it.pairwise(positions):
            interval_start_ts = interval_start_ts or p1.ts
            at_most_one_second_apart = (
                p1.ts + datetime.timedelta(seconds=1) >= p2.ts)
            if not at_most_one_second_apart:
                intervals.append((interval_start_ts, p1.ts))
                interval_start_ts = p2.ts
        if interval_start_ts:
            intervals.append((interval_start_ts, p2.ts))
        discontinuous_durations = (
            right_start - left_end
            for ((_, left_end), (right_start, _)) in it.pairwise(intervals))
        discontinuous_duration = sum(
            discontinuous_durations, start=datetime.timedelta())
        if discontinuous_duration:
            discontinuous_fraction = (
                discontinuous_duration / (end_ts - start_ts))
            logger.info(
                f'There are {len(intervals)-1} discontinuities totalling a '
                f'duration of {discontinuous_duration}. This is '
                f'{discontinuous_fraction*100:.2f}% of the total.')

    @classmethod
    def _check_start_end_offsets(cls, messages, positions):
        try:
            start_ts, end_ts = positions[0].ts, positions[-1].ts
            duration = end_ts - start_ts
            messages_start_ts = next(
                ts for ts in (
                    cls._field_value(m, 'timestamp', datetime.datetime)
                    for m in messages) if ts is not None)
            messages_end_ts = next(
                ts for ts in (
                    cls._field_value(m, 'timestamp', datetime.datetime)
                    for m in reversed(messages)) if ts is not None)
        except IndexError:
            logger.warning('No complete positions in track.')
            return None, None
        logger.info(
            f'Parsed track spanning {start_ts} - {end_ts} ({duration}).')
        start_offset = start_ts - messages_start_ts
        end_offset = messages_end_ts - end_ts
        if start_offset or end_offset:
            logger.info(
                f'Messages start {start_offset} earlier and end {end_offset} '
                'later than positions.')
        return start_ts, end_ts

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
            self, window_duration_seconds, attenuator):
        self.ensure_rolling_average_absolute_accels(
            window_duration_seconds, attenuator)
        key = (
            'rolling_average_absolute_accels', window_duration_seconds,
            attenuator)
        return [p.analysis_data[key] for p in self.positions]

    def ensure_rolling_average_absolute_accels(
            self, window_duration_seconds, attenuator):
        key = (
            'rolling_average_absolute_accels', window_duration_seconds,
            attenuator)
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
            if attenuator:
                absolute_accel = attenuator.attenuate(
                    absolute_accel, position.speed_kph)
            position.analysis_data[key] = absolute_accel

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


class MapSubplot:
    def __init__(self, figure, gridspec, conf):
        self.figure = figure
        self.gridspec = gridspec
        self.conf = conf
        self._axes = None
        self.projection = cartopy.crs.Mercator.GOOGLE
        self.color_gradient = list(
            colour.Color('green').range_to(colour.Color('red'), 101))
        cartopy.config['cache_dir'] = (
            pathlib.Path(__file__).parent.parent / 'cartopy_cache')

    def plot(self, track):
        self._axes = self.figure.add_subplot(
            self.gridspec, axes_class=self._geo_axes_class_with_projection())
        extent = self._buffered_bounds(track.bounds, 0.1)
        self._axes.set_extent(extent, crs=self.projection.as_geodetic())
        self._axes.add_image(
            cartopy.io.img_tiles.OSM(desired_tile_form='L', cache=True),
            self._zoom_level_for_extent(*extent), cmap='gray')
        self._plot_track(track)
        if self.conf.plot_spikes:
            self._plot_spikes(track)

    def _plot_track(self, track):
        track.ensure_rolling_average_absolute_accels(
            self.conf.rolling_average_window_duration_seconds,
            self.conf.attenuator)
        for slice in track.time_slices(self.conf.track_time_slice_seconds):
            line = shapely.geometry.LineString((p.lon, p.lat) for p in slice)
            att_abs_accels = [
                p.analysis_data[(
                    'rolling_average_absolute_accels',
                    self.conf.rolling_average_window_duration_seconds,
                    self.conf.attenuator)] for p in slice]
            avg_att_abs_accel = sum(att_abs_accels) / len(att_abs_accels)
            self._axes.add_geometries(
                [line], self.projection.as_geodetic(), linewidth=3,
                edgecolor=self._color_for_accel(avg_att_abs_accel),
                facecolor='none')

    def _plot_spikes(self, track):
        spikes = []
        for slice in track.time_slices(self.conf.spike_time_slice_seconds):
            max_accel = max(abs(p.accel) for p in slice)
            if max_accel >= self.conf.spike_lower_limit_millig:
                mid = slice[len(slice) // 2]
                spikes.append((mid.lon, mid.lat, max_accel))
        for x, y, accel in spikes:
            accel_over_min = accel - self.conf.spike_lower_limit_millig
            markersize = 5 + 10 * capped_fraction(
                accel_over_min, self.conf.spike_upper_limit_millig)
            self._axes.plot(
                x, y, 'o', markersize=markersize, color='purple', alpha=0.5,
                transform=self.projection.as_geodetic())

    def _geo_axes_class_with_projection(self):
        # We have to create a GeoAxes class that hardcodes our desired
        # projection because matplotlib won't let us pass a kwarg named
        # projection through to the axes class.
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
        adjusted_accel = max(
            0, abs_accel_millig - self.conf.track_lower_limit_millig)
        adjusted_upper_limit = (
            self.conf.track_upper_limit_millig
            - self.conf.track_lower_limit_millig)
        percent_to_max = int(
            capped_fraction(adjusted_accel, adjusted_upper_limit) * 100)
        return self.color_gradient[percent_to_max].hex


def analyze_files(paths, save, save_suffix, plot_separately, conf):
    figures_with_base_paths = []
    for path in paths:
        track = Track.from_path(path)
        figures_with_base_paths.extend(
            plot_track(track, path.with_suffix(''), plot_separately, conf))
    if save:
        if save_suffix:
            save_suffix = '.' + save_suffix
        save_suffix += '.png'
        for figure, base_path in figures_with_base_paths:
            file_name = base_path.name + save_suffix
            figure.savefig(base_path.parent / file_name)
    else:
        plt.show()


def plot_track(track, path, plot_separately, conf):
    def make_figure():
        figure = plt.figure(
            layout='constrained', figsize=(19.2, 10.8), dpi=100)
        figure.suptitle(f'{path}\n{conf}')
        return figure

    if plot_separately:
        dynamics_figure, map_figure = make_figure(), make_figure()
        figures = [(dynamics_figure, path.with_name(path.name + '.graphs')),
                   (map_figure, path.with_name(path.name + '.map'))]
        dynamics_specs = list(
            dynamics_figure.add_gridspec(3, 1, height_ratios=[2, 1, 2]))
        map_spec = map_figure.add_gridspec(1, 1)[0]
    else:
        figure = make_figure()
        dynamics_figure = map_figure = figure
        figures = [(figure, path)]
        gridspec = figure.add_gridspec(
            3, 2, figure=figure, height_ratios=[2, 1, 2])
        dynamics_specs = [gridspec[0, 0:1], gridspec[1, 0:1], gridspec[2, 0:1]]
        map_spec = gridspec[0:, 1]
    add_dynamics_subplots(track, dynamics_figure, dynamics_specs, conf)
    map_subplot = MapSubplot(map_figure, map_spec, conf)
    map_subplot.plot(track)
    return figures


def add_dynamics_subplots(track, figure, gridspecs, conf):
    assert len(gridspecs) == 3
    accel_axes = figure.add_subplot(gridspecs[0])
    speed_axes = figure.add_subplot(gridspecs[1], sharex=accel_axes)
    accel_analysis_axes = figure.add_subplot(gridspecs[2], sharex=accel_axes)
    accel_axes.plot(
        track.tss, track.accels, color='black', label='Raw acceleration')
    accel_axes.yaxis.set_label_text('mg')
    accel_axes.hlines([
        conf.spike_lower_limit_millig, conf.spike_upper_limit_millig,
        -conf.spike_lower_limit_millig, -conf.spike_upper_limit_millig],
                      track.tss[0], track.tss[-1], linestyles='dashed')
    accel_axes.legend()
    speed_axes.plot(track.tss, track.speeds_kph, color='black', label='Speed')
    speed_axes.yaxis.set_label_text('km/h')
    speed_axes.hlines([conf.attenuator.speed_cap], track.tss[0], track.tss[-1],
                      linestyles='dashed')
    speed_axes.legend()
    accel_analysis_axes.plot(
        track.tss,
        track.rolling_average_absolute_accels(
            conf.rolling_average_window_duration_seconds, attenuator=None),
        color='black', label='Absolute acceleration')
    accel_analysis_axes.plot(
        track.tss,
        track.rolling_average_absolute_accels(
            conf.rolling_average_window_duration_seconds, conf.attenuator),
        color='blue', label='Attenuated absolute acceleration')
    accel_analysis_axes.yaxis.set_label_text('mg')
    accel_analysis_axes.hlines([conf.track_lower_limit_millig], track.tss[0],
                               track.tss[-1], linestyles='dashed')
    accel_analysis_axes.hlines([conf.track_upper_limit_millig], track.tss[0],
                               track.tss[-1], linestyles='dashed')
    accel_analysis_axes.legend()


@dc.dataclass
class AnalysisConfig:
    track_time_slice_seconds: float
    spike_time_slice_seconds: float
    rolling_average_window_duration_seconds: float
    track_lower_limit_millig: float
    track_upper_limit_millig: float
    plot_spikes: bool
    spike_lower_limit_millig: float
    spike_upper_limit_millig: float
    attenuator: Attenuator

    def __post_init__(self):
        try:
            assert self.track_time_slice_seconds > 0
            assert self.spike_time_slice_seconds > 0
            assert self.rolling_average_window_duration_seconds > 0
            assert (
                self.track_lower_limit_millig < self.track_upper_limit_millig)
            assert (
                self.spike_lower_limit_millig < self.spike_upper_limit_millig)
        except AssertionError as e:
            raise ValueError('Invalid configuration.') from e

    def __str__(self):
        return '; '.join([
            f'time slice: {self.track_time_slice_seconds}s (track)/'
            f'{self.spike_time_slice_seconds}s (spikes)',
            'roll. avg. lookback: '
            f'{self.rolling_average_window_duration_seconds}s',
            f'track range: {self.track_lower_limit_millig}mg-'
            f'{self.track_upper_limit_millig}mg',
            f'spike range: {self.spike_lower_limit_millig}mg-'
            f'{self.spike_upper_limit_millig}mg',
            f'attenuation: {self.attenuator.spec}'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('paths', nargs='+', type=pathlib.Path)
    parser.add_argument(
        '--save', action='store_true',
        help='Save plots instead of showing them.')
    parser.add_argument(
        '--save-suffix', default='',
        help='Suffix to add to the file when saving.')
    parser.add_argument(
        '--plot-separately', action='store_true',
        help='Plot graphs and map separately.')
    parser.add_argument(
        '--track-time-slice', type=float, default=5,
        help='Duration of chunks in seconds into which the track is sliced '
        'for continuous analysis. Metrics of these chunks are averaged and '
        'drawn as one segment on the map.')
    parser.add_argument(
        '--spike-time-slice', type=float, default=1,
        help='Duration of chunks in seconds into which the track is sliced '
        'for spike analysis. Only the maximum acceleration value of each '
        'chunk decides whether a spike exists for the chunk.')
    parser.add_argument(
        '--rolling-average-window-duration', type=float, default=10,
        help='Lookback into the past in seconds when calculating a rolling '
        'average absolute acceleration for each individual position.')
    parser.add_argument(
        '--track-lower-limit', type=float, default=100,
        help='Threshold for average attenuated acceleration in millig at or '
        'below which the road quality at a position is considered excellent '
        '(i.e. will be drawn green).')
    parser.add_argument(
        '--track-upper-limit', type=float, default=300,
        help='Lowest average attenuated acceleration in millig at which a '
        'position is considered maximally bad (i.e. will be drawn red).')
    parser.add_argument(
        '--no-spikes', action='store_true', help='Disable plotting of spikes.')
    parser.add_argument(
        '--spike-lower-limit', type=float, default=3000,
        help='Lowest acceleration in millig needed for a position to be '
        'considered a spike.')
    parser.add_argument(
        '--spike-upper-limit', type=float, default=4000,
        help='Lowest acceleration in millig for a spike to be considered '
        'maximally bad (i.e. largest possible circle).')
    parser.add_argument(
        '--attenuation', type=Attenuator, default=Attenuator('linear,40,0.5'),
        help='Method of speed attenuation.')
    args = parser.parse_args()
    if {p.suffix for p in args.paths} != {'.fit'}:
        raise ValueError(
            f'One of {args.paths} doesn\'t look like a .fit file.')
    analysis_config = AnalysisConfig(
        args.track_time_slice, args.spike_time_slice,
        args.rolling_average_window_duration, args.track_lower_limit,
        args.track_upper_limit, not args.no_spikes, args.spike_lower_limit,
        args.spike_upper_limit, args.attenuation)
    analyze_files(
        args.paths, save=args.save, save_suffix=args.save_suffix,
        plot_separately=args.plot_separately, conf=analysis_config)


if __name__ == '__main__':
    setup_logging()
    logger = logging.getLogger(__name__)
    main()
