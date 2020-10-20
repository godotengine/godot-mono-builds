#!/usr/bin/env python3

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
    ]

    from subprocess import Popen
    from sys import exit
    for patch in patches:
        patch_cmd = 'patch -N -p1 < %s' % patch
        print('Running: %s' % patch_cmd)
        proc = Popen('bash -c \'%s; exit $?\'' % patch_cmd, cwd=emsdk_root, shell=True)
        exit_code = proc.wait()
        if exit_code != 0:
            exit('patch exited with error code: %s' % exit_code)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
