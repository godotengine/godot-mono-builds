#!/usr/bin/python

from os import environ
from os.path import exists as path_exists, join as path_join, isfile, isdir, abspath
from sys import exit


class MonoBuildError(Exception):
    '''Generic exception for custom build errors'''
    def __init__(self, msg):
        super(MonoBuildError, self).__init__(msg)
        self.message = msg


def run_command(command, args=[], custom_env=None, name='command'):
    def cmd_args_to_str(cmd_args):
        return ' '.join([arg if not ' ' in arg else '"%s"' % arg for arg in cmd_args])

    assert isinstance(command, str) and isinstance(args, list)
    args = [command] + args

    import subprocess
    try:
        print('Running command \'%s\': %s' % (name, cmd_args_to_str(args)))
        if custom_env is None:
            subprocess.check_call(args)
        else:
            subprocess.check_call(args, env=custom_env)
        print('Command \'%s\' completed successfully' % name)
    except subprocess.CalledProcessError as e:
        raise MonoBuildError('\'%s\' exited with error code: %s' % (name, e.returncode))


# Creates the directory if no other file or directory with the same path exists
def mkdir_p(path):
    from os import makedirs
    if not path_exists(path):
        print('creating directory: ' + path)
        makedirs(path)


def chdir(path):
    from os import chdir as os_chdir
    print('entering directory: ' + path)
    os_chdir(path)


# Remove files and/or directories recursively
def rm_rf(*paths):
    from os import remove
    from shutil import rmtree
    for path in paths:
        if isfile(path):
            print('removing file: ' + path)
            remove(path)
        elif isdir(path):
            print('removing directory and its contents: ' + path)
            rmtree(path)


def globs(pathnames, dirpath='.'):
    import glob
    files = []
    for pathname in pathnames:
        files.extend(glob.glob(path_join(dirpath, pathname)))
    return files


TOOLCHAIN_NAME_FMT = '%s-api%s-clang'

CONFIGURATION = None
RELEASE = None

ANDROID_TOOLCHAINS_PREFIX = None

ANDROID_SDK_ROOT = None
ANDROID_NDK_ROOT = None

WITH_MONODROID = None
ENABLE_CXX = None
VERBOSE_MAKE = None
STRIP_LIBS = None

CONFIGURE_DIR = None
INSTALL_DIR = None

MONO_SOURCE_ROOT = None

_ANDROID_API_VERSION = None
_ANDROID_CMAKE_VERSION = None


class AndroidTargetInfo:
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


def android_autodetect_cmake():
    from distutils.version import StrictVersion
    from os import listdir

    sdk_cmake_basedir = path_join(ANDROID_SDK_ROOT, 'cmake')
    versions = []

    for entry in listdir(sdk_cmake_basedir):
        if isdir(path_join(sdk_cmake_basedir, entry)):
            try:
                version = StrictVersion(entry)
                versions += [version]
            except ValueError:
                continue # Not a version folder

    if len(versions) == 0:
        raise MonoBuildError('Cannot auto-detect Android CMake version')

    lattest_version = str(sorted(versions)[-1])
    print('Auto-detected Android CMake version: ' + lattest_version)

    return lattest_version


def get_api_version_or_min(target):
    min_versions = { 'arm64-v8a': '21', 'x86_64': '21' }
    if target in min_versions and int(_ANDROID_API_VERSION) < int(min_versions[target]):
        print('WARNING: %s is less than minimum platform for %s; using %s' % (_ANDROID_API_VERSION, target, min_versions[target]))
        return min_versions[target]
    return _ANDROID_API_VERSION


def get_android_cmake_version():
    return _ANDROID_CMAKE_VERSION if _ANDROID_CMAKE_VERSION != 'autodetect' else android_autodetect_cmake()


