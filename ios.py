#!/usr/bin/env python3

import os
import os.path
import sys

from os.path import join as path_join

from options import *
from os_utils import *
import runtime


this_script_dir = os.path.dirname(os.path.realpath(__file__))

device_targets = ['armv7', 'arm64']
sim_targets = ['i386', 'x86_64']
cross_targets = ['cross-armv7', 'cross-arm64']


def is_cross(target) -> bool:
    return target in cross_targets


class iOSTargetTable:
    archs = {
        'armv7': 'arm',
        'arm64': 'arm64',
        'i386': 'i386',
        'x86_64': 'x86_64'
    }

    host_triples = {
        'armv7': 'arm-apple-darwin11',
        'arm64': 'aarch64-apple-darwin11',
        'i386': 'i386-apple-darwin11',
        'x86_64': 'x86_64-apple-darwin11'
    }

    osxcross_tool_triples = {
        'armv7': 'arm-apple-darwin11', # TODO: ?
        'arm64': 'arm-apple-darwin11',
        'i386': 'i386-apple-darwin11', # TODO: ?
        'x86_64': 'x86_64-apple-darwin11'
    }


def setup_ios_device_template(env: dict, opts: iOSOpts, target: str):
    ios_sysroot_path = opts.ios_sdk_path

    if not ios_sysroot_path and sys.platform == 'darwin':
        # Auto-detect on macOS
        ios_sysroot_path = xcrun_find_sdk('iphoneos')

    if not ios_sysroot_path:
        raise RuntimeError('Cannot find iOS SDK; specify one manually with \'--ios-sdk\'.')

    sysroot_flags = ['-isysroot', ios_sysroot_path, '-miphoneos-version-min=%s' % opts.ios_version_min]

    arch = iOSTargetTable.archs[target]
    host_triple = iOSTargetTable.host_triples[target]
    osxcross_tool_triple = iOSTargetTable.osxcross_tool_triples[target]

    tools_path = path_join(opts.ios_toolchain_path, 'usr', 'bin')

    if sys.platform != 'darwin':
        wrapper_path = create_osxcross_wrapper(opts, 'ios', target, opts.ios_toolchain_path)
        name_fmt = path_join(tools_path, osxcross_tool_triple + '-%s')
        name_fmt = "%s %s" % (wrapper_path, name_fmt)
    else:
        name_fmt = path_join(tools_path, '%s')

    AR = name_fmt % 'ar'
    AS = name_fmt % 'as'
    CC = name_fmt % 'clang'
    CXX = name_fmt % 'clang++'
    LD = name_fmt % 'ld'
    RANLIB = name_fmt % 'ranlib'
    STRIP = name_fmt % 'strip'

    ccache_path = os.environ.get('CCACHE', '')
    if ccache_path:
        CC = '%s %s' % (ccache_path, CC)
        CXX = '%s %s' % (ccache_path, CXX)

    AC_VARS = [
        'ac_cv_c_bigendian=no',
        'ac_cv_func_fstatat=no',
        'ac_cv_func_readlinkat=no',
        'ac_cv_func_getpwuid_r=no',
        'ac_cv_func_posix_getpwuid_r=yes',
        'ac_cv_header_curses_h=no',
        'ac_cv_header_localcharset_h=no',
        'ac_cv_header_sys_user_h=no',
        'ac_cv_func_getentropy=no',
        'ac_cv_func_futimens=no',
        'ac_cv_func_utimensat=no',
        'ac_cv_func_shm_open_working_with_mmap=no',
        'ac_cv_func_pthread_jit_write_protect_np=no',
        'ac_cv_func_preadv=no',
        'ac_cv_func_pwritev=no',
        'mono_cv_sizeof_sunpath=104',
        'mono_cv_uscore=yes'
    ]

    bitcode_marker = env.get('ios-%s_BITCODE_MARKER' % target, '')

    CFLAGS = sysroot_flags + [
    	'-arch %s' % arch,
    	'-Wl,-application_extension',
    	'-fexceptions'
    ]
    CFLAGS += [bitcode_marker] if bitcode_marker else []

    CXXFLAGS = sysroot_flags + [
    	'-arch %s' % arch,
    	'-Wl,-application_extension'
    ]
    CXXFLAGS += [bitcode_marker] if bitcode_marker else []

    CPPFLAGS = sysroot_flags + [
    	'-DMONOTOUCH=1',
    	'-arch %s' % arch,
    	'-DSMALL_CONFIG', '-D_XOPEN_SOURCE', '-DHOST_IOS', '-DHAVE_LARGE_FILE_SUPPORT=1'
    ]

    LDFLAGS = [
    	'-arch %s' % arch,
    	'-framework', 'CoreFoundation',
    	'-lobjc', '-lc++'
    ]

    CONFIGURE_FLAGS = [
    	'--disable-boehm',
    	'--disable-btls',
    	'--disable-executables',
    	'--disable-icall-tables',
    	'--disable-iconv',
    	'--disable-mcs-build',
    	'--disable-nls',
    	'--disable-visibility-hidden',
    	'--enable-dtrace=no',
    	'--enable-icall-export',
    	'--enable-maintainer-mode',
    	'--enable-minimal=ssa,com,interpreter,jit,portability,assembly_remapping,attach,verifier,' +
                'full_messages,appdomains,security,sgen_remset,sgen_marksweep_par,sgen_marksweep_fixed,' +
                'sgen_marksweep_fixed_par,sgen_copying,logging,remoting,shared_perfcounters,gac',
    	'--enable-monotouch',
		# We don't need this. Comment it so we don't have to call 'mono_gc_init_finalizer_thread' from Godot.
    	#'--with-lazy-gc-thread-creation=yes',
    	'--with-tls=pthread',
    	'--without-ikvm-native',
    	'--without-sigaltstack',
    	'--disable-cooperative-suspend',
    	'--disable-hybrid-suspend',
    	'--disable-crash-reporting'
    ]

    env['_ios-%s_AR' % target] = AR
    env['_ios-%s_AS' % target] = AS
    env['_ios-%s_CC' % target] = CC
    env['_ios-%s_CXX' % target] = CXX
    env['_ios-%s_LD' % target] = LD
    env['_ios-%s_RANLIB' % target] = RANLIB
    env['_ios-%s_STRIP' % target] = STRIP

    env['_ios-%s_AC_VARS' % target] = AC_VARS
    env['_ios-%s_CFLAGS' % target] = CFLAGS
    env['_ios-%s_CXXFLAGS' % target] = CXXFLAGS
    env['_ios-%s_CPPFLAGS' % target] = CPPFLAGS
    env['_ios-%s_LDFLAGS' % target] = LDFLAGS
    env['_ios-%s_CONFIGURE_FLAGS' % target] = CONFIGURE_FLAGS

    # Runtime template
    runtime.setup_runtime_template(env, opts, 'ios', target, host_triple)


