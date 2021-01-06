#!/usr/bin/env python3


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
        'mono-dbg-agent-clear-tls-instead-of-abort.diff',
        'bcl-profile-platform-override.diff',
        'mono_ios_asl_log_deprecated.diff',
        'wasm_m2n_trampolines_hook.diff',
    ]

    if os.path.isfile(os.path.join(mono_source_root, 'mono/tools/offsets-tool/offsets-tool.py')):
        patches += ['offsets-tool-extra-cflags_new.diff']
    else:
        patches += ['offsets-tool-extra-cflags_old.diff']

    from subprocess import Popen
    from sys import exit
    for patch in patches:
        patch_cmd = 'patch -N -p1 < %s' % os.path.join(patches_dir, patch)
        print('Running: %s' % patch_cmd)
        proc = Popen('bash -c \'%s; exit $?\'' % patch_cmd, cwd=mono_source_root, shell=True)
        exit_code = proc.wait()
        if exit_code != 0:
            exit('patch exited with error code: %s' % exit_code)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
