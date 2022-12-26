# (c) 2022 Michał Górny
# Released under the terms of the MIT license

import argparse
import logging
import os.path
import sys


def main(prog_name: str, *argv: str) -> int:
    argp = argparse.ArgumentParser(prog=os.path.basename(prog_name))
    args = argp.parse_args(argv)
    return 0


def entry_point() -> None:
    try:
        from rich.logging import RichHandler
    except ImportError:
        logging.basicConfig(
            format="[{levelname:>7}] {message}",
            level=logging.INFO,
            style="{")
    else:
        logging.basicConfig(
            format="{message}",
            level=logging.INFO,
            style="{",
            handlers=[RichHandler(show_time=False, show_path=False)])

    sys.exit(main(*sys.argv))


if __name__ == "__main__":
    entry_point()
