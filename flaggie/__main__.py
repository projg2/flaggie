# (c) 2022 Michał Górny
# Released under the terms of the MIT license

import argparse
import logging
import os.path
import sys

from pathlib import Path

from flaggie.config import (TokenType, find_config_files, read_config_files,
                            save_config_files,
                            )


def main(prog_name: str, *argv: str) -> int:
    argp = argparse.ArgumentParser(prog=os.path.basename(prog_name))
    argp.add_argument("--config-root",
                      type=Path,
                      default=Path("/"),
                      help="Root directory relative to which configuration "
                           "files will be processed (default: /)")
    argp.add_argument("--debug",
                      action="store_true",
                      help="Enable debug output")
    args = argp.parse_args(argv)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    portage_dir = args.config_root / "etc/portage"
    if not portage_dir.is_dir():
        argp.error(
            f"{portage_dir} does not exist, did you specify correct "
            "--config-root?")

    all_configs = {
        k: list(read_config_files(find_config_files(args.config_root, k)))
        for k in TokenType}

    for config_files in all_configs.values():
        save_config_files(config_files)

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
