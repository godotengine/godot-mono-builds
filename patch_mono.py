#!/usr/bin/python


def main(raw_args):
    import cmd_utils
    import os
    import os.path
    from os_utils import get_emsdk_root

    parser = cmd_utils.build_arg_parser(description='Apply patches to the Mono source tree')

    default_help = 'default: %(default)s'

    mono_sources_default = os.environ.get('MONO_SOURCE_ROOT', '')

    if mono_sources_default:
        parser.add_argument('--mono-sources', default=mono_sources_default, help=default_help)
    else:
        parser.add_argument('--mono-sources', required=True)

    args = parser.parse_args(raw_args)

    this_script_dir = os.path.dirname(os.path.realpath(__file__))
    patches_dir = os.path.join(this_script_dir, 'files', 'patches')

    mono_source_root = args.mono_sources

    patches = [
        'fix-mono-android-tkill.diff',
        'mono-dbg-agent-clear-tls-instead-of-abort.diff'
    ]

    from subprocess import Popen
    for patch in patches:
        proc = Popen('bash -c \'patch -N -p1 < %s; exit 0\'' % os.path.join(patches_dir, patch), cwd=mono_source_root, shell=True)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
