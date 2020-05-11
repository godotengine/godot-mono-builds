#!/usr/bin/python

import os
import os.path
import sys

from os.path import join as path_join

from options import *
from os_utils import *
import runtime


runtime_targets = ['armeabi-v7a', 'arm64-v8a', 'x86', 'x86_64']
cross_targets = ['cross-arm', 'cross-arm64', 'cross-x86', 'cross-x86_64']
cross_mxe_targets = ['cross-arm-win', 'cross-arm64-win', 'cross-x86-win', 'cross-x86_64-win']


def is_cross(target) -> bool:
    return target in cross_targets or is_cross_mxe(target)


def is_cross_mxe(target) -> bool:
    return target in cross_mxe_targets


def android_autodetect_cmake(opts: AndroidOpts) -> str:
    from distutils.version import LooseVersion
    from os import listdir

    sdk_cmake_basedir = path_join(opts.android_sdk_root, 'cmake')
    versions = []

    for entry in listdir(sdk_cmake_basedir):
        if os.path.isdir(path_join(sdk_cmake_basedir, entry)):
            try:
                version = LooseVersion(entry)
                versions += [version]
            except ValueError:
                continue # Not a version folder

    if len(versions) == 0:
        raise BuildError('Cannot auto-detect Android CMake version')

    lattest_version = str(sorted(versions)[-1])
    print('Auto-detected Android CMake version: ' + lattest_version)

    return lattest_version


def get_api_version_or_min(opts: AndroidOpts, target: str) -> str:
    min_versions = { 'arm64-v8a': '21', 'x86_64': '21' }
    if target in min_versions and int(opts.android_api_version) < int(min_versions[target]):
        print('WARNING: %s is less than minimum platform for %s; using %s' % (opts.android_api_version, target, min_versions[target]))
        return min_versions[target]
    return opts.android_api_version


def get_android_cmake_version(opts: AndroidOpts) -> str:
    return opts.android_cmake_version if opts.android_cmake_version != 'autodetect' else android_autodetect_cmake(opts)


class AndroidTargetTable:
    archs = {
        'armeabi-v7a': 'arm',
        'arm64-v8a': 'arm64',
        'x86': 'x86',
        'x86_64': 'x86_64'
    }

    abi_names = {
        'armeabi-v7a': 'arm-linux-androideabi',
        'arm64-v8a': 'aarch64-linux-android',
        'x86': 'i686-linux-android',
        'x86_64': 'x86_64-linux-android'
    }

    host_triples = {
        'armeabi-v7a': 'armv5-linux-androideabi',
        'arm64-v8a': 'aarch64-linux-android',
        'x86': 'i686-linux-android',
        'x86_64': 'x86_64-linux-android'
    }


