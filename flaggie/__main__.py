# (c) 2022 Michał Górny
# Released under the terms of the MIT license

import argparse
import logging
import os.path
import sys

from pathlib import Path

from flaggie.config import TokenType, find_config_files, read_config_files


def main(prog_name: str, *argv: str) -> int:
    argp = argparse.ArgumentParser(prog=os.path.basename(prog_name))
    argp.add_argument("--debug",
                      action="store_true",
                      help="Enable debug output")
    args = argp.parse_args(argv)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    config_root = Path("/")  # TODO
    all_configs = {
        k: list(read_config_files(find_config_files(config_root, k)))
        for k in TokenType}

    # silence pyflakes
    _ = all_configs

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
