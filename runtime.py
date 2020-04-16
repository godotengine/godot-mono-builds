
import os
from os.path import join as path_join

from options import RuntimeOpts
from os_utils import *


def setup_runtime_template(env: dict, opts: RuntimeOpts, product: str, target: str, host_triple: str, llvm: str=''):
    BITNESS = ''
    if any(s in host_triple for s in ['i686', 'i386']):
        BITNESS = '-m32'
    elif 'x86_64' in host_triple:
        BITNESS = '-m64'

    CFLAGS = []
    CFLAGS += ['-O2', '-g'] if opts.release else ['-O0', '-ggdb3', '-fno-omit-frame-pointer']
    CFLAGS += env.get('_%s-%s_CFLAGS' % (product, target), [])
    CFLAGS += env.get('%s-%s_CFLAGS' % (product, target), [])
    CFLAGS += [BITNESS] if BITNESS else []

    CXXFLAGS = []
    CXXFLAGS += ['-O2', '-g'] if opts.release else ['-O0', '-ggdb3', '-fno-omit-frame-pointer']
    CXXFLAGS += env.get('_%s-%s_CXXFLAGS' % (product, target), [])
    CXXFLAGS += env.get('%s-%s_CXXFLAGS' % (product, target), [])
    CXXFLAGS += [BITNESS] if BITNESS else []

    CPPFLAGS = []
    CPPFLAGS += ['-O2', '-g'] if opts.release else ['-O0', '-ggdb3', '-fno-omit-frame-pointer']
    CPPFLAGS += env.get('_%s-%s_CPPFLAGS' % (product, target), [])
    CPPFLAGS += env.get('%s-%s_CPPFLAGS' % (product, target), [])
    CPPFLAGS += [BITNESS] if BITNESS else []

    CXXCPPFLAGS = []
    CXXCPPFLAGS += ['-O2', '-g'] if opts.release else ['-O0', '-ggdb3', '-fno-omit-frame-pointer']
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

    def set_product_env_var(var_name):
        val = env.get('_%s-%s_%s' % (product, target, var_name), '')
        if val:
            CONFIGURE_ENVIRONMENT[var_name] = val

    set_product_env_var('AR')
    set_product_env_var('AS')
    set_product_env_var('CC')
    set_product_env_var('CPP')
    set_product_env_var('CXX')
    set_product_env_var('CXXCPP')
    set_product_env_var('DLLTOOL')
    set_product_env_var('LD')
    set_product_env_var('OBJDUMP')
    set_product_env_var('RANLIB')
    set_product_env_var('CMAKE')
    set_product_env_var('STRIP')

    CONFIGURE_ENVIRONMENT['CFLAGS'] = CFLAGS
    CONFIGURE_ENVIRONMENT['CXXFLAGS'] = CXXFLAGS
    CONFIGURE_ENVIRONMENT['CPPFLAGS'] = CPPFLAGS
    CONFIGURE_ENVIRONMENT['CXXCPPFLAGS'] = CXXCPPFLAGS
    CONFIGURE_ENVIRONMENT['LDFLAGS'] = LDFLAGS

    CONFIGURE_ENVIRONMENT.update(env.get('_%s-%s_CONFIGURE_ENVIRONMENT' % (product, target), {}))
    CONFIGURE_ENVIRONMENT.update(env.get('%s-%s_CONFIGURE_ENVIRONMENT' % (product, target), {}))

    CONFIGURE_FLAGS = []
    CONFIGURE_FLAGS += ['--host=%s' % host_triple] if host_triple else []
    CONFIGURE_FLAGS += ['--cache-file=%s/%s-%s-%s.config.cache' % (opts.configure_dir, product, target, opts.configuration)]
    CONFIGURE_FLAGS += ['--prefix=%s/%s-%s-%s' % (opts.install_dir, product, target, opts.configuration)]
    CONFIGURE_FLAGS += ['--enable-cxx'] if opts.enable_cxx else []
    CONFIGURE_FLAGS += env.get('_cross-runtime_%s-%s_CONFIGURE_FLAGS' % (product, target), [])
    CONFIGURE_FLAGS += env.get('_%s-%s_CONFIGURE_FLAGS' % (product, target), [])
    CONFIGURE_FLAGS += env.get('%s-%s_CONFIGURE_FLAGS' % (product, target), [])

    if llvm:
        CONFIGURE_FLAGS += ['--with-llvm=%s/llvm-%s' % (opts.install_dir, llvm)]

    env['_runtime_%s-%s_AC_VARS' % (product, target)] = AC_VARS
    env['_runtime_%s-%s_CONFIGURE_ENVIRONMENT' % (product, target)] = CONFIGURE_ENVIRONMENT
    env['_runtime_%s-%s_CONFIGURE_FLAGS' % (product, target)] = CONFIGURE_FLAGS