def setup_ios_simulator_template(env: dict, opts: iOSOpts, target: str):
    ios_sysroot_path = opts.ios_sdk_path

    if not ios_sysroot_path and sys.platform == 'darwin':
        # Auto-detect on macOS
        ios_sysroot_path = xcrun_find_sdk('iphonesimulator')

    if not ios_sysroot_path:
        raise RuntimeError('Cannot find iOS SDK; specify one manually with \'--ios-sdk\'.')

    sysroot_flags = ['-isysroot', ios_sysroot_path, '-miphoneos-version-min=%s' % opts.ios_version_min]

    arch = iOSTargetTable.archs[target]
    host_triple = iOSTargetTable.host_triples[target]
    osxcross_tool_triple = iOSTargetTable.osxcross_tool_triples[target]

    tools_path = path_join(opts.ios_toolchain_path, 'usr', 'bin')

    if sys.platform != 'darwin':
        wrapper_path = create_osxcross_wrapper(opts, 'ios', target, opts.ios_toolchain_path)
        name_fmt = path_join(tools_path, osxcross_tool_triple + '-%s')
        name_fmt = "%s %s" % (wrapper_path, name_fmt)
    else:
        name_fmt = path_join(tools_path, '%s')

    AR = name_fmt % 'ar'
    AS = name_fmt % 'as'
    CC = name_fmt % 'clang'
    CXX = name_fmt % 'clang++'
    LD = name_fmt % 'ld'
    RANLIB = name_fmt % 'ranlib'
    STRIP = name_fmt % 'strip'

    ccache_path = os.environ.get('CCACHE', '')
    if ccache_path:
        CC = '%s %s' % (ccache_path, CC)
        CXX = '%s %s' % (ccache_path, CXX)

    AC_VARS = [
        'ac_cv_func_clock_nanosleep=no',
        'ac_cv_func_fstatat=no',
        'ac_cv_func_readlinkat=no',
        'ac_cv_func_system=no',
        'ac_cv_func_getentropy=no',
        'ac_cv_func_futimens=no',
        'ac_cv_func_utimensat=no',
        'ac_cv_func_shm_open_working_with_mmap=no',
        'ac_cv_func_pthread_jit_write_protect_np=no',
        'ac_cv_func_preadv=no',
        'ac_cv_func_pwritev=no',
        'mono_cv_uscore=yes'
    ]

    CFLAGS = sysroot_flags + [
    	'-arch %s' % arch,
    	'-Wl,-application_extension'
    ]

    CXXFLAGS = sysroot_flags + [
    	'-arch %s' % arch,
    	'-Wl,-application_extension'
    ]

    CPPFLAGS = sysroot_flags + [
    	'-DMONOTOUCH=1',
    	'-arch %s' % arch,
        '-Wl,-application_extension',
    	'-DHOST_IOS'
    ]

    LDFLAGS = []

    CONFIGURE_FLAGS = [
        '--disable-boehm',
        '--disable-btls',
        '--disable-executables',
        '--disable-iconv',
        '--disable-mcs-build',
        '--disable-nls',
        '--disable-visibility-hidden',
        '--enable-maintainer-mode',
        '--enable-minimal=com,remoting,shared_perfcounters,gac',
        '--enable-monotouch',
        '--with-tls=pthread',
        '--without-ikvm-native',
        '--disable-cooperative-suspend',
        '--disable-hybrid-suspend',
        '--disable-crash-reporting'
    ]

    if sys.platform != 'darwin':
        # DTrace is not available when building with OSXCROSS
        CONFIGURE_FLAGS += ['--enable-dtrace=no']

    env['_ios-%s_AR' % target] = AR
    env['_ios-%s_AS' % target] = AS
    env['_ios-%s_CC' % target] = CC
    env['_ios-%s_CXX' % target] = CXX
    env['_ios-%s_LD' % target] = LD
    env['_ios-%s_RANLIB' % target] = RANLIB
    env['_ios-%s_STRIP' % target] = STRIP

    env['_ios-%s_AC_VARS' % target] = AC_VARS
    env['_ios-%s_CFLAGS' % target] = CFLAGS
    env['_ios-%s_CXXFLAGS' % target] = CXXFLAGS
    env['_ios-%s_CPPFLAGS' % target] = CPPFLAGS
    env['_ios-%s_LDFLAGS' % target] = LDFLAGS
    env['_ios-%s_CONFIGURE_FLAGS' % target] = CONFIGURE_FLAGS

    # Runtime template
    runtime.setup_runtime_template(env, opts, 'ios', target, host_triple)


