#! /usr/bin/env python3

from argparse import ArgumentParser, ArgumentTypeError, ArgumentDefaultsHelpFormatter
from datetime import datetime, date
from statistics import mean, stdev
import pandas as pd
from prettytable import PrettyTable


def hms_str2delta(value):
    """Convert argparse strings to datetime.timedelta objects

    :param str value: Raw command line input (either H:M:S or H:M)
    :return datetime.timedelta: Parsed timestamp
    :raises argparse.ArgumentTypeError: If string cannot be converted
    """

    # Auto-detect timestamp format
    num_colons = value.count(':')
    if num_colons == 2:
        fmt_str = '%H:%M:%S'
    elif num_colons == 1:
        fmt_str = '%H:%M'
    else:
        raise ArgumentTypeError(f'{value} does not match H:M:S or H:M formats')

    # Attempt to parse
    try:
        ts = datetime.time(datetime.strptime(value, fmt_str))
    except ValueError:
        raise ArgumentTypeError(f'Could not parse {value} to {fmt_str}')
    delta = datetime.combine(date.min, ts) - datetime.min
    return delta


def print_summary(combined):
    """Summarize AeT calculations in table

    Note the AeT key of each method's ``stats`` key will be the same since they
    all use the heart rate column. Therefore it doesn't matter which one is
    used for the table title

    :param [dict] combined: Matching the return format of ``Analyzer.rolling_aet()``
    :return None: Prints to console
    """

    # Table header and title
    summary = PrettyTable(field_names=['Method', 'AeT Drift (%)', 'Pace Drift (%)', 'Pace @ AeT', 'Successful'])
    aet_start = combined[0]['stats']['aet']['start']
    summary.title = f'Results from {len(aet_start):,} windows: AeT {mean(aet_start):.2f} +/- {stdev(aet_start):.2f} bpm'

    # One row per calculation method
    for method in combined:
        stats = method['stats']
        avg_aet_drift = mean(stats['aet']['drift'])
        row = [
            method['name'].title(),
            f'{avg_aet_drift:>5.2f} +/- {stdev(stats["aet"]["drift"]):.2f}']
        if method['units'] is not None:
            avg_pace_drift = mean(stats['pace']['drift'])
            pace_start = stats['pace']['start']
            row.extend([
                f'{avg_pace_drift:>5.2f} +/- {stdev(stats["pace"]["drift"]):.2f}',
                f'{mean(pace_start):.2f} +/- {stdev(pace_start):.2f} {method["units"]}'])
        else:
            avg_pace_drift = 0
            row.extend(['NA', 'NA'])
        row.append(0 < avg_aet_drift < 5 and -5 < avg_pace_drift < 5)
        summary.add_row(row)
    print(summary)