def setup_android_target_template(env: dict, opts: AndroidOpts, target: str):
    extra_target_envs = {
        'armeabi-v7a': {
            'android-armeabi-v7a_CFLAGS': ['-D__POSIX_VISIBLE=201002', '-DSK_RELEASE', '-DNDEBUG', '-UDEBUG', '-fpic', '-march=armv7-a', '-mtune=cortex-a8', '-mfpu=vfp', '-mfloat-abi=softfp'],
            'android-armeabi-v7a_CXXFLAGS': ['-D__POSIX_VISIBLE=201002', '-DSK_RELEASE', '-DNDEBUG', '-UDEBUG', '-fpic', '-march=armv7-a', '-mtune=cortex-a8', '-mfpu=vfp', '-mfloat-abi=softfp'],
            'android-armeabi-v7a_LDFLAGS': ['-Wl,--fix-cortex-a8']
        },
        'arm64-v8a': {
            'android-arm64-v8a_CFLAGS': ['-D__POSIX_VISIBLE=201002', '-DSK_RELEASE', '-DNDEBUG', '-UDEBUG', '-fpic', '-DL_cuserid=9', '-DANDROID64'],
            'android-arm64-v8a_CXXFLAGS': ['-D__POSIX_VISIBLE=201002', '-DSK_RELEASE', '-DNDEBUG', '-UDEBUG', '-fpic', '-DL_cuserid=9', '-DANDROID64']
        },
        'x86': {},
        'x86_64': {
            'android-x86_64_CFLAGS': ['-DL_cuserid=9'],
            'android-x86_64_CXXFLAGS': ['-DL_cuserid=9']
        }
    }

    if target in extra_target_envs:
        env.update(extra_target_envs[target])

    android_new_ndk = True

    with open(path_join(opts.android_ndk_root, 'source.properties')) as file:
        for line in file:
            line = line.strip()
            if line.startswith('Pkg.Revision ') or line.startswith('Pkg.Revision='):
                pkg_revision = line.split('=')[1].strip()
                mayor = int(pkg_revision.split('.')[0])
                android_new_ndk = mayor >= 18
                break

    arch = AndroidTargetTable.archs[target]
    abi_name = AndroidTargetTable.abi_names[target]
    host_triple = AndroidTargetTable.host_triples[target]
    api = env['ANDROID_API_VERSION']

    toolchain_path = path_join(opts.android_toolchains_prefix, opts.toolchain_name_fmt % (target, api))

    tools_path = path_join(toolchain_path, 'bin')
    name_fmt = abi_name + '-%s'

    sdk_cmake_dir = path_join(opts.android_sdk_root, 'cmake', get_android_cmake_version(opts))
    if not os.path.isdir(sdk_cmake_dir):
        print('Android CMake directory \'%s\' not found' % sdk_cmake_dir)

    AR = path_join(tools_path, name_fmt % 'ar')
    AS = path_join(tools_path, name_fmt % 'as')
    CC = path_join(tools_path, name_fmt % 'clang')
    CXX = path_join(tools_path, name_fmt % 'clang++')
    DLLTOOL = ''
    LD = path_join(tools_path, name_fmt % 'ld')
    OBJDUMP = path_join(tools_path, name_fmt % 'objdump')
    RANLIB = path_join(tools_path, name_fmt % 'ranlib')
    CMAKE = path_join(sdk_cmake_dir, 'bin', 'cmake')
    STRIP = path_join(tools_path, name_fmt % 'strip')

    CPP = path_join(tools_path, name_fmt % 'cpp')
    if not os.path.isfile(CPP):
        CPP = path_join(tools_path, (name_fmt % 'clang'))
        CPP += ' -E'

    CXXCPP = path_join(tools_path, name_fmt % 'cpp')
    if not os.path.isfile(CXXCPP):
        CXXCPP = path_join(tools_path, (name_fmt % 'clang++'))
        CXXCPP += ' -E'

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
    ]
    CFLAGS += ['-D__ANDROID_API__=' + api] if android_new_ndk else []

    CXXFLAGS += [
        '-fstack-protector',
        '-DMONODROID=1'
    ]
    CXXFLAGS += ['-D__ANDROID_API__=' + api] if android_new_ndk else []

    CPPFLAGS += ['-I%s/sysroot/usr/include' % toolchain_path]
    CXXCPPFLAGS += ['-I%s/sysroot/usr/include' % toolchain_path]

    path_link = '%s/platforms/android-%s/arch-%s/usr/lib' % (opts.android_ndk_root, api, arch)

    LDFLAGS += [
        '-z', 'now', '-z', 'relro', '-z', 'noexecstack',
        '-ldl', '-lm', '-llog', '-lc', '-lgcc',
        '-Wl,-rpath-link=%s,-dynamic-linker=/system/bin/linker' % path_link,
        '-L' + path_link
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
        '--with-btls-android-ndk=%s' % opts.android_ndk_root,
        '--with-btls-android-api=%s' % api,
    ]

    CONFIGURE_FLAGS += ['--enable-monodroid']
    CONFIGURE_FLAGS += ['--with-btls-android-ndk-asm-workaround'] if android_new_ndk else []

    CONFIGURE_FLAGS += [
        '--with-btls-android-cmake-toolchain=%s/build/cmake/android.toolchain.cmake' % opts.android_ndk_root,
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
    runtime.setup_runtime_template(env, opts, 'android', target, host_triple)


class AndroidCrossTable:
    target_archs = {
        'cross-arm': 'armv7',
        'cross-arm64': 'aarch64-v8a',
        'cross-x86': 'i686',
        'cross-x86_64': 'x86_64'
    }

    device_targets = {
        'cross-arm': 'armeabi-v7a',
        'cross-arm64': 'arm64-v8a',
        'cross-x86': 'x86',
        'cross-x86_64': 'x86_64'
    }

    offsets_dumper_abis = {
        'cross-arm': 'armv7-none-linux-androideabi',
        'cross-arm64': 'aarch64-v8a-linux-android',
        'cross-x86': 'i686-none-linux-android',
        'cross-x86_64': 'x86_64-none-linux-android'
    }


def get_android_libclang_path(opts):
    if sys.platform == 'darwin':
        return '%s/toolchains/llvm/prebuilt/darwin-x86_64/lib64/libclang.dylib' % opts.android_ndk_root
    elif sys.platform in ['linux', 'linux2']:
        loc = '%s/toolchains/llvm/prebuilt/linux-x86_64/lib64/libclang.so.9svn' % opts.android_ndk_root
        if os.path.isfile(loc):
            return loc
        return '%s/toolchains/llvm/prebuilt/linux-x86_64/lib64/libclang.so.8svn' % opts.android_ndk_root
    assert False


def setup_android_cross_template(env: dict, opts: AndroidOpts, target: str, host_arch: str):
    def get_host_triple():
        if sys.platform == 'darwin':
            return '%s-apple-darwin11' % host_arch
        elif sys.platform in ['linux', 'linux2']:
            return '%s-linux-gnu' % host_arch
        assert False

    target_arch = AndroidCrossTable.target_archs[target]
    device_target = AndroidCrossTable.device_targets[target]
    offsets_dumper_abi = AndroidCrossTable.offsets_dumper_abis[target]
    host_triple = get_host_triple()
    target_triple = '%s-linux-android' % target_arch

    android_libclang = get_android_libclang_path(opts)

    env['_android-%s_OFFSETS_DUMPER_ARGS' % target] = [
        '--libclang=%s' % android_libclang,
        '--sysroot=%s/sysroot' % opts.android_ndk_root
    ]

    env['_android-%s_AR' % target] = 'ar'
    env['_android-%s_AS' % target] = 'as'
    env['_android-%s_CC' % target] = 'cc'
    env['_android-%s_CXX' % target] = 'c++'
    env['_android-%s_CXXCPP' % target] = 'cpp'
    env['_android-%s_LD' % target] = 'ld'
    env['_android-%s_RANLIB' % target] = 'ranlib'
    env['_android-%s_STRIP' % target] = 'strip'

    is_darwin = sys.platform == 'darwin'

    CFLAGS = []
    CFLAGS += ['-DDEBUG_CROSS'] if not opts.release else []
    CFLAGS += ['-mmacosx-version-min=10.9'] if is_darwin else []

    env['_android-%s_CFLAGS' % target] = CFLAGS

    CXXFLAGS = []
    CXXFLAGS += ['-DDEBUG_CROSS'] if not opts.release else []
    CXXFLAGS += ['-mmacosx-version-min=10.9', '-stdlib=libc++'] if is_darwin else []

    env['_android-%s_CXXFLAGS' % target] = CXXFLAGS

    env['_android-%s_CONFIGURE_FLAGS' % target] = [
        '--disable-boehm',
        '--disable-mcs-build',
        '--disable-nls',
        '--enable-maintainer-mode',
        '--with-tls=pthread'
    ]

    # Runtime cross template
    runtime.setup_runtime_cross_template(env, opts, 'android', target, host_triple, target_triple, device_target, 'llvm64', offsets_dumper_abi)


def setup_android_cross_mxe_template(env: dict, opts: AndroidOpts, target: str, host_arch: str):
    table_target = cross_targets[cross_mxe_targets.index(target)] # Re-use the non-mxe table

    target_arch = AndroidCrossTable.target_archs[table_target]
    device_target = AndroidCrossTable.device_targets[table_target]
    offsets_dumper_abi = AndroidCrossTable.offsets_dumper_abis[table_target]
    host_triple = '%s-w64-mingw32' % host_arch
    target_triple = '%s-linux-android' % target_arch

    android_libclang = get_android_libclang_path(opts)

    env['_android-%s_OFFSETS_DUMPER_ARGS' % target] = [
        '--libclang=%s' % android_libclang,
        '--sysroot=%s/sysroot' % opts.android_ndk_root
    ]

    mxe_bin = path_join(opts.mxe_prefix, 'bin')

    env['_android-%s_PATH' % target] = mxe_bin

    name_fmt = host_arch + '-w64-mingw32-%s'

    env['_android-%s_AR' % target] = path_join(mxe_bin, name_fmt % 'ar')
    env['_android-%s_AS' % target] = path_join(mxe_bin, name_fmt % 'as')
    env['_android-%s_CC' % target] = path_join(mxe_bin, name_fmt % 'gcc')
    env['_android-%s_CXX' % target] = path_join(mxe_bin, name_fmt % 'g++')
    env['_android-%s_DLLTOOL' % target] = path_join(mxe_bin, name_fmt % 'dlltool')
    env['_android-%s_LD' % target] = path_join(mxe_bin, name_fmt % 'ld')
    env['_android-%s_OBJDUMP' % target] = path_join(mxe_bin, name_fmt % 'objdump')
    env['_android-%s_RANLIB' % target] = path_join(mxe_bin, name_fmt % 'ranlib')
    env['_android-%s_STRIP' % target] = path_join(mxe_bin, name_fmt % 'strip')

    mingw_zlib_prefix = '%s/opt/mingw-zlib/usr' % opts.mxe_prefix
    if not os.path.isdir(mingw_zlib_prefix):
        mingw_zlib_prefix = opts.mxe_prefix

    CFLAGS = []
    CFLAGS += ['-DDEBUG_CROSS'] if not opts.release else []
    CFLAGS += ['-I%s/%s-w64-mingw32/include' % (mingw_zlib_prefix, host_arch)]

    env['_android-%s_CFLAGS' % target] = CFLAGS

    CXXFLAGS = []
    CXXFLAGS += ['-DDEBUG_CROSS'] if not opts.release else []
    CXXFLAGS += ['-I%s/%s-w64-mingw32/include' % (mingw_zlib_prefix, host_arch)]

    env['_android-%s_CXXFLAGS' % target] = CXXFLAGS

    env['_android-%s_LDFLAGS' % target] = []

    CONFIGURE_FLAGS = [
        '--disable-boehm',
        '--disable-mcs-build',
        '--disable-nls',
        '--enable-static-gcc-libs',
        '--enable-maintainer-mode',
        '--with-tls=pthread'
    ]

    CONFIGURE_FLAGS += ['--with-static-zlib=%s/%s-w64-mingw32/lib/libz.a' % (mingw_zlib_prefix, host_arch)]

    env['_android-%s_CONFIGURE_FLAGS' % target] = CONFIGURE_FLAGS

    # Runtime cross template
    runtime.setup_runtime_cross_template(env, opts, 'android', target, host_triple, target_triple, device_target, 'llvmwin64', offsets_dumper_abi)


def make_standalone_toolchain(opts: AndroidOpts, target: str, api: str):
    install_dir = path_join(opts.android_toolchains_prefix, opts.toolchain_name_fmt % (target, api))
    if os.path.isdir(path_join(install_dir, 'bin')):
        return # Looks like it's already there, so no need to re-create it
    command = path_join(opts.android_ndk_root, 'build', 'tools', 'make_standalone_toolchain.py')
    args = ['--verbose', '--force', '--api=' + api, '--arch=' + AndroidTargetTable.archs[target],
            '--install-dir=' + install_dir]
    run_command(command, args=args, name='make_standalone_toolchain')


def strip_libs(opts: AndroidOpts, product: str, target: str, api: str):
    toolchain_path = path_join(opts.android_toolchains_prefix, opts.toolchain_name_fmt % (target, api))

    tools_path = path_join(toolchain_path, 'bin')
    name_fmt = AndroidTargetTable.abi_names[target] + '-%s'

    strip = path_join(tools_path, name_fmt % 'strip')

    install_dir = path_join(opts.install_dir, '%s-%s-%s' % (product, target, opts.configuration))
    out_libs_dir = path_join(install_dir, 'lib')

    lib_files = globs(('*.a', '*.so'), dirpath=out_libs_dir)
    if len(lib_files):
        run_command(strip, args=['--strip-unneeded'] + lib_files, name='strip')


def configure(opts: AndroidOpts, product: str, target: str):
    env = { 'ANDROID_API_VERSION': get_api_version_or_min(opts, target) }

    if is_cross(target):
        import llvm

        if is_cross_mxe(target):
            llvm.make(opts, 'llvmwin64')
            setup_android_cross_mxe_template(env, opts, target, host_arch='x86_64')
        else:
            llvm.make(opts, 'llvm64')
            setup_android_cross_template(env, opts, target, host_arch='x86_64')
    else:
        make_standalone_toolchain(opts, target, env['ANDROID_API_VERSION'])
        setup_android_target_template(env, opts, target)

    if not os.path.isfile(path_join(opts.mono_source_root, 'configure')):
        runtime.run_autogen(opts)

    runtime.run_configure(env, opts, product, target)


def make(opts: AndroidOpts, product: str, target: str):
    env = { 'ANDROID_API_VERSION': get_api_version_or_min(opts, target) }

    build_dir = path_join(opts.configure_dir, '%s-%s-%s' % (product, target, opts.configuration))

    make_args = make_default_args(opts)
    make_args += ['-C', build_dir]

    run_command('make', args=make_args, name='make')
    run_command('make', args=['-C', '%s/mono' % build_dir, 'install'], name='make install mono')
    run_command('make', args=['-C', '%s/support' % build_dir, 'install'], name='make install support')
    run_command('make', args=['-C', '%s/data' % build_dir, 'install'], name='make install data')

    if opts.strip_libs and not is_cross(target):
        strip_libs(opts, product, target, env['ANDROID_API_VERSION'])


def clean(opts: AndroidOpts, product: str, target: str):
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
        'all-runtime': runtime_targets,
        'all-cross': cross_targets,
        'all-cross-win': cross_mxe_targets
    }

    target_values = runtime_targets + cross_targets + cross_mxe_targets + list(target_shortcuts)

    actions = OrderedDict()
    actions['configure'] = configure
    actions['make'] = make
    actions['clean'] = clean

    parser = cmd_utils.build_arg_parser(
        description='Builds the Mono runtime for Android',
        env_vars={
            'ANDROID_SDK_ROOT': 'Overrides default value for --android-sdk',
            'ANDROID_NDK_ROOT': 'Overrides default value for --android-ndk',
            'ANDROID_HOME': 'Same as ANDROID_SDK_ROOT'
        }
    )

    home = os.environ.get('HOME')
    android_sdk_default = os.environ.get('ANDROID_HOME', os.environ.get('ANDROID_SDK_ROOT', path_join(home, 'Android/Sdk')))
    android_ndk_default = os.environ.get('ANDROID_NDK_ROOT', path_join(android_sdk_default, 'ndk-bundle'))

    default_help = 'default: %(default)s'

    parser.add_argument('action', choices=['configure', 'make', 'clean'])
    parser.add_argument('--target', choices=target_values, action='append', required=True)
    parser.add_argument('--toolchains-prefix', default=path_join(home, 'android-toolchains'), help=default_help)
    parser.add_argument('--android-sdk', default=android_sdk_default, help=default_help)
    parser.add_argument('--android-ndk', default=android_ndk_default, help=default_help)
    parser.add_argument('--android-api-version', default='21', help=default_help)
    parser.add_argument('--android-cmake-version', default='autodetect', help=default_help)

    cmd_utils.add_runtime_arguments(parser, default_help)

    args = parser.parse_args(raw_args)

    input_action = args.action
    input_targets = args.target

    opts = android_opts_from_args(args)

    if not os.path.isdir(opts.mono_source_root):
        print('Mono sources directory not found: ' + opts.mono_source_root)
        sys.exit(1)

    targets = cmd_utils.expand_input_targets(input_targets, target_shortcuts)
    action = actions[input_action]

    try:
        for target in targets:
            action(opts, 'android', target)
    except BuildError as e:
        sys.exit(e.message)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
