#!/usr/bin/env python3

import sys

from os.path import join as path_join
from options import *
from os_utils import *


def build(opts: BaseOpts):
    build_dir = '%s/mcs/class/reference-assemblies' % opts.mono_source_root
    install_dir = path_join(opts.install_dir, 'reference-assemblies')

    mkdir_p(install_dir)

    make_args = make_default_args(opts)
    make_args += ['-C', build_dir, 'build-reference-assemblies']

    run_command('make', args=make_args, name='make build-reference-assemblies')


def install(opts: BaseOpts):
    build_dir = '%s/mcs/class/reference-assemblies' % opts.mono_source_root
    install_dir = path_join(opts.install_dir, 'reference-assemblies')

    mkdir_p(install_dir)

    make_args = make_default_args(opts)
    make_args += ['-C', build_dir, 'install-local', 'DESTDIR=%s' % install_dir, 'prefix=/']

    run_command('make', args=make_args, name='make install-local')


def clean(opts: BaseOpts):
    install_dir = path_join(opts.install_dir, 'reference-assemblies')
    rm_rf(install_dir)


def main(raw_args):
    import cmd_utils

    actions = {
        'build': build,
        'install': install,
        'clean': clean
    }

    parser = cmd_utils.build_arg_parser(description='Copy the reference assemblies')

    default_help = 'default: %(default)s'

    parser.add_argument('action', choices=actions.keys())

    cmd_utils.add_base_arguments(parser, default_help)

    args = parser.parse_args(raw_args)

    opts = base_opts_from_args(args)

    try:
        action = actions[args.action]
        action(opts)
    except BuildError as e:
        sys.exit(e.message)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