def setup_runtime_cross_template(env: dict, opts: RuntimeOpts, product: str, target: str, host_triple: str,
                target_triple: str, device_target: str, llvm: str, offsets_dumper_abi: str):
    CONFIGURE_FLAGS = [
        '--target=%s' % target_triple,
        '--with-cross-offsets=%s.h' % target_triple,
        '--with-llvm=%s/llvm-%s' % (opts.install_dir, llvm)
    ]

    env['_cross-runtime_%s-%s_CONFIGURE_FLAGS' % (product, target)] = CONFIGURE_FLAGS

    new_offsets_tool_path = '%s/mono/tools/offsets-tool/offsets-tool.py' % opts.mono_source_root
    old_offsets_tool_path = '%s/tools/offsets-tool-py/offsets-tool.py' % opts.mono_source_root

    old_offsets_tool = not os.path.isfile(new_offsets_tool_path)

    offsets_tool_env = None

    if old_offsets_tool:
        # Setup old offsets-tool-py if present (new location doesn't require setup)
        run_command('make', ['-C', '%s/tools/offsets-tool-py' % opts.mono_source_root, 'setup'], name='make offsets-tool-py')

        # Run offsets-tool in its virtual env
        virtualenv_vars = source('%s/tools/offsets-tool-py/offtool/bin/activate' % opts.mono_source_root)

        offsets_tool_env = os.environ.copy()
        offsets_tool_env.update(virtualenv_vars)

    build_dir = '%s/%s-%s-%s' % (opts.configure_dir, product, target, opts.configuration)
    mkdir_p(build_dir)

    run_command('python3', [
            old_offsets_tool_path if old_offsets_tool else new_offsets_tool_path,
            '--targetdir=%s/%s-%s-%s' % (opts.configure_dir, product, device_target, opts.configuration),
            '--abi=%s' % offsets_dumper_abi,
            '--monodir=%s' % opts.mono_source_root,
            '--outfile=%s/%s.h' % (build_dir, target_triple)
        ] + env['_%s-%s_OFFSETS_DUMPER_ARGS' % (product, target)],
        env=offsets_tool_env, name='offsets-tool')

    # Runtime template
    setup_runtime_template(env, opts, product, target, host_triple)


def run_autogen(opts: RuntimeOpts):
    autogen_env = os.environ.copy()
    autogen_env['NOCONFIGURE'] = '1'

    if not find_executable('glibtoolize') and 'CUSTOM_GLIBTOOLIZE_PATH' in os.environ:
        autogen_env['PATH'] = os.environ['CUSTOM_GLIBTOOLIZE_PATH'] + ':' + autogen_env['PATH']

    run_command(os.path.join(opts.mono_source_root, 'autogen.sh'), cwd=opts.mono_source_root, env=autogen_env, name='autogen')


def run_configure(env: dict, opts: RuntimeOpts, product: str, target: str):
    build_dir = path_join(opts.configure_dir, '%s-%s-%s' % (product, target, opts.configuration))
    mkdir_p(build_dir)

    def str_dict_val(val):
        if isinstance(val, list):
            return ' '.join(val) # Don't need to surround with quotes
        return val

    ac_vars = env['_runtime_%s-%s_AC_VARS' % (product, target)]
    configure_env_args = env['_runtime_%s-%s_CONFIGURE_ENVIRONMENT' % (product, target)]
    configure_env_args = [('%s=%s' % (key, str_dict_val(value))) for (key, value) in configure_env_args.items()]
    configure_flags = env['_runtime_%s-%s_CONFIGURE_FLAGS' % (product, target)]

    configure = path_join(opts.mono_source_root, 'configure')
    configure_args = ac_vars + configure_env_args + configure_flags

    configure_env = os.environ.copy()
    target_extra_path = env.get('_%s-%s_PATH' % (product, target), '')
    if target_extra_path:
        configure_env['PATH'] += ':' + target_extra_path

    run_command(configure, args=configure_args, cwd=build_dir, env=configure_env, name='configure')
