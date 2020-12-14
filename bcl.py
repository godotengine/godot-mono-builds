#!/usr/bin/env python3

import os
import os.path
import runtime
import sys

from os.path import join as path_join
from options import *
from os_utils import *


product_values = ['desktop', 'desktop-win32', 'android', 'ios', 'wasm']
profiles_table = {
    'desktop': ['net_4_x'],
    'desktop-win32': ['net_4_x'],
    'android': ['monodroid', 'monodroid_tools'],
    'ios': ['monotouch', 'monotouch_runtime', 'monotouch_tools'],
    'wasm': ['wasm', 'wasm_tools']
}
test_profiles_table = {
    'desktop': [],
    'desktop-win32': [],
    'android': ['monodroid', 'monodroid_tools'],
    'ios': ['monotouch'],
    'wasm': ['wasm']
}

def get_install_dir(opts: BaseOpts, product: str):
    return path_join(opts.install_dir, '%s-bcl' % product)

def get_profile_dir(profile: str, product: str):
    if product == 'desktop-win32':
        return profile + '-win32'
    else:
        return profile

def get_profile_install_dirs(opts: BaseOpts, product: str):
    install_dir = get_install_dir(opts, product)
    profiles = profiles_table[product]
    return [path_join(install_dir, get_profile_dir(profile, product)) for profile in profiles]

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

    make_args = make_default_args(opts)
    make_args += ['-C', build_dir, '-C', 'mono']

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

    install_dir = get_install_dir(opts, product)

    mkdir_p(install_dir)

    make_args = make_default_args(opts)
    make_args += ['-C', build_dir, '-C', 'runtime', 'all-mcs', 'build_profiles=%s' % ' '.join(profiles)]

    if product == 'desktop-win32':
        make_args += ['PROFILE_PLATFORM=win32'] # Requires patch: 'bcl-profile-platform-override.diff'

    run_command('make', args=make_args, name='make profiles')

    if opts.tests and len(test_profiles) > 0:
        test_make_args = make_default_args(opts)
        test_make_args += ['-C', build_dir, '-C', 'runtime', 'test', 'xunit-test', 'test_profiles=%s' % ' '.join(test_profiles)]

        run_command('make', args=test_make_args, name='make tests')

    # Copy the bcl profiles to the output directory
    from distutils.dir_util import copy_tree
    for profile in profiles:
        profile_dir = get_profile_dir(profile, product)
        copy_tree('%s/mcs/class/lib/%s' % (opts.mono_source_root, profile_dir), '%s/%s' % (install_dir, profile_dir))

    # Remove unneeded files
    import glob
    file_patterns = []
    file_patterns += ['.*'] # Recursively remove hidden files we shoudln't have copied (e.g.: .stamp)
    file_patterns += ['*.dll.so', '*.exe.so'] # Remove pre-built AOT modules. We don't need them and they take a lot of space.
    file_patterns += ['*.pdb'] if opts.remove_pdb else []
    for profile in profiles:
        for file_pattern in file_patterns:
            file_pattern_recursive = '%s/**/%s' % (install_dir, file_pattern)
            [rm_rf(x) for x in glob.iglob(file_pattern_recursive, recursive=True)]

    # WebAssembly.Framework.sln
    if product == 'wasm':
        wasm_fx_output_dir = '%s/sdks/wasm/framework/netstandard2.0' % opts.mono_source_root
        wasm_fx_sln_file = '%s/sdks/wasm/framework/src/WebAssembly.Framework.sln' % opts.mono_source_root
        output_dir = path_join(install_dir, 'wasm')

        from msbuild_helper import build_solution
        build_solution(wasm_fx_sln_file, 'Release')

        import shutil
        from glob import glob

        fglob = glob(path_join(wasm_fx_output_dir, '*.dll'))

        if not opts.remove_pdb:
            fglob.extend(glob(path_join(wasm_fx_output_dir, '*.pdb')))

        for file in fglob:
            if os.path.isfile(file):
                shutil.copy(file, output_dir)

    # godot_android_ext profile (custom 'Mono.Android.dll')
    if product == 'android':
        this_script_dir = os.path.dirname(os.path.realpath(__file__))
        monodroid_profile_dir = '%s/%s' % (install_dir, 'monodroid')
        godot_profile_dir = '%s/%s' % (install_dir, 'godot_android_ext')
        refs = ['mscorlib.dll', 'System.Core.dll', 'System.dll']

        mkdir_p(godot_profile_dir)

        android_env_csc_args = [
            path_join(this_script_dir, 'files', 'godot-AndroidEnvironment.cs'),
            '-target:library', '-out:%s' % path_join(godot_profile_dir, 'Mono.Android.dll'),
            '-nostdlib', '-noconfig', '-langversion:latest'
        ]
        android_env_csc_args += ['-r:%s' % path_join(monodroid_profile_dir, r) for r in refs]

        run_command('csc', android_env_csc_args)


def clean_product(opts: BclOpts, product: str):
    clean_bcl(opts)

    install_dir = get_install_dir(opts, product)
    rm_rf(install_dir)


def main(raw_args):
    import cmd_utils
    from cmd_utils import custom_bool

    actions = {
        'make': make_product,
        'clean': clean_product
    }

    parser = cmd_utils.build_arg_parser(description='Builds the Mono BCL')

    default_help = 'default: %(default)s'

    parser.add_argument('action', choices=actions.keys())
    parser.add_argument('--product', choices=product_values, action='append', required=True)
    parser.add_argument('--tests', action='store_true', default=False, help=default_help)
    parser.add_argument('--remove-pdb', type=custom_bool, default=True, help=default_help)

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