def setup_runtime_template(env, product, target, host_triple):
    BITNESS = ''
    if any(s in host_triple for s in ['i686', 'i386']):
        BITNESS = '-m32'
    elif 'x86_64' in host_triple:
        BITNESS = '-m64'

    CFLAGS = []
    CFLAGS += ['-O2', '-g'] if RELEASE else ['-O0', '-ggdb3', '-fno-omit-frame-pointer']
    CFLAGS += env.get('_%s-%s_CFLAGS' % (product, target), [])
    CFLAGS += env.get('%s-%s_CFLAGS' % (product, target), [])
    CFLAGS += [BITNESS] if BITNESS else []

    CXXFLAGS = []
    CXXFLAGS += ['-O2', '-g'] if RELEASE else ['-O0', '-ggdb3', '-fno-omit-frame-pointer']
    CXXFLAGS += env.get('_%s-%s_CXXFLAGS' % (product, target), [])
    CXXFLAGS += env.get('%s-%s_CXXFLAGS' % (product, target), [])
    CXXFLAGS += [BITNESS] if BITNESS else []

    CPPFLAGS = []
    CPPFLAGS += ['-O2', '-g'] if RELEASE else ['-O0', '-ggdb3', '-fno-omit-frame-pointer']
    CPPFLAGS += env.get('_%s-%s_CPPFLAGS' % (product, target), [])
    CPPFLAGS += env.get('%s-%s_CPPFLAGS' % (product, target), [])
    CPPFLAGS += [BITNESS] if BITNESS else []

    CXXCPPFLAGS = []
    CXXCPPFLAGS += ['-O2', '-g'] if RELEASE else ['-O0', '-ggdb3', '-fno-omit-frame-pointer']
    CXXCPPFLAGS += env.get('_%s-%s_CXXCPPFLAGS' % (product, target), [])
    CXXCPPFLAGS += env.get('%s-%s_CXXCPPFLAGS' % (product, target), [])
    CXXCPPFLAGS += [BITNESS] if BITNESS else []

    LDFLAGS = []
    LDFLAGS += env.get('_%s-%s_LDFLAGS' % (product, target), [])
    LDFLAGS += env.get('%s-%s_LDFLAGS' % (product, target), [])

    AC_VARS = []
    AC_VARS += env.get('_%s-%s_AC_VARS' % (product, target), [])
    AC_VARS += env.get('%s-%s_AC_VARS' % (product, target), [])

    CONFIGURE_ENVIRONMENT = {}

    def append_product_env_var(var_name):
        val = env.get('_%s-%s_%s' % (product, target, var_name), '')
        if val:
            CONFIGURE_ENVIRONMENT[var_name] = val

    append_product_env_var('AR')
    append_product_env_var('AS')
    append_product_env_var('CC')
    append_product_env_var('CPP')
    append_product_env_var('CXX')
    append_product_env_var('CXXCPP')
    append_product_env_var('DLLTOOL')
    append_product_env_var('LD')
    append_product_env_var('OBJDUMP')
    append_product_env_var('RANLIB')
    append_product_env_var('CMAKE')
    append_product_env_var('STRIP')

    CONFIGURE_ENVIRONMENT['CFLAGS'] = CFLAGS
    CONFIGURE_ENVIRONMENT['CXXFLAGS'] = CXXFLAGS
    CONFIGURE_ENVIRONMENT['CPPFLAGS'] = CPPFLAGS
    CONFIGURE_ENVIRONMENT['CXXCPPFLAGS'] = CXXCPPFLAGS
    CONFIGURE_ENVIRONMENT['LDFLAGS'] = LDFLAGS

    CONFIGURE_ENVIRONMENT.update(env.get('_%s-%s_CONFIGURE_ENVIRONMENT' % (product, target), {}))
    CONFIGURE_ENVIRONMENT.update(env.get('%s-%s_CONFIGURE_ENVIRONMENT' % (product, target), {}))

    CONFIGURE_FLAGS = []
    CONFIGURE_FLAGS += ['--host=%s' % host_triple] if host_triple else []
    CONFIGURE_FLAGS += ['--cache-file=%s/%s-%s-%s.config.cache' % (CONFIGURE_DIR, product, target, CONFIGURATION)]
    CONFIGURE_FLAGS += ['--prefix=%s/%s-%s-%s' % (INSTALL_DIR, product, target, CONFIGURATION)]
    CONFIGURE_FLAGS += ['--enable-cxx'] if ENABLE_CXX else []
    # CONFIGURE_FLAGS += env['_cross-runtime_%s-%s_CONFIGURE_FLAGS' % (product, target)]
    CONFIGURE_FLAGS += env.get('_%s-%s_CONFIGURE_FLAGS' % (product, target), [])
    CONFIGURE_FLAGS += env.get('%s-%s_CONFIGURE_FLAGS' % (product, target), [])

    env['_runtime_%s-%s_AC_VARS' % (product, target)] = AC_VARS
    env['_runtime_%s-%s_CONFIGURE_ENVIRONMENT' % (product, target)] = CONFIGURE_ENVIRONMENT
    env['_runtime_%s-%s_CONFIGURE_FLAGS' % (product, target)] = CONFIGURE_FLAGS


