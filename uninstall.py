from argparse import ArgumentParser
from glob import glob
import os


if __name__ == '__main__':

    parser = ArgumentParser(description='Remove command scripts from /usr/local/bin')
    parser.add_argument('-p', '--install_path', type=str, default='/usr/local/bin', help='location for install')
    args = parser.parse_args()

    commands = [os.path.realpath(g) for g in glob('commands/*.py') if '__' not in g]
    for c in commands:
        command_name = os.path.basename(c).split('.')[0]
        bin_path = os.path.join(args.install_path, command_name)
        if os.path.exists(bin_path):
            if os.path.islink(bin_path):
                os.unlink(bin_path)
            elif os.path.isfile(bin_path):
                os.remove(bin_path)
            else:
                raise TypeError(f'Binary path {bin_path} is neither symlink nor file')
    print(f'Successfully uninstalled {len(commands)} commands \nRun `ls -l {args.install_path}` to confirm')
