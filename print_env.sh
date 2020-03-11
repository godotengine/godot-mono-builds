#!/bin/bash

# This is used in python to get the export environment variables from bash's 'source' command.

# The 'env' command option '-0' separates the 'name=value' results by 'null' instead of line breaks.
# This is required to parse the output because a variable value can contain line breaks as well.
# Unfortunately, the '-0' option is not supported on some platforms like macOS,
# hence why we need this script to print the environment variables instead.

unset IFS
for var in $(compgen -e); do
    printf "$var=${!var}\0"
done
