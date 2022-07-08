
from dataclasses import dataclass
from os.path import abspath


@dataclass
class BaseOpts:
    verbose_make: bool
    jobs: str
    configure_dir: str
    install_dir: str
    mono_source_root: str
    mxe_prefix: str


@dataclass
class RuntimeOpts(BaseOpts):
    configuration: str
    release: bool
    enable_cxx: bool
    strip_libs: bool


@dataclass
class AndroidOpts(RuntimeOpts):
    android_sdk_root: str
    android_ndk_version: str
    android_api_version: str
    android_cmake_version: str
    toolchain_name_fmt: str = '%s-api%s-clang'


@dataclass
class iOSOpts(RuntimeOpts):
    ios_toolchain_path: str
    ios_sdk_path: str
    ios_version_min: str
    osx_toolchain_path: str
    osx_sdk_path: str
    osx_triple_abi: str


@dataclass
class DesktopOpts(RuntimeOpts):
    with_llvm: bool


@dataclass
class BclOpts(BaseOpts):
    tests: bool
    remove_pdb: bool


# Need to make paths absolute as we change cwd


def base_opts_from_args(args):
    from os.path import abspath
    return BaseOpts(
        verbose_make = args.verbose_make,
        jobs = args.jobs,
        configure_dir = abspath(args.configure_dir),
        install_dir = abspath(args.install_dir),
        mono_source_root = abspath(args.mono_sources),
        mxe_prefix = args.mxe_prefix
    )


def runtime_opts_from_args(args):
    return RuntimeOpts(
        **vars(base_opts_from_args(args)),
        configuration = args.configuration,
        release = (args.configuration == 'release'),
        enable_cxx = args.enable_cxx,
        strip_libs = args.strip_libs
    )


def android_opts_from_args(args):
    return AndroidOpts(
        **vars(runtime_opts_from_args(args)),
        android_sdk_root = abspath(args.android_sdk),
        android_ndk_version = args.android_ndk_version,
        android_api_version = args.android_api_version,
        android_cmake_version = args.android_cmake_version
    )


def ios_opts_from_args(args):
    return iOSOpts(
        **vars(runtime_opts_from_args(args)),
        ios_toolchain_path = abspath(args.ios_toolchain),
        ios_sdk_path = abspath(args.ios_sdk) if args.ios_sdk else '',
        ios_version_min = args.ios_version_min,
        osx_toolchain_path = abspath(args.osx_toolchain),
        osx_sdk_path = abspath(args.osx_sdk) if args.ios_sdk else '',
        osx_triple_abi = args.osx_triple_abi
    )


def bcl_opts_from_args(args):
    return BclOpts(
        **vars(base_opts_from_args(args)),
        tests = args.tests,
        remove_pdb = args.remove_pdb
    )


def desktop_opts_from_args(args):
    return DesktopOpts(
        **vars(runtime_opts_from_args(args)),
        with_llvm = args.with_llvm
    )


def make_default_args(opts: BaseOpts):
    make_args = ['-j%s' % opts.jobs]
    make_args += ['V=1'] if opts.verbose_make else []
    return make_args