class Analyzer:

    def __init__(self, window, frequency):
        self.window = window
        self.frequency = frequency
        self.metrics = {
            'raw': {
                'name': 'raw',
                'config': {
                    'drift': 'heart_rate',
                    'pace': None},
                'units': None},
            'speed': {
                'name': 'hr/speed',
                'config': {
                    'drift': 'hr_pace',
                    'pace': 'mph'},
                'units': 'mph'},
            'elevation': {
               'name': 'hr/elevation',
               'config': {
                   'drift': 'hr_elev',
                   'pace': 'ft_hour'},
                'units': 'ft/hour'}}
        self.conversions = {
            'm/s_ft/hr': 3.28084 * 3600,
            'm/s_mph': 3600 / 1609.34}

    def extract_stats(self, relevant, drift, pace):
        """Calculate AeT related stats using different methods

        :param pd.DataFrame relevant: Subsection of the workout to analyze
        :param str drift: Column name to measure the drift of
        :param str pace: Column name to use for mean pace
        :return dict stats: Values are lists with one element for each window
        """

        def get_drift(series, first_half, second_half):
            """Calculate percent drift between halves

            :param pd.Series series: Data points to compare
            :param slice first_half: Indices for the first half of the test
            :param slice second_half: Indices for the second half of the test
            :return float drift: Percent increase from first to second half
            """
            first_avg = series[first_half].mean()
            second_avg = series[second_half].mean()
            drift = (second_avg - first_avg) / first_avg * 100
            return drift

        start_idx = 0
        stats = {
            'aet': {'start': [], 'drift': []},
            'pace': {'start': [], 'drift': []}}
        window_seconds = min(self.window * 60, int(len(relevant)/2) - 1)
        num_required_rows = window_seconds * 2
        while start_idx + num_required_rows < len(relevant):
            first_half = slice(start_idx, start_idx + window_seconds)
            second_half = slice(start_idx + window_seconds, start_idx + 2*window_seconds)
            stats['aet']['start'].append(relevant.heart_rate[first_half].mean())
            stats['aet']['drift'].append(get_drift(relevant[drift], first_half, second_half))
            if pace is not None:
                stats['pace']['start'].append(relevant[pace][first_half].mean())
                stats['pace']['drift'].append(get_drift(relevant[pace], first_half, second_half))
            start_idx += self.frequency
        return stats

    def rolling_aet(self, csv_path, start_time, end_time, max_speed=None, max_elev=None):
        """See argparse descriptions below"""

        # Load and validate data
        with open(csv_path, 'r') as f:
            columns = [c.strip() for c in f.read().splitlines()[0].split(',')]
        required_cols = ['activity', 'heart_rate', 'timestamp']
        missing = [r for r in required_cols if r not in columns]
        if len(missing) > 0:
            raise RuntimeError(f'CSV missing required column(s) {", ".join(missing)}')
        df = pd.read_csv(csv_path, parse_dates=['activity', 'timestamp'])

        # Calculate derived columns for different metrics
        metrics = [self.metrics['raw']]
        eps = 1e-32
        if 'speed' in df:
            metrics.append(self.metrics['speed'])
            df['mph'] = df.enhanced_speed * self.conversions['m/s_mph']
            df['hr_pace'] = df.apply(lambda row: row.heart_rate / (row.mph + eps), axis=1)
        if 'elevation' in df:
            metrics.append(self.metrics['elevation'])
            df['ft_hour'] = df.elevation.diff() / df.timestamp.diff().dt.total_seconds() * self.conversions['m/s_ft/hr']
            df['hr_elev'] = df.apply(lambda row: row.heart_rate / (row.ft_hour + eps), axis=1)

        # Add time-base index and filter range
        df.set_index(pd.TimedeltaIndex(df.activity), inplace=True)
        relevant = df[(df.index > start_time) & (df.index < end_time)].copy()
        if len(relevant) == 0:
            raise RuntimeError(f'No data found between {start_time}-{end_time}')
        num_relevant = len(relevant)

        # Remove any outliers by average speed (to avoid brief downhill sections skewing results)
        # Everything from this point forward works on integer indexing only, so timestamps don't need to be contiguous
        rolling_sec = 5
        if max_speed is not None:
            assert 'mph' in relevant.columns, 'mph column required to filter by max speed'
            relevant['rolling_mph'] = relevant.mph.rolling(rolling_sec).mean()
            relevant = relevant[relevant.rolling_mph < max_speed]  # FIXME setting on a copy
            print(f'Removed {num_relevant - len(relevant)} seconds > {max_speed} mph')
        if max_elev is not None:
            assert 'ft_hour' in relevant.columns, 'ft_hour column required to filter by max elevation gain rate'
            relevant['rolling_ft_hour'] = relevant.ft_hour.rolling(rolling_sec).mean()
            relevant = relevant[relevant.rolling_mph < max_elev]
            print(f'Removed {num_relevant - len(relevant)} seconds > {max_speed} ft/hr')

        # Calculate AeT for each metric in windows
        combined = []
        for m in metrics:
            config = m.pop('config')
            combined.append({'stats': self.extract_stats(relevant, **config), **m})
        return combined


if __name__ == '__main__':

    parser = ArgumentParser(
        description='Calculate AeT drift over rolling thresholds',
        formatter_class=lambda prog: ArgumentDefaultsHelpFormatter(prog, width=120, max_help_position=50))
    parser.add_argument('csv_path', type=str, help='path to heart rate CSV timeseries')
    parser.add_argument('-e', '--end_time', type=hms_str2delta, required=True, help='timestamp to stop rolling at')
    parser.add_argument('-f', '--frequency', type=int, default=1, help='number of seconds to slide window each time')
    parser.add_argument('-s', '--start_time', type=hms_str2delta, required=True, help='timestamp to begin rolling from')
    parser.add_argument('-w', '--window', type=int, default=30, help='max minutes for each half of the test')
    parser.add_argument('--max_elev', type=float, help='max rolling elevation gain (ft/hr) to exclude times from AeT')
    parser.add_argument('--max_speed', type=float, help='max rolling speed (mph) to exclude times from AeT')
    args = parser.parse_args()

    analyzer = Analyzer(args.window, args.frequency)
    stats = analyzer.rolling_aet(args.csv_path, args.start_time, args.end_time, args.max_speed, args.max_elev)
    print_summary(stats)