def setup_android_target_template(env, target):
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

    env.update(extra_target_envs[target])

    android_new_ndk = True

    with open(path_join(ANDROID_NDK_ROOT, 'source.properties')) as file:
        for line in file:
            line = line.strip()
            if line.startswith('Pkg.Revision ') or line.startswith('Pkg.Revision='):
                pkg_revision = line.split('=')[1].strip()
                mayor = int(pkg_revision.split('.')[0])
                android_new_ndk = mayor >= 18
                break

    arch = AndroidTargetInfo.archs[target]
    abi_name = AndroidTargetInfo.abi_names[target]
    host_triple = AndroidTargetInfo.host_triples[target]
    api = env['ANDROID_API_VERSION']

    toolchain_path = path_join(ANDROID_TOOLCHAINS_PREFIX, TOOLCHAIN_NAME_FMT % (target, api))

    tools_path = path_join(toolchain_path, 'bin')
    name_fmt = abi_name + '-%s'

    sdk_cmake_dir = path_join(ANDROID_SDK_ROOT, 'cmake', get_android_cmake_version())
    if not isdir(sdk_cmake_dir):
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
    if not isfile(CPP):
        CPP = path_join(tools_path, (name_fmt % 'clang'))
        CPP += ' -E'

    CXXCPP = path_join(tools_path, name_fmt % 'cpp')
    if not isfile(CXXCPP):
        CXXCPP = path_join(tools_path, (name_fmt % 'clang++'))
        CXXCPP += ' -E'

    ccache_path = environ.get('CCACHE', '')
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

    CFLAGS += ['-fstack-protector']
    CFLAGS += ['-DMONODROID=1'] if WITH_MONODROID else []
    CFLAGS += ['-D__ANDROID_API__=' + api] if android_new_ndk else []
    CXXFLAGS += ['-fstack-protector']
    CXXFLAGS += ['-DMONODROID=1'] if WITH_MONODROID else []
    CXXFLAGS += ['-D__ANDROID_API__=' + api] if android_new_ndk else []

    CPPFLAGS += ['-I%s/sysroot/usr/include' % toolchain_path]
    CXXCPPFLAGS += ['-I%s/sysroot/usr/include' % toolchain_path]

    path_link = '%s/platforms/android-%s/arch-%s/usr/lib' % (ANDROID_NDK_ROOT, api, arch)

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
        '--with-btls-android-ndk=%s' % ANDROID_NDK_ROOT,
        '--with-btls-android-api=%s' % api,
    ]

    CONFIGURE_FLAGS += ['--enable-monodroid'] if WITH_MONODROID else []
    CONFIGURE_FLAGS += ['--with-btls-android-ndk-asm-workaround'] if android_new_ndk else []

    CONFIGURE_FLAGS += [
        '--with-btls-android-cmake-toolchain=%s/build/cmake/android.toolchain.cmake' % ANDROID_NDK_ROOT,
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

    setup_runtime_template(env, 'android', target, host_triple)


def make_standalone_toolchain(target, api):
    install_dir = path_join(ANDROID_TOOLCHAINS_PREFIX, TOOLCHAIN_NAME_FMT % (target, api))
    if isdir(path_join(install_dir, 'bin')):
        return # Looks like it's already there, so no need to re-create it
    command = path_join(ANDROID_NDK_ROOT, 'build', 'tools', 'make_standalone_toolchain.py')
    args = ['--verbose', '--force', '--api=' + api, '--arch=' + AndroidTargetInfo.archs[target],
            '--install-dir=' + install_dir]
    run_command(command, args=args, name='make_standalone_toolchain')


def strip_libs(product, target, api):
    toolchain_path = path_join(ANDROID_TOOLCHAINS_PREFIX, TOOLCHAIN_NAME_FMT % (target, api))

    tools_path = path_join(toolchain_path, 'bin')
    name_fmt = AndroidTargetInfo.abi_names[target] + '-%s'

    STRIP = path_join(tools_path, name_fmt % 'strip')

    install_dir = '%s/%s-%s-%s' % (INSTALL_DIR, product, target, CONFIGURATION)
    out_libs_dir = path_join(install_dir, 'lib')

    lib_files = globs(('*.a', '*.so'), dirpath=out_libs_dir)
    if len(lib_files):
        run_command(STRIP, args=['--strip-unneeded'] + lib_files, name='strip')


def configure(product, target):
    env = { 'ANDROID_API_VERSION': get_api_version_or_min(target) }

    make_standalone_toolchain(target, env['ANDROID_API_VERSION'])

    setup_android_target_template(env, target)

    chdir(MONO_SOURCE_ROOT)
    autogen_env = environ.copy()
    autogen_env['NOCONFIGURE'] = '1'
    run_command(path_join(MONO_SOURCE_ROOT, 'autogen.sh'), custom_env=autogen_env, name='autogen')

    build_dir = CONFIGURE_DIR + '/%s-%s-%s' % (product, target, CONFIGURATION)
    mkdir_p(build_dir)
    chdir(build_dir)

    def str_dict_val(val):
        if isinstance(val, list):
            return ' '.join(val) # No need for quotes
        return val

    ac_vars = env['_runtime_%s-%s_AC_VARS' % (product, target)]
    configure_env = env['_runtime_%s-%s_CONFIGURE_ENVIRONMENT' % (product, target)]
    configure_env = [('%s=%s' % (key, str_dict_val(value))) for (key, value) in configure_env.items()]
    configure_flags = env['_runtime_%s-%s_CONFIGURE_FLAGS' % (product, target)]

    command = path_join(MONO_SOURCE_ROOT, 'configure')
    configure_args = ac_vars + configure_env + configure_flags

    run_command(command, args=configure_args, name='configure')


def make(product, target):
    env = { 'ANDROID_API_VERSION': get_api_version_or_min(target) }

    build_dir = CONFIGURE_DIR + '/%s-%s-%s' % (product, target, CONFIGURATION)
    chdir(build_dir)

    make_args = ['V=1'] if VERBOSE_MAKE else []

    run_command('make', args=make_args, name='make')
    run_command('make', args=['install'], name='make install')

    if STRIP_LIBS:
        strip_libs(product, target, env['ANDROID_API_VERSION'])


def clean(product, target):
    rm_rf(
        CONFIGURE_DIR + '/toolchains/%s-%s' % (product, target),
        CONFIGURE_DIR + '/%s-%s-%s' % (product, target, CONFIGURATION),
        CONFIGURE_DIR + '/%s-%s-%s.config.cache' % (product, target, CONFIGURATION),
        INSTALL_DIR + '/%s-%s-%s' % (product, target, CONFIGURATION)
    )


def set_arguments(args):
    global CONFIGURATION, RELEASE, ANDROID_TOOLCHAINS_PREFIX, ANDROID_SDK_ROOT, ANDROID_NDK_ROOT, \
        _ANDROID_API_VERSION, _ANDROID_CMAKE_VERSION, WITH_MONODROID, ENABLE_CXX, \
        VERBOSE_MAKE, STRIP_LIBS, CONFIGURE_DIR, INSTALL_DIR, MONO_SOURCE_ROOT, CONFIGURATION

    # Need to make paths absolute as we change cwd later

    CONFIGURATION = args.configuration
    RELEASE = (CONFIGURATION == 'release')
    ANDROID_TOOLCHAINS_PREFIX = abspath(args.toolchains_prefix)
    ANDROID_SDK_ROOT = abspath(args.android_sdk)
    ANDROID_NDK_ROOT = abspath(args.android_ndk)
    WITH_MONODROID = args.with_monodroid
    ENABLE_CXX = args.enable_cxx
    VERBOSE_MAKE = args.verbose_make
    STRIP_LIBS = args.strip_libs
    CONFIGURE_DIR = abspath(args.configure_dir)
    INSTALL_DIR = abspath(args.install_dir)
    MONO_SOURCE_ROOT = abspath(args.mono_sources)

    _ANDROID_API_VERSION = args.android_api_version
    _ANDROID_CMAKE_VERSION = args.android_cmake_version


def main(raw_args):
    import argparse

    from collections import OrderedDict
    from textwrap import dedent

    target_indiv_values = ['armeabi-v7a', 'arm64-v8a', 'x86', 'x86_64']
    target_values = target_indiv_values + ['all']

    actions = OrderedDict()
    actions['configure'] = configure
    actions['make'] = make
    actions['clean'] = clean

    parser = argparse.ArgumentParser(
        description='Builds the Mono runtime for Android',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=dedent('''\
            environment variables:
                ANDROID_SDK_ROOT: Overrides default value for --android-sdk
                ANDROID_NDK_ROOT: Overrides default value for --android-ndk
                MONO_SOURCE_ROOT: Overrides default value for --mono-sources
                ANDROID_HOME: Same as ANDROID_SDK_ROOT
            ''')
        )

    def custom_bool(val):
        if isinstance(val, bool):
            return val
        if val.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif val.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            raise argparse.ArgumentTypeError('Boolean value expected.')

    home = environ.get('HOME')
    android_sdk_default = environ.get('ANDROID_HOME', environ.get('ANDROID_SDK_ROOT', path_join(home, 'Android/Sdk')))
    android_ndk_default = environ.get('ANDROID_NDK_ROOT', path_join(android_sdk_default, 'ndk-bundle'))
    mono_sources_default = environ.get('MONO_SOURCE_ROOT', '')

    default_help = dedent('default: %(default)s')

    parser.add_argument('action', choices=['configure', 'make', 'clean'])
    parser.add_argument('--target', choices=target_values, action='append', required=True)
    parser.add_argument('--configuration', choices=['release', 'debug'], default='release', help=default_help)
    parser.add_argument('--toolchains-prefix', default=path_join(home, 'android-toolchains'), help=default_help)
    parser.add_argument('--android-sdk', default=android_sdk_default, help=default_help)
    parser.add_argument('--android-ndk', default=android_ndk_default, help=default_help)
    parser.add_argument('--android-api-version', default='18', help=default_help)
    parser.add_argument('--android-cmake-version', default='autodetect', help=default_help)
    parser.add_argument('--enable-cxx', action='store_true', default=False, help=default_help)
    parser.add_argument('--verbose-make', action='store_true', default=False, help=default_help)
    parser.add_argument('--strip-libs', type=custom_bool, default=True, help=default_help)
    parser.add_argument('--with-monodroid', type=custom_bool, default=True, help=default_help)
    parser.add_argument('--configure-dir', default=path_join(home, 'mono-configs'), help=default_help)
    parser.add_argument('--install-dir', default=path_join(home, 'mono-installs'), help=default_help)

    if mono_sources_default:
        parser.add_argument('--mono-sources', default=mono_sources_default, help=default_help)
    else:
        parser.add_argument('--mono-sources', required=True)

    args = parser.parse_args(raw_args)

    action = args.action
    targets = args.target

    set_arguments(args)

    if not isdir(MONO_SOURCE_ROOT):
        print('Mono sources directory not found: ' + MONO_SOURCE_ROOT)
        exit(1)

    android_targets = []

    if 'all' in targets:
        android_targets = target_indiv_values[:]
    else:
        for target in targets:
            if not target in android_targets:
                android_targets += [target]

    action_fn = actions[action]

    try:
        for target in android_targets:
            action_fn('android', target)
    except MonoBuildError as e:
        exit(e.message)


if __name__ == '__main__':
    from sys import argv
    main(argv[1:])
