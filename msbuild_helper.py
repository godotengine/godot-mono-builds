import os

from os_utils import *


def find_dotnet_cli():
    import os.path

    for hint_dir in os.environ["PATH"].split(os.pathsep):
        hint_dir = hint_dir.strip('"')
        hint_path = os.path.join(hint_dir, "dotnet")
        if os.path.isfile(hint_path) and os.access(hint_path, os.X_OK):
            return hint_path


def find_msbuild():
    import os.path
    import sys

    hint_dirs = []
    if sys.platform == "darwin":
        hint_dirs[:0] = [
            "/Library/Frameworks/Mono.framework/Versions/Current/bin",
            "/usr/local/var/homebrew/linked/mono/bin",
        ]

    for hint_dir in hint_dirs:
        hint_path = os.path.join(hint_dir, "msbuild")
        if os.path.isfile(hint_path):
            return hint_path

    for hint_dir in os.environ["PATH"].split(os.pathsep):
        hint_dir = hint_dir.strip('"')
        hint_path = os.path.join(hint_dir, "msbuild")
        if os.path.isfile(hint_path) and os.access(hint_path, os.X_OK):
            return hint_path

    return None


def build_solution(solution_path, build_config, extra_msbuild_args=[]):
    msbuild_args = []

    dotnet_cli = find_dotnet_cli()

    if dotnet_cli:
        msbuild_path = dotnet_cli
        msbuild_args += ["msbuild"]  # `dotnet msbuild` command
    else:
        msbuild_path = find_msbuild()
        if msbuild_path is None:
            raise BuildError("Cannot find MSBuild executable")

    print("MSBuild path: " + msbuild_path)

    # Build solution

    msbuild_args += [solution_path, "/restore", "/t:Build", "/p:Configuration=" + build_config]
    msbuild_args += extra_msbuild_args

    run_command(msbuild_path, msbuild_args, name="msbuild")
