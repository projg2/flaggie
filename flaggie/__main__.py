# (c) 2022-2023 Michał Górny
# Released under the terms of the MIT license

import argparse
import logging
import os.path
import shutil
import sys
import textwrap
import typing

from functools import partial
from pathlib import Path

from flaggie.config import (TokenType, find_config_files, read_config_files,
                            save_config_files,
                            )


def split_arg_sets(argp: argparse.ArgumentParser, args: list[str]
                   ) -> typing.Generator[tuple[list[str], list[str]],
                                         None, None]:
    """Split arguments into tuples of (packages, actions)"""

    packages: list[str] = []
    ops: list[str] = []
    for arg in args:
        if not arg:
            argp.error("Empty string in requests")
        if arg[0].isidentifier():
            if ops:
                yield (packages, ops)
                packages = []
                ops = []
            packages.append(arg)
        else:
            ops.append(arg)
    if not ops:
        argp.error(
            f"Packages ({' '.join(packages)}) with no operations specified "
            "in requests")
    yield (packages, ops)


def split_op(op: str,
             ) -> tuple[str, typing.Optional[str], typing.Optional[str]]:
    """Split operation argument into (operation, namespace, flag)"""

    operator = op[0]
    split = op[1:].split("::", 1)
    ns = split[0] if len(split) == 2 else None
    flag = split[-1] or None
    return (operator, ns, flag)


NAMESPACE_MAP = {
    "use": TokenType.USE_FLAG,
    "kw": TokenType.KEYWORD,
    "lic": TokenType.LICENSE,
    "prop": TokenType.PROPERTY,
    "restrict": TokenType.RESTRICT,
    "env": TokenType.ENV_FILE,
}


def namespace_into_token_group(ns: str) -> tuple[TokenType,
                                                 typing.Optional[str]]:
    """Map namespace into a tuple of (token type, group name)"""

    token_type = NAMESPACE_MAP.get(ns)
    if token_type is not None:
        return (token_type, None)
    return (TokenType.USE_FLAG, ns)


REQUEST_HELP = """
Every request consists of zero or more packages, followed by one or more \
flag changes, i.e.:

  request = [package ...] op [op ...]

Packages can be specified in any form suitable for package.* files. \
If category is omitted, a package lookup is attempted. If no packages \
are specified, "*/*" is assumed.

The operations supported are:

  +[ns::]flag         Enable specified flag
  -[ns::]flag         Disable specified flag

Every flag can be prefixed using namespace, followed by "::".  The namespace \
can either be a USE_EXPAND name or one of the special values:

  auto::              (the default) recognize type
  env::               package.env entries
  kw::                package.accept_keywords entries
  lic::               package.license entries
  prop::              package.properties entries
  restrict::          package.accept_restrict entries
  use::               package.use entries
"""


def main(prog_name: str, *argv: str) -> int:
    # same as argparse default, enforce for consistency
    help_width = shutil.get_terminal_size().columns - 2

    # FIXME: handle "-"-arguments cleanly without "--"
    argp = argparse.ArgumentParser(
        prog=os.path.basename(prog_name),
        epilog="\n".join(textwrap.fill(x,
                                       width=help_width,
                                       drop_whitespace=False,
                                       replace_whitespace=False)
                         for x in REQUEST_HELP.splitlines()),
        formatter_class=partial(argparse.RawDescriptionHelpFormatter,
                                width=help_width),
        )
    argp.add_argument("--config-root",
                      type=Path,
                      default=Path("/"),
                      help="Root directory relative to which configuration "
                           "files will be processed (default: /)")
    argp.add_argument("--debug",
                      action="store_true",
                      help="Enable debug output")
    argp.add_argument("--pretend",
                      action="store_true",
                      help="Do not write any changes to the original files")
    argp.add_argument("request",
                      nargs="+",
                      help="Requested operations (see description)")
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

    for packages, ops in split_arg_sets(argp, args.request):
        if not packages:
            packages.append("*/*")
        logging.debug(f"Request: packages = {packages}, ops = {ops}")
        for op in ops:
            operator, ns, flag = split_op(op)
            logging.debug(f"Operation: {operator}, ns: {ns}, flag: {flag}")
            if ns in (None, "auto"):
                # FIXME
                argp.error(
                    f"{op}: Flag type guessing is not supported yet")
            # FIXME: workaround for mypy, may become unnecessary once auto
            # is implemented
            assert ns is not None
            token_type, group = namespace_into_token_group(ns)
            logging.debug(
                f"Namespace mapped into {token_type.name}, group: {group}")

    for config_files in all_configs.values():
        save_config_files(config_files, write=not args.pretend)

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
