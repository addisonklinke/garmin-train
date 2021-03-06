#! /usr/bin/env python3

from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from collections import OrderedDict
from datetime import datetime, timedelta
from functools import reduce
from io import BytesIO
import os
from zipfile import ZipFile
from fitparse import FitFile
import pandas as pd
import pytz
import xmltodict


def utc2local(naive_utc, local):
    """Adjust UTC timestamp to local

    :param datetime.datetime naive_utc: Starting point for conversion
    :param pytz.timezone local: To convert to
    :return datetime.datetime:
    """
    return pytz.utc.localize(naive_utc).astimezone(local)


class Converter:

    def __init__(self, locale, detect_gaps=False):
        """Initialize workout file converter

        :param str locale: Timezone label accepted by ``pytz``
        :param bool detect_gaps: Whether to print a summary of gaps in timeseries
        """
        self.tz = pytz.timezone(locale)
        self.detect_gaps = detect_gaps

    def __call__(self, activity_files):
        """Pass files to appropriate converter and merge results

        Gaps only need to be printed once for the combined data since they
        will be the same for all versions of the activity. To support a new
        file format, create a ``*2csv()`` method that accepts a singular
        filepath as its argument
        """

        # Convert individual formats
        parsed = []
        for i, path in enumerate(activity_files):
            filename = os.path.basename(path)
            file_type = filename.split('.')[-1]
            func = getattr(self, file_type + '2csv', None)
            msg = f'Processing {i + 1}/{len(activity_files)}: '
            if func is not None:
                msg += filename
                parsed.append(func(path))
            else:
                msg += f'No conversion for file type .{file_type}'
            print(msg)

        # Merge by timestamp and check gaps
        combined = reduce(lambda x, y: pd.merge(x, y, on='timestamp'), parsed)
        if self.detect_gaps:
            deltas = combined.timestamp.diff()[1:]
            gaps = deltas[deltas > timedelta(seconds=1)]
            if len(gaps) > 0:
                print(f'Found {len(gaps)} gaps in timeseries data')
            for i, g in gaps.iteritems():
                gap_start = datetime.strftime(combined.timestamp[i - 1], "%I:%M:%S %p")
                print(f'\t* {gap_start}: {str(g.to_pytimedelta())}'.expandtabs(4))
        return combined

    def fit2csv(self, fit_path):
        """Convert FIT fields to CSV format

        Based on Github package https://github.com/dtcooper/python-fitparse

        Extracts whatever fields are provided in each FIT record item. The units
        for some of these are not particularly intuitive, and in some cases are
        provided in each field's ``'units'`` key. A summary is included below
            * timestamp: UTC datetime.datetime
            * position_lat: int
            * position_long: int
            * distance: meters
            * speed: int (1000 * enhanced_speed)
            * enhanced_speed: float (m/s)
            * heart_rate: beats per minute (BPM)
            * cadence: revolutions per minute (RPM)

        :param str or BytesIO fit_path: Full path to .fit file on disk
        :return pd.DataFrame: In tabular CSV format
        """

        # Load FIT data
        fitfile = FitFile(fit_path)
        records = [r for r in fitfile.get_messages('record', as_dict=True)]
        fields_stoi = OrderedDict({f['name']: i for i, f in enumerate(records[0]['fields'])})
        if 'timestamp' not in fields_stoi:
            raise RuntimeError(f'Records do not contain timestamps')

        # Convert FIT timestamps from UTC to user's locale
        for r in records:
            local_ts = r['fields'][fields_stoi['timestamp']]['value']
            r['fields'][fields_stoi['timestamp']]['value'] = utc2local(local_ts, self.tz)

        # Extract all field values for each record to CSV and add an activity time counter
        rows = [[timedelta(seconds=s)] + [r['fields'][idx]['value'] for idx in fields_stoi.values()]
                for s, r in enumerate(records)]
        return pd.DataFrame(rows, columns=['activity'] + list(fields_stoi.keys()))

    def gpx2csv(self, gpx_path):
        """Convert GPX elevation data to CSV format

        :param str gpx_path: Full path to .gpx file on disk
        :return pd.Dataframe: With elevation in meters
        """

        # Extract points timeseries
        with open(gpx_path, 'r') as f:
            raw = xmltodict.parse(f.read(), xml_attribs=False)
        try:
            points = raw['gpx']['trk']['trkseg']['trkpt']
        except KeyError as e:
            raise RuntimeError('GPX structure missing required keys: gpx, trk, trkseg, and trkpt') from e

        # Form rows of local timestamps and elevation
        rows = [{'timestamp': utc2local(datetime.strptime(p['time'].split('.')[0], '%Y-%m-%dT%H:%M:%S'), self.tz),
                 'elevation': float(p['ele'])}
                for p in points]
        return pd.DataFrame(rows)

    def zip2csv(self, zip_path):
        """Automate extration of .fit file

        The initializer for ``fitparse.FitFile`` can accept either a filepath
        or a ``BytesIO`` object, so we can pass the content of the zip archive
        directly and it will be handled by ``fitparse.utils.fileish_open``
        """
        with ZipFile(zip_path, 'r') as f:
            all_files = f.namelist()
            fit_file = next((file for file in all_files if file.endswith('.fit')), None)
            if fit_file is None:
                raise RuntimeError('zip archive does not contain a .fit file')
            fileish = BytesIO(f.read(fit_file))
        return self.fit2csv(fileish)


if __name__ == '__main__':

    parser = ArgumentParser(
        description='Extract activity data from Garmin workout files',
        formatter_class=lambda prog: ArgumentDefaultsHelpFormatter(prog, width=120, max_help_position=50))
    parser.add_argument('activity_files', type=str, nargs='+', help='currently supports .fit/.zip and .gpx')
    parser.add_argument('-g', '--detect_gaps', action='store_true', help='print any timeseries gaps > 1s')
    parser.add_argument('-l', '--locale', type=str, required=True, help='location of activity, i.e. US/Pacific')
    parser.add_argument('-n', '--name', type=str, help='activity name to append to yyyymmdd CSV format')
    args = parser.parse_args()

    # Combine data from the provided activity files
    converter = Converter(args.locale, args.detect_gaps)
    df = converter(args.activity_files)

    # Use the starting date (and optional name) to identity the CSV export
    start_local = df['timestamp'][0]
    filename = datetime.strftime(start_local, "%Y%m%d")
    if args.name is not None:
        filename += '-' + args.name
    filename += '.csv'

    # Write to disk
    df.to_csv(filename, index=False)
    print(f'CSV saved to {filename}')
