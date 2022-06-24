#!/usr/bin/env python3

import os
import os.path
import subprocess
import sys

from options import *
from os_utils import *
import runtime


DEFAULT_NDK_VERSION = '23.2.8568313'
DEFAULT_CMAKE_VERSION = '3.18.1'
targets = ['armv7', 'arm64v8', 'x86', 'x86_64']


def get_min_api_version(target) -> str:
    # Minimum API version should be in sync with Godot's platform/android/detect.py.
    # Note: The minimum API version for arm64v8 and x86_64 is '21'
    min_versions = {
        'armv7': '19',
        'arm64v8': '21',
        'x86': '19',
        'x86_64': '21',
    }
    return min_versions[target]


def check_for_android_ndk(opts: AndroidOpts):
    if not os.path.exists(os.path.join(opts.android_sdk_root, 'ndk', opts.android_ndk_version)):
        print("Attempting to install Android NDK version %s" % (opts.android_ndk_version))
        sdkmanager = opts.android_sdk_root + "/cmdline-tools/latest/bin/sdkmanager"
        if os.path.exists(sdkmanager):
            sdk_args = "ndk;" + opts.android_ndk_version
            subprocess.check_call([sdkmanager, sdk_args])
        else:
            print("ERROR: Cannot find %s. Please ensure ANDROID_SDK_ROOT is correct and cmdline-tools are installed" % (sdkmanager))
            sys.exit(1)


def check_for_cmake(opts: AndroidOpts):
    if not os.path.exists(os.path.join(opts.android_sdk_root, 'cmake', opts.android_cmake_version)):
        print("Attempting to install CMake version %s" % (opts.android_cmake_version))
        sdkmanager = opts.android_sdk_root + "/cmdline-tools/latest/bin/sdkmanager"
        if os.path.exists(sdkmanager):
            sdk_args = "cmake;" + opts.android_cmake_version
            subprocess.check_call([sdkmanager, sdk_args])
        else:
            print("ERROR: Cannot find %s. Please ensure ANDROID_SDK_ROOT is correct and cmdline-tools are installed" % (sdkmanager))
            sys.exit(1)


def get_api_version_or_min(opts: AndroidOpts, target: str) -> str:
    min_api_version = get_min_api_version(target)
    if int(opts.android_api_version) < int(min_api_version):
        print('WARNING: API version %s is less than the minimum for platform %s; using %s' % (opts.android_api_version, target, min_api_version))
        return min_api_version
    return opts.android_api_version


