import collections
import dataclasses as dc
import datetime
import functools as ft
import itertools as it
import logging
import math
import re

import fitparse


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


class Track:
    EXPECTED_ACCEL_VALUES_PER_MESSAGE = 25
    logger = logging.getLogger('Track')

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
            cls.logger.info(
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
            cls.logger.warning('No complete positions in track.')
            return None, None
        cls.logger.info(
            f'Parsed track spanning {start_ts} - {end_ts} ({duration}).')
        start_offset = start_ts - messages_start_ts
        end_offset = messages_end_ts - end_ts
        if start_offset or end_offset:
            cls.logger.info(
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
