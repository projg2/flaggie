# (c) 2022 Michał Górny
# Released under the terms of the MIT license

import enum
import os
import typing

from pathlib import Path


class TokenType(enum.IntEnum):
    USE_FLAG = enum.auto()


CONFIG_FILENAMES = {
    TokenType.USE_FLAG: "package.use",
}


def find_config_files(config_root: Path, token_type: TokenType) -> list[Path]:
    """
    Find all configuration files of given type and return a list of paths
    sorted in the same order as they are read by Portage.
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
        return [path / "99local.conf"]

    # if it does not exist yet, create a new directory and put a `local.conf`
    # in there
    if not path.exists():
        path.mkdir(parents=True)
        return [path / "99local.conf"]

    # otherwise (presumably it's a file), use the path directly
    return [path]