def setup_android_target_template(env: dict, opts: AndroidOpts, target: str):
    extra_target_envs = {
        'armv7': {
            'android-armeabi-v7a_CFLAGS': ['-D__POSIX_VISIBLE=201002', '-DSK_RELEASE', '-DNDEBUG', '-UDEBUG', '-fpic', '-march=armv7-a', '-mtune=cortex-a8', '-mfpu=vfp', '-mfloat-abi=softfp'],
            'android-armeabi-v7a_CXXFLAGS': ['-D__POSIX_VISIBLE=201002', '-DSK_RELEASE', '-DNDEBUG', '-UDEBUG', '-fpic', '-march=armv7-a', '-mtune=cortex-a8', '-mfpu=vfp', '-mfloat-abi=softfp'],
            'android-armeabi-v7a_LDFLAGS': ['-Wl,--fix-cortex-a8']
        },
        'arm64v8': {
            'android-arm64-v8a_CFLAGS': ['-D__POSIX_VISIBLE=201002', '-DSK_RELEASE', '-DNDEBUG', '-UDEBUG', '-fpic', '-DL_cuserid=9', '-DANDROID64'],
            'android-arm64-v8a_CXXFLAGS': ['-D__POSIX_VISIBLE=201002', '-DSK_RELEASE', '-DNDEBUG', '-UDEBUG', '-fpic', '-DL_cuserid=9', '-DANDROID64']
        },
        'x86': {},
        'x86_64': {
            'android-x86_64_CFLAGS': ['-DL_cuserid=9'],
            'android-x86_64_CXXFLAGS': ['-DL_cuserid=9']
        }
    }
    env.update(extra_target_envs[target])

    if target == "armv7":
        target_triple = "armv7a-linux-androideabi"
        bin_utils = "arm-linux-androideabi"
    elif target == "arm64v8":
        target_triple = "aarch64-linux-android"
        bin_utils = target_triple
    elif target == "x86":
        target_triple = "i686-linux-android"
        bin_utils = target_triple
    elif target == "x86_64":
        target_triple = "x86_64-linux-android"
        bin_utils = target_triple

    if sys.platform.startswith("linux"):
        host_subpath = "linux-x86_64"
    elif sys.platform.startswith("darwin"):
        host_subpath = "darwin-x86_64"
    elif sys.platform.startswith("win"):
        if platform.machine().endswith("64"):
            host_subpath = "windows-x86_64"
        else:
            host_subpath = "windows"

    cmake_path = os.path.join(opts.android_sdk_root, 'cmake', opts.android_cmake_version, 'bin')
    ndk_path = os.path.join(opts.android_sdk_root, 'ndk', opts.android_ndk_version)
    toolchain_path = os.path.join(ndk_path, 'toolchains/llvm/prebuilt', host_subpath)
    compiler_path = os.path.join(toolchain_path, 'bin')
    compiler_wrapper = target_triple + env['ANDROID_API_VERSION'] + '-'
    bin_utils_path = os.path.join(toolchain_path, bin_utils, 'bin')
    android_api = env['ANDROID_API_VERSION']

    AR = os.path.join(compiler_path, 'llvm-ar')
    AS = os.path.join(bin_utils_path, 'as')
    CC = os.path.join(compiler_path, compiler_wrapper + 'clang')
    CXX = os.path.join(compiler_path, compiler_wrapper + 'clang++')
    LD = os.path.join(compiler_path, 'ld')
    DLLTOOL = ''
    OBJDUMP = os.path.join(compiler_path, 'llvm-objdump')
    RANLIB = os.path.join(compiler_path, 'llvm-ranlib')
    CMAKE = os.path.join(cmake_path, 'cmake')
    STRIP = os.path.join(compiler_path, 'llvm-strip')
    CPP = CC + ' -E'
    CXXCPP = CXX + ' -E'

    ccache_path = os.environ.get('CCACHE', '')
    if ccache_path:
        CC = '%s %s' % (ccache_path, CC)
        CXX = '%s %s' % (ccache_path, CXX)
        CPP = '%s %s' % (ccache_path, CPP)
        CXXCPP = '%s %s' % (ccache_path, CXXCPP)

    AC_VARS = [
        'mono_cv_uscore=yes',
        'ac_cv_func_sched_getaffinity=no',
        'ac_cv_func_sched_setaffinity=no',
        'ac_cv_func_shm_open_working_with_mmap=no'
    ]

    CFLAGS, CXXFLAGS, CPPFLAGS, CXXCPPFLAGS, LDFLAGS = [], [], [], [], []

    # On Android we use 'getApplicationInfo().nativeLibraryDir' as the libdir where Mono will look for shared objects.
    # This path looks something like this: '/data/app-lib/{package_name-{num}}'. However, Mono does some relocation
    # and the actual path it will look at will be '/data/app-lib/{package_name}-{num}/../lib', which doesn't exist.
    # Cannot use '/data/data/{package_name}/lib' either, as '/data/data/{package_name}/lib/../lib' may result in
    # permission denied. Therefore we just override 'MONO_RELOC_LIBDIR' here to avoid the relocation.
    CPPFLAGS += ['-DMONO_RELOC_LIBDIR=\\\".\\\"']

    CFLAGS += [
        '-fstack-protector',
        '-DMONODROID=1'
        '-D__ANDROID_API__=' + android_api
    ]

    CXXFLAGS += [
        '-fstack-protector',
        '-DMONODROID=1'
        '-D__ANDROID_API__=' + android_api,
    ]

    LDFLAGS += [
        '-z', 'now', '-z', 'relro', '-z', 'noexecstack',
        '-ldl', '-lm', '-llog', '-lc'
    ]

    # Fixes this error: DllImport unable to load library 'dlopen failed: empty/missing DT_HASH in "libmono-native.so" (built with --hash-style=gnu?)'.
    LDFLAGS += ['-Wl,--hash-style=both']

    CONFIGURE_FLAGS = [
        '--disable-boehm',
        '--disable-executables',
        '--disable-iconv',
        '--disable-mcs-build',
        '--disable-nls',
        '--enable-dynamic-btls',
        '--enable-maintainer-mode',
        '--enable-minimal=ssa,portability,attach,verifier,full_messages,sgen_remset'
                ',sgen_marksweep_par,sgen_marksweep_fixed,sgen_marksweep_fixed_par'
                ',sgen_copying,logging,security,shared_handles,interpreter',
        '--with-btls-android-ndk=%s' % ndk_path,
        '--with-btls-android-api=%s' % android_api,
    ]

    CONFIGURE_FLAGS += ['--enable-monodroid']
    CONFIGURE_FLAGS += ['--with-btls-android-ndk-asm-workaround']

    CONFIGURE_FLAGS += [
        '--with-btls-android-cmake-toolchain=%s/build/cmake/android.toolchain.cmake' % ndk_path,
        '--with-sigaltstack=yes',
        '--with-tls=pthread',
        '--without-ikvm-native',
        '--disable-cooperative-suspend',
        '--disable-hybrid-suspend',
        '--disable-crash-reporting'
    ]

    env['_android-%s_AR' % target] = AR
    env['_android-%s_AS' % target] = AS
    env['_android-%s_CC' % target] = CC
    env['_android-%s_CXX' % target] = CXX
    env['_android-%s_CPP' % target] = CPP
    env['_android-%s_CXXCPP' % target] = CXXCPP
    env['_android-%s_DLLTOOL' % target] = DLLTOOL
    env['_android-%s_LD' % target] = LD
    env['_android-%s_OBJDUMP' % target] = OBJDUMP
    env['_android-%s_RANLIB' % target] = RANLIB
    env['_android-%s_CMAKE' % target] = CMAKE
    env['_android-%s_STRIP' % target] = STRIP

    env['_android-%s_AC_VARS' % target] = AC_VARS
    env['_android-%s_CFLAGS' % target] = CFLAGS
    env['_android-%s_CXXFLAGS' % target] = CXXFLAGS
    env['_android-%s_CPPFLAGS' % target] = CPPFLAGS
    env['_android-%s_CXXCPPFLAGS' % target] = CXXCPPFLAGS
    env['_android-%s_LDFLAGS' % target] = LDFLAGS
    env['_android-%s_CONFIGURE_FLAGS' % target] = CONFIGURE_FLAGS

    # Runtime template
    runtime.setup_runtime_template(env, opts, 'android', target, target_triple)


