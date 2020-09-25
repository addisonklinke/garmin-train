from argparse import ArgumentParser
from datetime import datetime, timedelta
from fitparse import FitFile
import pandas as pd
import pytz


def fit2csv(fit_path, locale, detect_gaps):
    """Based on Github package https://github.com/dtcooper/python-fitparse"""

    def utc2local(naive_utc, local):
        return pytz.utc.localize(naive_utc).astimezone(local)

    # Load FIT data
    fitfile = FitFile(fit_path)
    records = [r for r in fitfile.get_messages('record', as_dict=True)]

    # Localize FIT timestamps and determine activity offset
    tz = pytz.timezone(locale)
    start_utc = records[0]['fields'][0]['value']
    start_local = utc2local(start_utc, tz)
    csv_path = f'{datetime.strftime(start_local, "%Y%m%d")}.csv'

    # Parse into CSV
    rows = [(utc2local(r['fields'][0]['value'], tz),
             timedelta(seconds=i),
             r['fields'][-2]['value'])
            for i, r in enumerate(records)]
    df = pd.DataFrame(rows, columns=['local', 'activity', 'heart_rate'])
    df.to_csv(csv_path, index=False)

    # Check for timeseries gaps if requested
    if detect_gaps:
        deltas = df.diff().local[1:]
        gaps = deltas[deltas > timedelta(seconds=1)]
        if len(gaps) > 0:
            print(f'Found {len(gaps)} gaps in heart rate data')
        for i, g in gaps.iteritems():
            gap_start = df.local[i - 1]
            print(f'\t* {datetime.strftime(gap_start, "%I:%M:%S %p")}: {str(g.to_pytimedelta())}'.expandtabs(4))


if __name__ == '__main__':

    parser = ArgumentParser(description='Extract heart rate data from Garmin fit file')
    parser.add_argument('fit_path', type=str, help='path to .fit data')
    parser.add_argument('-g', '--gaps', action='store_true', help='print any timeseries gaps > 1s')
    parser.add_argument('-l', '--locale', type=str, default='US/Mountain', help='location of activity')
    args = parser.parse_args()

    fit2csv(args.fit_path, args.locale, args.gaps)
