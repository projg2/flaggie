# (c) 2022-2023 Michał Górny
# Released under the terms of the MIT license

import argparse
import functools
import logging
import os.path
import shlex
import shutil
import subprocess
import sys
import textwrap
import typing

from functools import partial
from pathlib import Path

from flaggie import __version__
from flaggie.config import (TokenType, find_config_files, read_config_files,
                            save_config_files, ConfigFile,
                            )
from flaggie.mangle import mangle_flag, remove_flag
from flaggie.pm import (match_package, get_valid_values, split_use_expand,
                        MatchError,
                        )

if typing.TYPE_CHECKING:
    import gentoopm


class Operation(typing.NamedTuple):
    function: typing.Callable[[list[ConfigFile],  # config_files
                               str,  # package
                               typing.Optional[str],  # prefix
                               typing.Optional[str],  # flag
                               ], None]
    flag_required: bool
    verify_flag: bool
    match_multiple_ns: bool


OPERATOR_MAP = {
    "+": Operation(function=functools.partial(mangle_flag, new_state=True),
                   flag_required=True,
                   verify_flag=True,
                   match_multiple_ns=False,
                   ),
    "-": Operation(function=functools.partial(mangle_flag, new_state=False),
                   flag_required=True,
                   verify_flag=True,
                   match_multiple_ns=False,
                   ),
    "%": Operation(function=remove_flag,
                   flag_required=False,
                   verify_flag=False,
                   match_multiple_ns=True,
                   ),
}


def split_arg_sets(argp: argparse.ArgumentParser, args: list[str]
                   ) -> typing.Generator[tuple[list[str], list[str]],
                                         None, None]:
    """Split arguments into tuples of (packages, actions)"""

    packages: list[str] = []
    ops: list[str] = []
    for arg in args:
        if not arg:
            argp.error("Empty string in requests")
        if arg[0] in OPERATOR_MAP:
            ops.append(arg)
            continue
        if ops:
            yield (packages, ops)
            packages = []
            ops = []
        packages.append(arg)
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
  %[ns::][flag]       Removed specified flag (or all flags)

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


def guess_token_type(argp: argparse.ArgumentParser,
                     pm: typing.Optional["gentoopm.BasePM"],
                     op: str,
                     flag: str,
                     packages: list[str],
                     ) -> str:
    if pm is None:
        argp.error(
            f"{op}: Flag type guessing requires package manager, "
            f"pass e.g. use::{flag} to specify type")

    def get_matching_types() -> typing.Generator[tuple[str, TokenType],
                                                 None, None]:
        for package in packages:
            for ns, token_type in NAMESPACE_MAP.items():
                values = get_valid_values(pm, package, token_type, None)
                if values is None:
                    argp.error(f"{op}: Flag type guessing not supported "
                               f"for {package}")
                if flag in values:
                    yield (ns, token_type)

    matched_types = set(get_matching_types())
    if not matched_types:
        argp.error(f"{op}: Argument not recognized as any type, pass "
                   f"e.g. use::{flag} to force one (for packages: "
                   f"{packages})")
    elif len(matched_types) > 1:
        names = sorted(x[0] for x in matched_types)
        argp.error(f"{op}: Argument matches multiple token types: "
                   f"{', '.join(names)}; pass e.g. {names[0]}::{flag} to "
                   f"disambiguate (for packages: {packages})")
    return next(iter(matched_types))[0]


