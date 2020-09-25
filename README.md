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
