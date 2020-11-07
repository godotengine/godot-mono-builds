
import os
import os.path
import sys

from os.path import join as path_join

from options import *
from os_utils import *
import runtime


# TODO: mono cross-compilers

targets = {
    'linux': ['x86', 'x86_64'],
    'windows': ['x86', 'x86_64'],
    'osx': ['x86_64']
}

target_arch = {
    'linux': {
        'x86': 'i686',
        'x86_64': 'x86_64'
    },
    'windows': {
        'x86': 'i686',
        'x86_64': 'x86_64'
    },
    'osx': {
        'x86_64': 'x86_64'
    }
}

host_triples = {
    'linux': '%s-linux-gnu',
    'windows': '%s-w64-mingw32',
    'osx': '%s-apple-darwin',
}

llvm_table = {
    'linux': {
        'x86': 'llvm32',
        'x86_64': 'llvm64'
    },
    'windows': {
        'x86': 'llvm32',
        'x86_64': 'llvm64'
    },
    'osx': {
        'x86_64': 'llvm64'
    }
}


def is_cross_compiling(target_platform: str) -> bool:
    return (sys.platform == 'darwin' and target_platform != 'osx') or \
            (sys.platform in ['linux', 'linux2', 'cygwin'] and target_platform != 'linux')


def get_osxcross_sdk(osxcross_bin, arch):
    osxcross_sdk = os.environ.get('OSXCROSS_SDK', 18)

    name_fmt = path_join(osxcross_bin, arch + '-apple-darwin%s-%s')

    if not os.path.isfile(name_fmt % (osxcross_sdk, 'ar')):
        raise BuildError('Specify a valid osxcross SDK with the environment variable \'OSXCROSS_SDK\'')

    return osxcross_sdk


def setup_desktop_template(env: dict, opts: DesktopOpts, product: str, target_platform: str, target: str):
    host_triple = host_triples[target_platform] % target_arch[target_platform][target]

    CONFIGURE_FLAGS = [
        '--disable-boehm',
        '--disable-mcs-build',
        '--enable-maintainer-mode',
        '--with-tls=pthread',
        '--without-ikvm-native'
    ]

    if target_platform == 'windows':
        CONFIGURE_FLAGS += [
            '--with-libgdiplus=%s' % opts.mxe_prefix
        ]
    else:
        CONFIGURE_FLAGS += [
            '--disable-iconv',
            '--disable-nls',
            '--enable-dynamic-btls',
            '--with-sigaltstack=yes',
        ]

    if target_platform == 'windows':
        mxe_bin = path_join(opts.mxe_prefix, 'bin')

        env['_%s-%s_PATH' % (product, target)] = mxe_bin

        name_fmt = path_join(mxe_bin, target_arch[target_platform][target] + '-w64-mingw32-%s')

        env['_%s-%s_AR' % (product, target)] = name_fmt % 'ar'
        env['_%s-%s_AS' % (product, target)] = name_fmt % 'as'
        env['_%s-%s_CC' % (product, target)] = name_fmt % 'gcc'
        env['_%s-%s_CXX' % (product, target)] = name_fmt % 'g++'
        env['_%s-%s_DLLTOOL' % (product, target)] = name_fmt % 'dlltool'
        env['_%s-%s_LD' % (product, target)] = name_fmt % 'ld'
        env['_%s-%s_OBJDUMP' % (product, target)] = name_fmt % 'objdump'
        env['_%s-%s_RANLIB' % (product, target)] = name_fmt % 'ranlib'
        env['_%s-%s_STRIP' % (product, target)] = name_fmt % 'strip'

        CONFIGURE_FLAGS += [
            #'--enable-static-gcc-libs'
        ]
    elif target_platform == 'osx':
        if is_cross_compiling(target_platform):
            osxcross_root = os.environ['OSXCROSS_ROOT']
            osx_toolchain_path = path_join(osxcross_root, 'target')
            osxcross_bin = path_join(osx_toolchain_path, 'bin')
            osx_triple_abi = 'darwin%s' % get_osxcross_sdk(osxcross_bin, arch=target_arch[target_platform][target]) # TODO: Replace with '--osx-triple-abi' as in ios.py

            env['_%s-%s_PATH' % (product, target)] = osxcross_bin

            wrapper_path = create_osxcross_wrapper(opts, product, target, osx_toolchain_path)
            name_fmt = path_join(osxcross_bin, target_arch[target_platform][target] + '-apple-' + osx_triple_abi + '-%s')
            name_fmt = "%s %s" % (wrapper_path, name_fmt)

            env['_%s-%s_AR' % (product, target)] = name_fmt % 'ar'
            env['_%s-%s_AS' % (product, target)] = name_fmt % 'as'
            env['_%s-%s_CC' % (product, target)] = name_fmt % 'clang'
            env['_%s-%s_CXX' % (product, target)] = name_fmt % 'clang++'
            env['_%s-%s_LD' % (product, target)] = name_fmt % 'ld'
            env['_%s-%s_RANLIB' % (product, target)] = name_fmt % 'ranlib'
            env['_%s-%s_CMAKE' % (product, target)] = name_fmt % 'cmake'
            env['_%s-%s_STRIP' % (product, target)] = name_fmt % 'strip'

            # DTrace is not available when building with OSXCROSS
            CONFIGURE_FLAGS += ['--enable-dtrace=no']
        else:
            env['_%s-%s_CC' % (product, target)] = 'cc'

    env['_%s-%s_CONFIGURE_FLAGS' % (product, target)] = CONFIGURE_FLAGS

    llvm = llvm_table[target_platform][target] if opts.with_llvm else ''

    runtime.setup_runtime_template(env, opts, product, target, host_triple, llvm=llvm)


