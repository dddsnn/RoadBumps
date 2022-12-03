import dataclasses as dc
import datetime
import itertools as it
import logging
import math
import re
import sys

import fitparse
import matplotlib.pyplot as plt

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


class Track:
    EXPECTED_ACCEL_VALUES_PER_MESSAGE = 25

    def __init__(self, positions):
        self.positions = positions

    @classmethod
    def from_path(cls, file_path):
        with open(file_path, 'rb') as file:
            fit_file = fitparse.FitFile(file)
            fit_file.parse()
        positions = []
        for message in fit_file.messages:
            ts = cls._field_value(message, 'timestamp', datetime.datetime)
            lon = cls._field_value(message, 'position_long')
            lat = cls._field_value(message, 'position_lat')
            speed = cls._field_value(message, 'enhanced_speed')
            accel_fields = sorted((
                field for field in message.fields
                if field.name.startswith('accel')),
                                  key=cls._accel_field_bounds)
            accel_fields = accel_fields or None
            if not all(v is not None
                       for v in [ts, lon, lat, speed, accel_fields]):
                if any(v is not None for v in [lon, lat, speed, accel_fields]):
                    logger.warning(
                        'Not all expected values were present, but some were '
                        f'({values}).')
                continue
            cls._assert_valid_accel_fields(accel_fields)
            accels = cls._extract_accels(accel_fields)
            for accel in cls._adjusted_accels(accels):
                positions.append(Position(ts, lon, lat, speed, accel))
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
    def _check_consecutive_positions(cls, positions):
        for p1, p2 in it.pairwise(positions):
            same_ts = p1.ts == p2.ts
            one_second_apart = p1.ts + datetime.timedelta(seconds=1) == p2.ts
            if not same_ts and not one_second_apart:
                logger.warning(
                    'Position timestamps don\'t have equal or consecutive '
                    f'timestamps: {p1.ts} - {p2.ts}.')


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
    tss = [p.ts for p in track.positions]
    accels = [p.accel for p in track.positions]
    speeds_kph = [mps_to_kph(p.speed) for p in track.positions]
    fig = plt.figure()
    axess = fig.subplots(2, 1, sharex=True, height_ratios=[3, 1])
    axess[0].plot(tss, accels, color='blue')
    axess[0].yaxis.set_label_text('mg')
    axess[1].plot(tss, speeds_kph, color='red')
    axess[1].yaxis.set_label_text('km/h')
    plt.show()


def mps_to_kph(mps):
    return mps * 3.6


if __name__ == '__main__':
    setup_logging()
    logger = logging.getLogger(__name__)
    main()
