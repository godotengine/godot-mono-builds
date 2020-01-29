
import os
import os.path
import sys

from os.path import join as path_join

from options import *
from os_utils import *
import runtime


# TODO: mono cross-compilers

targets = {
    'linux': ['i686', 'x86_64'],
    'windows': ['i686', 'x86_64'],
    'osx': ['x86_64']
}

host_triples = {
    'linux': '%s-linux-gnu',
    'windows': '%s-w64-mingw32',
    'osx': '%s-apple-darwin',
}

llvm_table = {
    'linux': {
        'i686': 'llvm32',
        'x86_64': 'llvm64'
    },
    'windows': {
        'i686': 'llvm32',
        'x86_64': 'llvm64'
    },
    'osx': {
        'x86_64': 'llvm64'
    }
}


def is_cross_compiling(target_platform: str) -> bool:
    return (sys.platform == 'darwin' and target_platform != 'osx') or \
            (sys.platform in ['linux', 'linux2', 'cygwin'] and target_platform != 'linux')


def get_osxcross_sdk(target, osxcross_bin):
    osxcross_sdk = os.environ.get('OSXCROSS_SDK', 14)

    name_fmt = path_join(osxcross_bin, target + '-apple-darwin%s-%s')

    if not 'OSXCROSS_SDK' in os.environ and not os.path.isfile(name_fmt % (osxcross_sdk, 'ar')):
        # Default 14 wasn't it, try 15
        osxcross_sdk = 15

    if not os.path.isfile(name_fmt % (osxcross_sdk, 'ar')):
        raise BuildError('Specify a valid osxcross SDK with the environment variable \'OSXCROSS_SDK\'')

    return osxcross_sdk


def setup_desktop_template(env: dict, opts: DesktopOpts, product: str, target_platform: str, target: str):
    host_triple = host_triples[target_platform] % target

    CONFIGURE_FLAGS = [
        '--disable-boehm',
        '--disable-iconv',
        '--disable-mcs-build',
        '--disable-nls',
        '--enable-dynamic-btls',
        '--enable-maintainer-mode',
        '--with-sigaltstack=yes',
        '--with-tls=pthread',
        '--without-ikvm-native'
    ]

    if target_platform == 'windows':
        mxe_bin = path_join(opts.mxe_prefix, 'bin')

        env['_%s-%s_PATH' % (product, target)] = mxe_bin

        name_fmt = path_join(mxe_bin, target + '-w64-mingw32-%s')

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
            '--enable-static-gcc-libs'
        ]
    elif target_platform == 'osx' and 'OSXCROSS_ROOT' in os.environ:
        osxcross_root = os.environ['OSXCROSS_ROOT']
        osxcross_bin = path_join(osxcross_root, 'target', 'bin')
        osxcross_sdk = get_osxcross_sdk(target, osxcross_bin)

        env['_%s-%s_PATH' % (product, target)] = osxcross_bin

        name_fmt = path_join(osxcross_bin, target + ('-apple-darwin%s-' % osxcross_sdk) + '%s')

        env['_%s-%s_AR' % (product, target)] = name_fmt % 'ar'
        env['_%s-%s_AS' % (product, target)] = name_fmt % 'as'
        env['_%s-%s_CC' % (product, target)] = name_fmt % 'cc'
        env['_%s-%s_CXX' % (product, target)] = name_fmt % 'c++'
        env['_%s-%s_LD' % (product, target)] = name_fmt % 'ld'
        env['_%s-%s_RANLIB' % (product, target)] = name_fmt % 'ranlib'
        env['_%s-%s_CMAKE' % (product, target)] = name_fmt % 'cmake'
        env['_%s-%s_STRIP' % (product, target)] = name_fmt % 'strip'
    else:
        env['_%s-%s_CC' % (product, target)] = 'cc'

    env['_%s-%s_CONFIGURE_FLAGS' % (product, target)] = CONFIGURE_FLAGS

    llvm = llvm_table[target_platform][target] if opts.with_llvm else ''

    runtime.setup_runtime_template(env, opts, product, target, host_triple, llvm=llvm)


def strip_libs(opts: DesktopOpts, product: str, target_platform: str, target: str):
    if is_cross_compiling(target_platform):
        if target_platform == 'windows':
            mxe_bin = path_join(opts.mxe_prefix, 'bin')
            name_fmt = path_join(mxe_bin, target + '-w64-mingw32-%s')
            strip = name_fmt % 'strip'
        elif target_platform == 'osx':
            assert 'OSXCROSS_ROOT' in os.environ
            osxcross_root = os.environ['OSXCROSS_ROOT']
            osxcross_bin = path_join(osxcross_bin, 'target', 'bin')
            osxcross_sdk = get_osxcross_sdk(target, osxcross_bin)

            name_fmt = path_join(osxcross_bin, target + ('-apple-darwin%s-' % osxcross_sdk) + '%s')
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

    make_args = ['-C', build_dir]
    make_args += ['V=1'] if opts.verbose_make else []

    run_command('make', args=make_args, name='make')
    run_command('make', args=['-C', '%s/mono' % build_dir, 'install'], name='make install mono')
    run_command('make', args=['-C', '%s/support' % build_dir, 'install'], name='make install support')
    run_command('make', args=['-C', '%s/data' % build_dir, 'install'], name='make install data')

    if opts.strip_libs:
        strip_libs(opts, product, target_platform, target)


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
    actions['clean'] = clean

    parser = cmd_utils.build_arg_parser(description='Builds the Mono runtime for the Desktop')

    default_help = 'default: %(default)s'

    parser.add_argument('action', choices=['configure', 'make', 'clean'])
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
