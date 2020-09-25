from argparse import ArgumentParser, ArgumentTypeError
from datetime import datetime, date, time
from statistics import mean, stdev
import pandas as pd


def hms_str2delta(value):
    """Convert argparse strings to datetime.timedelta objects

    :param str value: Raw command line input
    :return datetime.timedelta: Parsed timestamp
    :raises argparse.ArgumentTypeError: If string cannot be converted
    """
    try:
        ts = datetime.time(datetime.strptime(value, '%H:%M:%S'))
    except ValueError:
        raise ArgumentTypeError(f'{value} does not match H:M:S timestamp format')
    delta = datetime.combine(date.min, ts) - datetime.min
    return delta


def rolling_aet(csv_path, end_time, start_time, window, frequency):
    """See argparse descriptions below"""

    # Load and validate data
    df = pd.read_csv(csv_path)
    required_cols = ['activity', 'heart_rate']
    missing = [r for r in required_cols if r not in df.columns]
    if len(missing) > 0:
        raise RuntimeError(f'CSV missing required column(s) {", ".join(missing)}')

    # Add time-base index and filter range
    df.set_index(pd.TimedeltaIndex(df.activity), inplace=True)
    relevant = df[(df.index > start_time) & (df.index < end_time)]
    if len(relevant) == 0:
        raise RuntimeError(f'No data found between {start_time}-{end_time}')

    # Calculate AeT in windows and return average percent drift
    start_idx = 0
    stats = {'drift': [], 'aet': []}
    window_seconds = window * 60
    num_required_rows = window_seconds * 2
    while start_idx + num_required_rows < len(relevant):
        first_half = mean(df.heart_rate[start_idx:start_idx + window_seconds])
        second_half = mean(df.heart_rate[start_idx + window_seconds:start_idx + 2*window_seconds])
        stats['drift'].append((second_half - first_half) / first_half * 100)
        stats['aet'].append(first_half)
        start_idx += frequency
    return stats


if __name__ == '__main__':

    parser = ArgumentParser(description='Calculate AeT drift over rolling thresholds')
    parser.add_argument('csv_path', type=str, help='path to heart rate CSV timeseries')
    parser.add_argument('-e', '--end_time', type=hms_str2delta, required=True, help='timestamp to stop rolling at')
    parser.add_argument('-f', '--frequency', type=int, default=1, help='number of seconds to slide window each time')
    parser.add_argument('-s', '--start_time', type=hms_str2delta, required=True, help='timestamp to begin rolling from')
    parser.add_argument('-w', '--window', type=int, default=30, help='number of minutes for each half of the test')
    args = parser.parse_args()

    stats = rolling_aet(**vars(args))
    print(f'Results from {len(stats["drift"])} windows')
    avg_drift = mean(stats['drift'])
    print(f'Successfull test: {0 < avg_drift < 5} ({avg_drift:+.2f}% drift)')
    print(f'AeT: {mean(stats["aet"]):.2f} +/- {stdev(stats["aet"]):.2f} bpm')