def main(prog_name: str, *argv: str) -> int:
    # same as argparse default, enforce for consistency
    help_width = shutil.get_terminal_size().columns - 2
    if help_width > 10:
        epilog = "\n".join(textwrap.fill(x,
                                         width=help_width,
                                         drop_whitespace=False,
                                         replace_whitespace=False)
                           for x in REQUEST_HELP.splitlines())
    else:
        epilog = REQUEST_HELP

    if shutil.which("git"):
        diff_default = "git --no-pager diff --no-index --word-diff --"
    else:
        diff_default = "diff -d -u --"

    argp = argparse.ArgumentParser(
        add_help=False,
        prog=os.path.basename(prog_name),
        usage="%(prog)s [options] request ...",
        epilog=epilog,
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
    argp.add_argument("--diff",
                      default=diff_default,
                      help="Program used to diff configs "
                           f"(default: {diff_default})")
    argp.add_argument("--force",
                      action="store_true",
                      help="Force performing the action even if arguments "
                           "are invalid")
    argp.add_argument("--help",
                      action="help",
                      help="Print help text and exit")
    argp.add_argument("--no-diff",
                      action="store_const",
                      const=None,
                      dest="diff",
                      help="Do not diff configs")
    argp.add_argument("--no-package-manager",
                      action="store_true",
                      help="Disable package manager interaction and features "
                           "requiring it (category and argument type "
                           "guessing, validation)")
    argp.add_argument("--pretend",
                      action="store_true",
                      help="Do not write any changes to the original files")
    argp.add_argument("--version",
                      action="version",
                      help="Print program version and exit",
                      version=f"flaggie {__version__}")
    args, request = argp.parse_known_args(argv)

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    if not request:
        argp.error("No request specified")

    pm = None
    if not args.no_package_manager:
        try:
            import gentoopm
            pm = gentoopm.get_package_manager()
        except Exception:
            logging.warning(
                "Package manager API init failed. You can disable package "
                "manager integration using --no-package-manager, at the cost "
                "of losing category and argument type guessing and validation")
            raise

    portage_dir = args.config_root / "etc/portage"
    if not portage_dir.is_dir():
        argp.error(
            f"{portage_dir} does not exist, did you specify correct "
            "--config-root?")

    all_configs = {
        k: list(read_config_files(find_config_files(args.config_root, k)))
        for k in TokenType}

    for packages, ops in split_arg_sets(argp, request):
        if not packages:
            packages.append("*/*")
        logging.debug(f"Request: packages = {packages}, ops = {ops}")

        def expand_package(pkg: str) -> str:
            try:
                return match_package(pm, pkg)
            except MatchError as err:
                if not args.force:
                    argp.error(str(err))
                else:
                    logging.warning(str(err))
                return pkg

        packages = list(map(expand_package, packages))

        for op in ops:
            operator, arg_ns, flag = split_op(op)
            logging.debug(f"Operation: {operator}, ns: {arg_ns}, flag: {flag}")

            try:
                operation = OPERATOR_MAP[operator]
            except KeyError:
                argp.error(f"{op}: incorrect operation")

            if operation.flag_required and not flag:
                argp.error(f"{op}: flag name required")

            if arg_ns is None or arg_ns == "auto":
                if operation.match_multiple_ns:
                    namespaces = list(NAMESPACE_MAP)
                else:
                    assert flag is not None
                    namespaces = [
                        guess_token_type(argp, pm, op, flag, packages)
                    ]
            else:
                namespaces = [arg_ns]

            for ns in namespaces:
                token_type, group = namespace_into_token_group(ns)
                logging.debug(
                    f"Namespace mapped into {token_type.name}, group: {group}")

                config_file = all_configs[token_type]
                if token_type == TokenType.USE_FLAG and (group is None and
                                                         flag is not None):
                    group, flag = split_use_expand(pm, flag)
                    if group is not None:
                        logging.debug(f"Flag remapped into {group}: {flag}")

                for package in packages:
                    if flag is not None and operation.verify_flag:
                        valid_values = get_valid_values(pm, package,
                                                        token_type, group)
                        if valid_values is None:
                            pass
                        elif flag not in valid_values:
                            if not args.force:
                                argp.error(
                                    f"{op}: argument incorrect for {package}")
                            else:
                                logging.warning(
                                    f"{op}: argument incorrect for {package}")

                    operation.function(config_file, package, group, flag)

    diff_prog = shlex.split(args.diff) if args.diff is not None else None

    def confirm_cb(orig_file: Path, temp_file: Path) -> bool:
        if diff_prog is not None:
            subprocess.run(diff_prog + [str(orig_file), str(temp_file)])
        return not args.pretend

    for config_files in all_configs.values():
        save_config_files(config_files, confirm_cb=confirm_cb)

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
