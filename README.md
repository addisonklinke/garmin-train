# Garmin Train

Python utilities for handling with Garmin workout data

## Prequisites

* Python3
* Linux

## Installation

1. Clone the repository
2. Install Python requirements
3. Give scripts executable permissions
4. Symlink (to update via `git pull`) or copy (for a one-time update) the Python scripts to `/usr/local/bin`

```bash
git clone https://github.com/addisonklinke/garmin-train.git
cd garmin-train
pip install -r requirements.txt
ls commands/* | xargs -I {} sh -c 'sudo chmod +x {}; sudo ln -s $(realpath {}) /usr/local/bin;'
```

## Usage

1. Download activity data
    1. Login to your Garmin connect [account](https://connect.garmin.com)
    2. From the left-hand panel, go to Activites > All Activites
    3. Click the name of the activity you are interested in
    4. Click the gear icon in the upper left and select "Export Original".
       This will download a .zip archive containing a .fit file with your heart rate and speed data (among other fields)
    5. (Optional) From the same menu, also select "Export GPX" to add elevation data
2. Convert the Garmin files into a CSV
3. Define a time range to analyze the CSV data for aerobic threshold (AeT) calculations


Starting in the folder with your downloaded activity files

```bash
user@linux:~/Downloads$ ls
5633299714.zip  5633299714.gpx
```

Use the `activity2csv` command to perform the conversion

* If you name your activity files with a common prefix, you can use the shell expansion `*` to pass them as a list
* `-l/--locale` is the only required flag and must represent a valid `pytz.timezone` string
* `-g/--gaps` is recommended to warn you of any large gaps in the timeseries data.
  Gaps longer than 1 minute may impact the accuracy of subsequent AeT calculations
* `-n/--name` adds an extra identifier to the resulting CSV.
  Without `-n` set, the default uses yyyymmdd convention to match the date of the activity

```bash
user@linux:~/Downloads$ activity2csv -g -l US/Mountain -n myActivity 5633299714.*
```

Analyze the CSV data

* Start and end times can use seconds-level precision if desired
* By default, tests use a 1-second rolling window with 30 minute halves.
  Either of these can be adjusted with the `-f` and `-w` flags, respectively
* Read more about the theory behind the AeT drift test in The Uphill Athelte's
  [article](https://www.uphillathlete.com/heart-rate-drift/)

```bash
user@linux:~/Downloads$ rolling-aet -s HH:MM -e HH:MM yyyymmdd-myActivity.csv
+------------------------------------------------------------------------+
|            Results from 59 windows: AeT 105.22 +/- 0.08 bpm            |
+--------------+----------------+------------+---------------------------+
|    Method    |   Drift (%)    | Successful |         Pace @ AeT        |
+--------------+----------------+------------+---------------------------+
|     Raw      |  0.69 +/- 0.12 |    True    |             NA            |
|   Hr/Speed   | -3.70 +/- 0.86 |   False    |     3.94 +/- 0.02 mph     |
| Hr/Elevation | -7.00 +/- 0.29 |   False    | 1231.84 +/- 12.81 ft/hour |
+--------------+----------------+------------+---------------------------+
```
