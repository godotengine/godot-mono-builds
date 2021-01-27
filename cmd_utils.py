

def custom_bool(val):
        if isinstance(val, bool):
            return val
        if val.lower() in ('yes', 'true', 't', 'y', '1'):
            return True
        elif val.lower() in ('no', 'false', 'f', 'n', '0'):
            return False
        else:
            from argparse import ArgumentTypeError
            raise ArgumentTypeError('Boolean value expected.')


def build_arg_parser(description, env_vars={}):
    from argparse import ArgumentParser, RawDescriptionHelpFormatter
    from textwrap import dedent

    base_env_vars = {
        'MONO_SOURCE_ROOT': 'Overrides default value for --mono-sources',
    }

    env_vars_text = '\n'.join(['    %s: %s' % (var, desc) for var, desc in env_vars.items()])
    base_env_vars_text = '\n'.join(['    %s: %s' % (var, desc) for var, desc in base_env_vars.items()])

    epilog=dedent('''\
environment variables:
%s
%s
''' % (env_vars_text, base_env_vars_text))

    return ArgumentParser(
        description=description,
        formatter_class=RawDescriptionHelpFormatter,
        epilog=epilog
    )


def add_base_arguments(parser, default_help):
    import os
    from os.path import join as path_join

    home = os.environ.get('HOME')
    mono_sources_default = os.environ.get('MONO_SOURCE_ROOT', '')

    parser.add_argument('--verbose-make', action='store_true', default=False, help=default_help)
    # --jobs supports not passing an argument, in which case the 'const' is used,
    # which is the number of CPU cores on the host system.
    parser.add_argument('--jobs', '-j', nargs='?', const=str(os.cpu_count()), default='1', help=default_help)
    parser.add_argument('--configure-dir', default=path_join(home, 'mono-configs'), help=default_help)
    parser.add_argument('--install-dir', default=path_join(home, 'mono-installs'), help=default_help)

    if mono_sources_default:
        parser.add_argument('--mono-sources', default=mono_sources_default, help=default_help)
    else:
        parser.add_argument('--mono-sources', required=True)

    parser.add_argument('--mxe-prefix', default='/usr', help=default_help)


def add_runtime_arguments(parser, default_help):
    add_base_arguments(parser, default_help)

    parser.add_argument('--configuration', choices=['release', 'debug'], default='release', help=default_help)
    parser.add_argument('--enable-cxx', action='store_true', default=False, help=default_help)
    parser.add_argument('--strip-libs', type=custom_bool, default=True, help='Strip the libraries if possible after running make.\n' + default_help)
    parser.add_argument('--is-sim', type=custom_bool, default=False, help='Use iOS simulator SDK.\n'+ default_help)


def expand_input_targets(input_targets, target_shortcuts=[]):
    targets = []

    for shortcut in target_shortcuts.keys():
        if shortcut in input_targets:
            targets += target_shortcuts[shortcut][:]

    # The shortcuts options ('all-*') have already been handled. Remove them this way as there may be duplicates.
    input_targets = [t for t in input_targets if not t in target_shortcuts]

    for target in input_targets:
        if not target in targets:
            targets += [target]

    return targets