class iOSCrossTable:
    target_triples = {
        'cross-armv7': 'arm-apple-darwin',
        'cross-arm64': 'aarch64-apple-darwin'
    }

    device_targets = {
        'cross-armv7': 'armv7',
        'cross-arm64': 'arm64'
    }

    # 'darwin10' is hard-coded in 'offsets-tool.py', hence why we use 'darwin10' here
    offsets_dumper_abis = {
        'cross-armv7': 'arm-apple-darwin10',
        'cross-arm64': 'aarch64-apple-darwin10'
    }


def setup_ios_cross_template(env: dict, opts: iOSOpts, target: str, host_arch: str):

    target_triple = iOSCrossTable.target_triples[target]
    device_target = iOSCrossTable.device_targets[target]
    offsets_dumper_abi = iOSCrossTable.offsets_dumper_abis[target]
    host_triple = '%s-apple-darwin11' % host_arch

    is_sim = device_target in sim_targets

    ios_sysroot_path = opts.ios_sdk_path

    if not ios_sysroot_path and sys.platform == 'darwin':
        # Auto-detect on macOS
        ios_sysroot_path = xcrun_find_sdk('iphonesimulator' if is_sim else 'iphoneos')

    if not ios_sysroot_path:
        raise RuntimeError('Cannot find iOS SDK; specify one manually with \'--ios-sdk\'.')

    osx_sysroot_path = opts.osx_sdk_path

    if not osx_sysroot_path and sys.platform == 'darwin':
        # Auto-detect on macOS
        osx_sysroot_path = xcrun_find_sdk('macosx')

    if not osx_sysroot_path:
        raise RuntimeError('Cannot find MacOSX SDK; specify one manually with \'--osx-sdk\'.')

    if sys.platform != 'darwin':
        osxcross_root = opts.osx_toolchain_path
        osxcross_bin = path_join(osxcross_root, 'bin')

        env['_ios-%s_PATH' % target] = osxcross_bin

        wrapper_path = create_osxcross_wrapper(opts, 'ios', target, opts.osx_toolchain_path)
        name_fmt = path_join(osxcross_bin, host_arch + '-apple-' + opts.osx_triple_abi + '-%s')
        name_fmt = "%s %s" % (wrapper_path, name_fmt)
    else:
        tools_path = path_join(opts.osx_toolchain_path, 'usr', 'bin')
        name_fmt = path_join(tools_path, '%s')

    env['_ios-%s_AR' % target] = name_fmt % 'ar'
    env['_ios-%s_AS' % target] = name_fmt % 'as'
    env['_ios-%s_CC' % target] = name_fmt % 'clang'
    env['_ios-%s_CXX' % target] = name_fmt % 'clang++'
    env['_ios-%s_LD' % target] = name_fmt % 'ld'
    env['_ios-%s_RANLIB' % target] = name_fmt % 'ranlib'
    env['_ios-%s_STRIP' % target] = name_fmt % 'strip'

    libclang = os.environ.get('LIBCLANG_PATH', '')
    if libclang and not os.path.isfile(libclang):
        raise RuntimeError('Specified libclang file not found: \'%s\'' % libclang)

    if not libclang:
        libclang = try_find_libclang(toolchain_path=opts.ios_toolchain_path)

    if not libclang:
        raise RuntimeError('Cannot find libclang shared library; specify a path manually with the \'LIBCLANG_PATH\' environment variable.')

    offsets_dumper_args = [
        '--libclang=%s' % libclang,
        '--sysroot=%s' % ios_sysroot_path
    ]

    if sys.platform != 'darwin':
        # Needed in order to locate the iOS toolchain's clang to use with offsets-tool
        setup_ios_device_template(env, opts, device_target)
        ios_clang = env['_ios-%s_CC' % device_target]

        # Extra CFLAGS needed in order to make offsets-tool work with OSXCross.
        offsets_dumper_args += ['--extra-cflag=' + cflag for cflag in [
            '-target', 'aarch64-apple-darwin',
            '-resource-dir', get_clang_resource_dir(ios_clang)
        ]]

    env['_ios-%s_OFFSETS_DUMPER_ARGS' % target] = offsets_dumper_args

    AC_VARS = ['ac_cv_func_shm_open_working_with_mmap=no']

    CFLAGS = ['-isysroot', osx_sysroot_path, '-mmacosx-version-min=10.9', '-Qunused-arguments']
    CXXFLAGS = ['-isysroot', osx_sysroot_path, '-mmacosx-version-min=10.9', '-Qunused-arguments', '-stdlib=libc++']
    CPPFLAGS = ['-DMONOTOUCH=1']
    LDFLAGS = ['-stdlib=libc++']

    CONFIGURE_FLAGS = [
        '--disable-boehm',
        '--disable-btls',
        '--disable-iconv',
        '--disable-libraries',
        '--disable-mcs-build',
        '--disable-nls',
        '--enable-dtrace=no',
        '--enable-icall-symbol-map',
        '--enable-minimal=com,remoting',
        '--enable-monotouch',
        '--disable-crash-reporting'
    ]

    env['_ios-%s_AC_VARS' % target] = AC_VARS
    env['_ios-%s_CFLAGS' % target] = CFLAGS
    env['_ios-%s_CXXFLAGS' % target] = CXXFLAGS
    env['_ios-%s_CPPFLAGS' % target] = CPPFLAGS
    env['_ios-%s_LDFLAGS' % target] = LDFLAGS
    env['_ios-%s_CONFIGURE_FLAGS' % target] = CONFIGURE_FLAGS

    # Runtime cross template
    runtime.setup_runtime_cross_template(env, opts, 'ios', target, host_triple, target_triple, device_target, 'llvm64', offsets_dumper_abi)


