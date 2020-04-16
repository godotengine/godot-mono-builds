
import os
import os.path
from options import *


class BuildError(Exception):
    '''Generic exception for custom build errors'''
    def __init__(self, msg):
        super(BuildError, self).__init__(msg)
        self.message = msg


def run_command(command, args=[], cwd=None, env=None, name='command'):
    def cmd_args_to_str(cmd_args):
        return ' '.join([arg if not ' ' in arg else '"%s"' % arg for arg in cmd_args])

    assert isinstance(command, str) and isinstance(args, list)
    args = [command] + args

    check_call_args = {}
    if cwd is not None:
        check_call_args['cwd'] = cwd
    if env is not None:
        check_call_args['env'] = env

    import subprocess
    try:
        print('Running command \'%s\': %s' % (name, subprocess.list2cmdline(args)))
        subprocess.check_call(args, **check_call_args)
        print('Command \'%s\' completed successfully' % name)
    except subprocess.CalledProcessError as e:
        raise BuildError('\'%s\' exited with error code: %s' % (name, e.returncode))


print_env_sh_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'print_env.sh')


def source(script: str, cwd=None) -> dict:
    popen_args = {}
    if cwd is not None:
        popen_args['cwd'] = cwd

    import subprocess
    cmd = 'bash -c \'source %s; bash %s\'' % (script, print_env_sh_path)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, shell=True, **popen_args)
    output = proc.communicate()[0]
    return dict(line.split('=', 1) for line in output.decode().split('\x00') if line)


# Creates the directory if no other file or directory with the same path exists
def mkdir_p(path):
    if not os.path.exists(path):
        print('creating directory: ' + path)
        os.makedirs(path)


# Remove files and/or directories recursively
def rm_rf(*paths):
    from shutil import rmtree
    for path in paths:
        if os.path.isfile(path):
            print('removing file: ' + path)
            os.remove(path)
        elif os.path.isdir(path):
            print('removing directory and its contents: ' + path)
            rmtree(path)


ENV_PATH_SEP = ';' if os.name == 'nt' else ':'


def find_executable(name) -> str:
    is_windows = os.name == 'nt'
    windows_exts = os.environ['PATHEXT'].split(ENV_PATH_SEP) if is_windows else None
    path_dirs = os.environ['PATH'].split(ENV_PATH_SEP)

    search_dirs = path_dirs + [os.getcwd()] # cwd is last in the list

    for dir in search_dirs:
        path = os.path.join(dir, name)

        if is_windows:
            for extension in windows_exts:
                path_with_ext = path + extension

                if os.path.isfile(path_with_ext) and os.access(path_with_ext, os.X_OK):
                    return path_with_ext
        else:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

    return ''


def replace_in_new_file(src_file, search, replace, dst_file):
    with open(src_file, 'r') as file:
        content = file.read()

    content = content.replace(search, replace)

    with open(dst_file, 'w') as file:
        file.write(content)


def replace_in_file(filepath, search, replace):
    replace_in_new_file(src_file=filepath, search=search, replace=replace, dst_file=filepath)


def touch(filepath: str):
    import pathlib
    pathlib.Path(filepath).touch()


def get_emsdk_root():
    # Shamelessly copied from Godot's detect.py
    em_config_file = os.getenv('EM_CONFIG') or os.path.expanduser('~/.emscripten')
    if not os.path.exists(em_config_file):
        raise BuildError("Emscripten configuration file '%s' does not exist" % em_config_file)
    with open(em_config_file) as f:
        em_config = {}
        try:
            # Emscripten configuration file is a Python file with simple assignments.
            exec(f.read(), em_config)
        except StandardError as e:
            raise BuildError("Emscripten configuration file '%s' is invalid:\n%s" % (em_config_file, e))
    if 'BINARYEN_ROOT' in em_config and os.path.isdir(os.path.join(em_config.get('BINARYEN_ROOT'), 'emscripten')):
        # New style, emscripten path as a subfolder of BINARYEN_ROOT
        return os.path.join(em_config.get('BINARYEN_ROOT'), 'emscripten')
    elif 'EMSCRIPTEN_ROOT' in em_config:
        # Old style (but can be there as a result from previous activation, so do last)
        return em_config.get('EMSCRIPTEN_ROOT')
    else:
        raise BuildError("'BINARYEN_ROOT' or 'EMSCRIPTEN_ROOT' missing in Emscripten configuration file '%s'" % em_config_file)


def globs(pathnames, dirpath='.'):
    import glob
    files = []
    for pathname in pathnames:
        files.extend(glob.glob(os.path.join(dirpath, pathname)))
    return files


def xcrun_find_sdk(sdk_name):
    import subprocess
    xcrun_output = subprocess.check_output(['xcrun', '--sdk', sdk_name, '--show-sdk-path']).decode().strip()
    if xcrun_output.startswith('xcrun: error: SDK "%s" cannot be located' % sdk_name):
        return ''
    sdk_path = xcrun_output
    return sdk_path


def chmod_plus_x(file):
    import os
    import stat
    umask = os.umask(0)
    os.umask(umask)
    st = os.stat(file)
    os.chmod(file, st.st_mode | ((stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) & ~umask))


def get_clang_resource_dir(clang_command):
    import shlex
    from subprocess import check_output
    return check_output(shlex.split(clang_command) + ['-print-resource-dir']).strip().decode('utf-8')


def try_find_libclang(toolchain_path: str = '', llvm_config=''):
    import sys
    from subprocess import check_output

    hint_paths = []

    if toolchain_path:
        libclang = os.path.join(toolchain_path, 'usr', 'lib', 'libclang.dylib')
        if os.path.isfile(libclang):
            print('Found libclang at: \'%s\'' % libclang)
            return libclang

    if not llvm_config:
        llvm_config = find_executable('llvm-config')
        if not llvm_config:
            print('WARNING: llvm-config not found')
            return ''
    elif not os.path.isfile(llvm_config):
        raise RuntimeError('Specified llvm-config file not found: \'%s\'' % llvm_config)

    llvm_libdir = check_output([llvm_config, '--libdir']).strip().decode('utf-8')
    if llvm_libdir:
        libsuffix = '.dylib' if sys.platform == 'darwin' else '.so'
        hints = ['libclang', 'clang']
        libclang = next((p for p in [os.path.join(llvm_libdir, h + libsuffix) for h in hints] if os.path.isfile(p)), '')
        if libclang:
            print('Found libclang at: \'%s\'' % libclang)
        return libclang

    return ''


def create_osxcross_wrapper(opts: RuntimeOpts, product: str, target: str, toolchain_path : str):
    # OSXCROSS toolchain executables use rpath to locate the toolchain's shared libraries.
    # However, when moving the toolchain without care, the rpaths can be broken.
    # Since fixing the rpaths can be tedious, we use this wrapper to override LD_LIBRARY_PATH.
    # The reason we don't just run configure and make with LD_LIBRARY_PATH is because
    # we want the resulting configuration to be independent from out python scripts.

    wrapper_src = """#!/bin/bash
OSXCROSS_COMMAND=$1;
shift;
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:%s";
${OSXCROSS_COMMAND} "$@";
exit $?;
""" % os.path.join(toolchain_path, 'lib')

    build_dir = os.path.join(opts.configure_dir, '%s-%s-%s' % (product, target, opts.configuration))
    wrapper_path = os.path.join(build_dir, 'osxcross_cmd_wrapper.sh')

    mkdir_p(build_dir)

    with open(wrapper_path, 'w') as f:
        f.write(wrapper_src)

    chmod_plus_x(wrapper_path)

    return wrapper_path
