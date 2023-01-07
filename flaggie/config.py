# (c) 2022-2023 Michał Górny
# Released under the terms of the MIT license

import enum
import os
import re
import typing

from pathlib import Path


class TokenType(enum.IntEnum):
    USE_FLAG = enum.auto()
    KEYWORD = enum.auto()
    LICENSE = enum.auto()
    PROPERTY = enum.auto()
    RESTRICT = enum.auto()
    ENV_FILE = enum.auto()


class ConfigLine(typing.NamedTuple):
    package: typing.Optional[str] = None
    flat_flags: list[str] = []
    grouped_flags: list[tuple[str, list[str]]] = []
    comment: typing.Optional[str] = None


class ConfigFile(typing.NamedTuple):
    path: Path
    raw_lines: list[str]
    parsed_lines: list[ConfigLine]


CONFIG_FILENAMES = {
    TokenType.USE_FLAG: "package.use",
    TokenType.KEYWORD: "package.accept_keywords",
    TokenType.LICENSE: "package.license",
    TokenType.PROPERTY: "package.properties",
    TokenType.RESTRICT: "package.accept_restrict",
    TokenType.ENV_FILE: "package.env",
}

COMMENT_RE = re.compile(r"(?<!\S)#(.*)$")


def find_config_files(config_root: Path, token_type: TokenType) -> list[Path]:
    """
    Find all configuration files of given type

    Find all configuration files of type `token_type` inside root
    `config_root` (usually "/").  Returns a list of paths sorted in the same
    order as they are read by Portage.
    """

    path = config_root / "etc/portage" / CONFIG_FILENAMES[token_type]

    # if it's an existing directory, find the last visible file
    # in the directory (provided there is any)
    if path.is_dir():
        def _is_visible(fn: str) -> bool:
            return not fn.startswith(".") and not fn.endswith("~")

        # yes, Portage is insane
        def _get_all_paths_recursively(topdir: Path
                                       ) -> typing.Generator[Path, None, None]:
            for curpath, dirnames, filenames in os.walk(path):
                dirnames = list(filter(_is_visible, dirnames))
                for f in filter(_is_visible, filenames):
                    yield Path(curpath) / f

        all_files = sorted(_get_all_paths_recursively(path))
        if all_files:
            return all_files
        path /= "99local.conf"
        path.touch()
        return [path]

    # if it does not exist yet, create a new directory and put a `local.conf`
    # in there
    if not path.exists():
        path.mkdir(parents=True)
        path /= "99local.conf"
        path.touch()
        return [path]

    # otherwise (presumably it's a file), use the path directly
    return [path]


def parse_config_file(lines: list[str]
                      ) -> typing.Generator[ConfigLine, None, None]:
    """
    Parse config file data

    Parse the config file data supplied as list of lines into a list
    of corresponding ConfigLine objects.
    """

    for line in lines:
        line = line.rstrip()
        comment_m = COMMENT_RE.search(line)
        if comment_m is not None:
            line = line[:comment_m.start()]

        split = line.split()
        group: tuple[str, list[str]] = ("", [])
        groups = [group]
        for flag in split[1:]:
            if flag.endswith(":"):
                group = (flag[:-1], [])
                groups.append(group)
                continue
            group[1].append(flag)

        assert groups[0][0] == ""
        yield ConfigLine(
            package=split[0] if split else None,
            flat_flags=groups[0][1],
            grouped_flags=groups[1:],
            comment=comment_m.group(1) if comment_m is not None else None)


def dump_config_line(line: ConfigLine) -> str:
    """
    Convert ConfigLine back into str
    """

    def inner() -> typing.Generator[str, None, None]:
        if line.package is not None:
            yield line.package
        yield from line.flat_flags
        for group, flags in line.grouped_flags:
            yield f"{group}:"
            yield from flags
        if line.comment is not None:
            yield f"#{line.comment}"

    return " ".join(inner()) + "\n"


def read_config_files(paths: list[Path]
                      ) -> typing.Generator[ConfigFile, None, None]:
    """
    Read and parse data from config files passed in.
    """

    for path in paths:
        with open(path, "r") as f:
            raw_lines = f.readlines()
        yield ConfigFile(path, raw_lines, list(parse_config_file(raw_lines)))