def strip_libs(opts: iOSOpts, product: str, target: str):
    # 'strip' doesn't support '--strip-unneeded' on macOS
    return


def configure(opts: iOSOpts, product: str, target: str):
    env = {}

    is_sim = target in sim_targets

    if is_cross(target):
        import llvm

        llvm.make(opts, 'llvm64')
        setup_ios_cross_template(env, opts, target, host_arch='x86_64')
    else:
        if is_sim:
            setup_ios_simulator_template(env, opts, target)
        else:
            setup_ios_device_template(env, opts, target)

    if not os.path.isfile(path_join(opts.mono_source_root, 'configure')):
        runtime.run_autogen(opts)

    runtime.run_configure(env, opts, product, target)


def make(opts: iOSOpts, product: str, target: str):
    env = {}

    build_dir = path_join(opts.configure_dir, '%s-%s-%s' % (product, target, opts.configuration))

    make_args = make_default_args(opts)
    make_args += ['-C', build_dir]

    run_command('make', args=make_args, name='make')
    run_command('make', args=['-C', '%s/mono' % build_dir, 'install'], name='make install mono')
    run_command('make', args=['-C', '%s/support' % build_dir, 'install'], name='make install support')
    run_command('make', args=['-C', '%s/data' % build_dir, 'install'], name='make install data')

    if opts.strip_libs and not is_cross(target):
        strip_libs(opts, product, target)


