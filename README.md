# Mono build scripts for Godot
This repository contains scripts for building the Mono runtime to use with Godot Engine

## Android instructions

Run `python build_mono_android.py --help` for the full list of command line options.
You may need to tweak some of those if the default values do not fit your needs.

Example:

```bash
# These are the default values. You can omit them if they apply to your system
export ANDROID_SDK_ROOT=$HOME/Android/Sdk
export ANDROID_NDK_ROOT=$ANDROID_SDK_ROOT/ndk-bundle

# The mono sources may be in a different location on your system
export MONO_SOURCE_ROOT=$HOME/git/mono

./build_mono_android.py configure --target=all
./build_mono_android.py make --target=all
```

The option `--target=all` is a shortcut for `--target=armeabi-v7a --target=x86 --target=arm64-v8a --target=x86_64`.

By default, the script will install the resulting files to `$HOME/mono-installs`.
You can specify a custom output directory with the `--install-dir` option.
