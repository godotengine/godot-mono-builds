#!/usr/bin/python

from desktop import run_main


if __name__ == '__main__':
    from sys import argv
    run_main(argv[1:], target_platform='linux')