def clean(opts: iOSOpts, product: str, target: str):
    rm_rf(
        path_join(opts.configure_dir, '%s-%s-%s' % (product, target, opts.configuration)),
        path_join(opts.configure_dir, '%s-%s-%s.config.cache' % (product, target, opts.configuration)),
        path_join(opts.install_dir, '%s-%s-%s' % (product, target, opts.configuration))
    )


def main(raw_args):
    import cmd_utils
    from cmd_utils import custom_bool
    from collections import OrderedDict
    from typing import Callable

    target_shortcuts = {
        'all-device': device_targets,
        'all-sim': sim_targets,
        'all-cross': cross_targets
    }

    target_values = device_targets + sim_targets + cross_targets + list(target_shortcuts)

    actions = OrderedDict()
    actions['configure'] = configure
    actions['make'] = make
    actions['clean'] = clean

    parser = cmd_utils.build_arg_parser(description='Builds the Mono runtime for iOS')

    default_help = 'default: %(default)s'

    default_ios_toolchain = '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain'
    default_osx_toolchain = '/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain'
    default_ios_version_min = '10.0' # Same as Godot

    parser.add_argument('action', choices=['configure', 'make', 'clean'])
    parser.add_argument('--target', choices=target_values, action='append', required=True)
    parser.add_argument('--ios-toolchain', default=default_ios_toolchain, help=default_help)
    parser.add_argument('--ios-sdk', default='', help=default_help)
    parser.add_argument('--ios-version-min', default=default_ios_version_min, help=default_help)
    parser.add_argument('--osx-toolchain', default=default_osx_toolchain, help=default_help)
    parser.add_argument('--osx-sdk', default='', help=default_help)
    parser.add_argument('--osx-triple-abi', default='darwin18', help=default_help)

    cmd_utils.add_runtime_arguments(parser, default_help)

    args = parser.parse_args(raw_args)

    input_action = args.action
    input_targets = args.target

    opts = ios_opts_from_args(args)

    targets = cmd_utils.expand_input_targets(input_targets, target_shortcuts)

    if not os.path.isdir(opts.mono_source_root):
        print('Mono sources directory not found: ' + opts.mono_source_root)
        sys.exit(1)

    action = actions[input_action]

    try:
        for target in targets:
            action(opts, 'ios', target)
    except BuildError as e:
        sys.exit(e.message)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
