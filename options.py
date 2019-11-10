
from dataclasses import dataclass
from os.path import abspath


@dataclass
class BaseOpts:
    verbose_make: bool
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
    android_toolchains_prefix: str
    android_sdk_root: str
    android_ndk_root: str
    with_monodroid: bool
    android_api_version: str
    android_cmake_version: str
    toolchain_name_fmt: str = '%s-api%s-clang'


@dataclass
class BclOpts(BaseOpts):
    tests: bool


# Need to make paths absolute as we change cwd


def base_opts_from_args(args):
    from os.path import abspath
    return BaseOpts(
        verbose_make = args.verbose_make,
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
        android_toolchains_prefix = abspath(args.toolchains_prefix),
        android_sdk_root = abspath(args.android_sdk),
        android_ndk_root = abspath(args.android_ndk),
        with_monodroid = args.with_monodroid,
        android_api_version = args.android_api_version,
        android_cmake_version = args.android_cmake_version
    )


def bcl_opts_from_args(args):
    return BclOpts(
        **vars(base_opts_from_args(args)),
        tests = args.tests
    )