def strip_libs(opts: AndroidOpts, product: str, target: str):
    ndk_path = os.path.join(opts.android_sdk_root, 'ndk', opts.android_ndk_version)
    toolchain_path = os.path.join(ndk_path, 'toolchains/llvm/prebuilt/linux-x86_64')
    strip = os.path.join(toolchain_path, 'bin', 'llvm-strip')

    install_dir = os.path.join(opts.install_dir, '%s-%s-%s' % (product, target, opts.configuration))
    out_libs_dir = os.path.join(install_dir, 'lib')

    lib_files = globs(('*.a', '*.so'), dirpath=out_libs_dir)
    if len(lib_files):
        run_command(strip, args=['--strip-unneeded'] + lib_files, name='strip')


def configure(opts: AndroidOpts, product: str, target: str):
    env = { 'ANDROID_API_VERSION': get_api_version_or_min(opts, target) }

    setup_android_target_template(env, opts, target)

    if not os.path.isfile(os.path.join(opts.mono_source_root, 'configure')):
        runtime.run_autogen(opts)

    runtime.run_configure(env, opts, product, target)


def make(opts: AndroidOpts, product: str, target: str):
    env = { 'ANDROID_API_VERSION': get_api_version_or_min(opts, target) }

    build_dir = os.path.join(opts.configure_dir, '%s-%s-%s' % (product, target, opts.configuration))

    make_args = make_default_args(opts)
    make_args += ['-C', build_dir]

    run_command('make', args=make_args, name='make')
    run_command('make', args=['-C', '%s/mono' % build_dir, 'install'], name='make install mono')
    run_command('make', args=['-C', '%s/support' % build_dir, 'install'], name='make install support')
    run_command('make', args=['-C', '%s/data' % build_dir, 'install'], name='make install data')

    if opts.strip_libs:
        strip_libs(opts, product, target)


def clean(opts: AndroidOpts, product: str, target: str):
    rm_rf(
        os.path.join(opts.configure_dir, '%s-%s-%s' % (product, target, opts.configuration)),
        os.path.join(opts.configure_dir, '%s-%s-%s.config.cache' % (product, target, opts.configuration)),
        os.path.join(opts.install_dir, '%s-%s-%s' % (product, target, opts.configuration))
    )


def main(raw_args):
    import cmd_utils
    from cmd_utils import custom_bool
    from collections import OrderedDict
    from typing import Callable

    target_choices = targets + ['all-targets']

    actions = OrderedDict()
    actions['configure'] = configure
    actions['make'] = make
    actions['clean'] = clean

    parser = cmd_utils.build_arg_parser(
        description='Builds the Mono runtime for Android',
        env_vars={ 'ANDROID_SDK_ROOT': 'Overrides default value for --android-sdk' }
    )

    home = os.environ.get('HOME')
    android_sdk_default = os.environ.get('ANDROID_SDK_ROOT', os.path.join(home, 'Android/Sdk'))

    default_help = 'default: %(default)s'

    parser.add_argument('action', choices=['configure', 'make', 'clean'])
    parser.add_argument('--target', choices=target_choices, action='append', required=True)
    parser.add_argument('--android-sdk', default=android_sdk_default, help=default_help)
    parser.add_argument('--android-ndk-version', default=DEFAULT_NDK_VERSION, help=default_help)
    parser.add_argument('--android-api-version', default=get_min_api_version(targets[0]), help=default_help)
    parser.add_argument('--android-cmake-version', default=DEFAULT_CMAKE_VERSION, help=default_help)

    cmd_utils.add_runtime_arguments(parser, default_help)

    args = parser.parse_args(raw_args)

    input_action = args.action
    input_targets = args.target

    opts = android_opts_from_args(args)

    if not os.path.isdir(opts.mono_source_root):
        print('Mono sources directory not found: ' + opts.mono_source_root)
        sys.exit(1)

    check_for_android_ndk(opts)
    check_for_cmake(opts)

    build_targets = cmd_utils.expand_input_targets(input_targets, { 'all-targets': targets })
    action = actions[input_action]

    try:
        for target in build_targets:
            action(opts, 'android', target)
    except BuildError as e:
        sys.exit(e.message)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