def strip_libs(opts: DesktopOpts, product: str, target_platform: str, target: str):
    if target_platform == 'osx':
        # 'strip' doesn't support '--strip-unneeded' on macOS
        return

    if is_cross_compiling(target_platform) and target_platform == 'windows':
        mxe_bin = path_join(opts.mxe_prefix, 'bin')
        name_fmt = path_join(mxe_bin, target_arch[target_platform][target] + '-w64-mingw32-%s')
        strip = name_fmt % 'strip'
    else:
        strip = 'strip'

    install_dir = path_join(opts.install_dir, '%s-%s-%s' % (product, target, opts.configuration))
    out_libs_dir = path_join(install_dir, 'lib')

    lib_files = globs(('*.a', '*.so'), dirpath=out_libs_dir)
    if len(lib_files):
        run_command(strip, args=['--strip-unneeded'] + lib_files, name='strip')

    if target_platform == 'windows':
        out_bin_dir = path_join(install_dir, 'bin')

        dll_files = globs(('*.dll',), dirpath=out_bin_dir)
        if len(dll_files):
            run_command(strip, args=['--strip-unneeded'] + dll_files, name='strip')


def configure(opts: DesktopOpts, product: str, target_platform: str, target: str):
    env = {}

    setup_desktop_template(env, opts, product, target_platform, target)

    if not os.path.isfile(path_join(opts.mono_source_root, 'configure')):
        runtime.run_autogen(opts)

    runtime.run_configure(env, opts, product, target)


def make(opts: DesktopOpts, product: str, target_platform: str, target: str):
    build_dir = path_join(opts.configure_dir, '%s-%s-%s' % (product, target, opts.configuration))

    make_args = make_default_args(opts)
    make_args += ['-C', build_dir]

    run_command('make', args=make_args, name='make')
    run_command('make', args=['-C', '%s/mono' % build_dir, 'install'], name='make install mono')
    run_command('make', args=['-C', '%s/support' % build_dir, 'install'], name='make install support')
    run_command('make', args=['-C', '%s/data' % build_dir, 'install'], name='make install data')

    if opts.strip_libs:
        strip_libs(opts, product, target_platform, target)

def copy_bcl(opts: DesktopOpts, product: str, target_platform: str, target: str):
    from distutils.dir_util import copy_tree
    from bcl import get_profile_install_dirs
    dest_dir = path_join(opts.install_dir, '%s-%s-%s' % (product, target, opts.configuration), 'lib/mono/4.5')
    for src_dir in get_profile_install_dirs(opts, 'desktop'):
        if not os.path.isdir(src_dir):
            raise BuildError('BCL source directory does not exist: %s. The BCL must be built prior to this.' % src_dir)
        copy_tree(src_dir, dest_dir)

def clean(opts: DesktopOpts, product: str, target_platform: str, target: str):
    rm_rf(
        path_join(opts.configure_dir, '%s-%s-%s' % (product, target, opts.configuration)),
        path_join(opts.configure_dir, '%s-%s-%s.config.cache' % (product, target, opts.configuration)),
        path_join(opts.install_dir, '%s-%s-%s' % (product, target, opts.configuration))
    )


def run_main(raw_args, target_platform):
    import cmd_utils
    from collections import OrderedDict
    from typing import Callable

    actions = OrderedDict()
    actions['configure'] = configure
    actions['make'] = make
    actions['copy-bcl'] = copy_bcl
    actions['clean'] = clean

    parser = cmd_utils.build_arg_parser(description='Builds the Mono runtime for the Desktop')

    default_help = 'default: %(default)s'

    parser.add_argument('action', choices=['configure', 'make', 'copy-bcl', 'clean'])
    parser.add_argument('--target', choices=targets[target_platform], action='append', required=True)
    parser.add_argument('--with-llvm', action='store_true', default=False, help=default_help)

    cmd_utils.add_runtime_arguments(parser, default_help)

    args = parser.parse_args(raw_args)

    input_action = args.action
    input_targets = args.target

    opts = desktop_opts_from_args(args)

    if not os.path.isdir(opts.mono_source_root):
        print('Mono sources directory not found: ' + opts.mono_source_root)
        sys.exit(1)

    if target_platform == 'osx' and sys.platform != 'darwin' and not 'OSXCROSS_ROOT' in os.environ:
        raise RuntimeError('The \'OSXCROSS_ROOT\' environment variable is required for cross-compiling to macOS')

    if is_cross_compiling(target_platform) and sys.platform == 'darwin':
        raise RuntimeError('Cross-compiling from macOS is not supported')

    action = actions[input_action]

    try:
        for target in input_targets:
            action(opts, 'desktop-%s' % target_platform, target_platform, target)
    except BuildError as e:
        sys.exit(e.message)
