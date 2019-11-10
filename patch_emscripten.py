#!/usr/bin/python


def main(raw_args):
    import os
    import cmd_utils
    from os_utils import get_emsdk_root

    parser = cmd_utils.build_arg_parser(description='Apply patches to the active Emscripten SDK')

    default_help = 'default: %(default)s'

    mono_sources_default = os.environ.get('MONO_SOURCE_ROOT', '')

    if mono_sources_default:
        parser.add_argument('--mono-sources', default=mono_sources_default, help=default_help)
    else:
        parser.add_argument('--mono-sources', required=True)

    args = parser.parse_args(raw_args)

    mono_source_root = args.mono_sources
    emsdk_root = get_emsdk_root()

    patches = [
        '%s/sdks/builds/fix-emscripten-8511.diff' % mono_source_root,
        '%s/sdks/builds/emscripten-pr-8457.diff' % mono_source_root
    ]

    from subprocess import Popen
    for patch in patches:
        proc = Popen('bash -c \'patch -N -p1 < %s; exit 0\'' % patch, cwd=emsdk_root, shell=True)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
