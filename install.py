from argparse import ArgumentParser, ArgumentDefaultsHelpFormatter
from glob import glob
import os
import shutil


if __name__ == '__main__':

    parser = ArgumentParser(
        description='Setup command scripts on local $PATH',
        formatter_class=lambda prog: ArgumentDefaultsHelpFormatter(prog, width=120, max_help_position=50))
    parser.add_argument('-o', '--overwrite', action='store_true', help='replace any existing installed command(s)')
    parser.add_argument('-m', '--method', type=str, choices=['symlink', 'copy'], default='symlink', help='setup method')
    parser.add_argument('-p', '--install_path', type=str, default='/usr/local/bin', help='location for install')
    args = parser.parse_args()

    # Process each available command
    commands = [os.path.realpath(g) for g in glob('commands/*.py') if '__' not in g]
    func = os.symlink if args.method == 'symlink' else shutil.copy
    exist_count = 0
    for src in commands:
        command_name = os.path.basename(src).split('.')[0]
        dest = os.path.join(args.install_path, command_name)
        if os.path.exists(dest):
            if args.overwrite:
                os.remove(dest)
            else:
                exist_count += 1
                continue
        func(src, dest)

    # Summarize status
    if exist_count > 0:
        print(f'{exist_count}/{len(commands)} commands already exist in {args.install_path}'
              f'\nRemove with uninstall.py or re-run with -o/--overwrite')
    else:
        print(f'Successfully installed {len(commands)} commands')
        print('Run `ls -l /usr/local/bin/` to confirm')
