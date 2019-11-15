#!/usr/bin/python
#!/usr/bin/python

import os
import os.path
import runtime
import sys

from os.path import join as path_join
from options import *
from os_utils import *


product_values = ['desktop', 'android', 'wasm']
profiles_table = {
    'desktop': ['net_4_x'],
    'android': ['monodroid', 'monodroid_tools'],
    'wasm': ['wasm', 'wasm_tools']
}
test_profiles_table = {
    'desktop': [],
    'android': ['monodroid', 'monodroid_tools'],
    'wasm': ['wasm']
}


def configure_bcl(opts: BclOpts):
    stamp_file = path_join(opts.configure_dir, '.stamp-bcl-configure')

    if os.path.isfile(stamp_file):
        return

    if not os.path.isfile(path_join(opts.mono_source_root, 'configure')):
        runtime.run_autogen(opts)

    build_dir = path_join(opts.configure_dir, 'bcl')
    mkdir_p(build_dir)

    CONFIGURE_FLAGS = [
        '--disable-boehm',
        '--disable-btls-lib',
        '--disable-nls',
        '--disable-support-build',
        '--with-mcs-docs=no'
    ]

    configure = path_join(opts.mono_source_root, 'configure')
    configure_args = CONFIGURE_FLAGS

    run_command(configure, args=configure_args, cwd=build_dir, name='configure bcl')

    touch(stamp_file)


def make_bcl(opts: BclOpts):
    stamp_file = path_join(opts.configure_dir, '.stamp-bcl-make')

    if os.path.isfile(stamp_file):
        return

    build_dir = path_join(opts.configure_dir, 'bcl')

    make_args = ['-C', build_dir, '-C', 'mono']
    make_args += ['V=1'] if opts.verbose_make else []

    run_command('make', args=make_args, name='make bcl')

    touch(stamp_file)


def build_bcl(opts: BclOpts):
    configure_bcl(opts)
    make_bcl(opts)


def clean_bcl(opts: BclOpts):
    configure_stamp_file = path_join(opts.configure_dir, '.stamp-bcl-configure')
    make_stamp_file = path_join(opts.configure_dir, '.stamp-bcl-make')
    build_dir = path_join(opts.configure_dir, 'bcl')
    rm_rf(configure_stamp_file, make_stamp_file, build_dir)


def make_product(opts: BclOpts, product: str):
    build_bcl(opts)

    build_dir = path_join(opts.configure_dir, 'bcl')

    profiles = profiles_table[product]
    test_profiles = test_profiles_table[product]

    install_dir = path_join(opts.install_dir, '%s-bcl' % product)

    mkdir_p(install_dir)

    for profile in profiles:
        mkdir_p('%s/%s' % (install_dir, profile))

    make_args = ['-C', build_dir, '-C', 'runtime', 'all-mcs', 'build_profiles=%s' % ' '.join(profiles)]
    make_args += ['V=1'] if opts.verbose_make else []
    run_command('make', args=make_args, name='make profiles')

    if opts.tests and len(test_profiles) > 0:
        test_make_args = ['-C', build_dir, '-C', 'runtime', 'test', 'xunit-test', 'test_profiles=%s' % ' '.join(test_profiles)]
        test_make_args += ['V=1'] if opts.verbose_make else []
        run_command('make', args=test_make_args, name='make tests')

    # Copy the bcl profiles to the output directory
    from distutils.dir_util import copy_tree
    for profile in profiles:
        copy_tree('%s/mcs/class/lib/%s' % (opts.mono_source_root, profile), '%s/%s' % (install_dir, profile))

    # Recursively remove hidden files we shoudln't have copied (e.g.: .stamp)
    import glob
    hidden_file_pattern = '%s/**/.*' % install_dir
    for profile in profiles:
        [rm_rf(x) for x in glob.iglob(hidden_file_pattern, recursive=True)]


def clean_product(opts: BclOpts, product: str):
    clean_bcl(opts)

    install_dir = path_join(opts.install_dir, '%s-bcl' % product)
    rm_rf(install_dir)


def main(raw_args):
    import cmd_utils

    actions = {
        'make': make_product,
        'clean': clean_product
    }

    parser = cmd_utils.build_arg_parser(description='Builds the Mono BCL')

    default_help = 'default: %(default)s'

    parser.add_argument('action', choices=actions.keys())
    parser.add_argument('--product', choices=product_values, action='append', required=True)
    parser.add_argument('--tests', action='store_true', default=False, help=default_help)

    cmd_utils.add_base_arguments(parser, default_help)

    args = parser.parse_args(raw_args)

    opts = bcl_opts_from_args(args)
    products = args.product

    try:
        for product in products:
            action = actions[args.action]
            action(opts, product)
    except BuildError as e:
        sys.exit(e.message)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
