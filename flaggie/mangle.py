# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import fnmatch
import logging
import typing

from flaggie.config import ConfigFile, ConfigLine


def match_packages(config_files: list[ConfigFile],
                   package: str,
                   exact_match: bool,
                   ) -> typing.Generator[tuple[ConfigFile, int, ConfigLine],
                                         None, None]:
    """
    Yield matching packages from config files, latest first

    Iterate over all config file lines, in reverse order and match them
    against specified package.  If exact_match is True, the package name
    must match exactly.  Otherwise, wildcard matching (against wildcards
    in config file) is used.

    Yields a tuple of (config file object, line number, config line object).
    """

    for config_file in reversed(config_files):
        for rev_no, line in enumerate(reversed(config_file.parsed_lines)):
            if line.package is None:
                continue

            if exact_match:
                if line.package == package:
                    continue
            elif not fnmatch.fnmatch(package, line.package):
                continue

            # 1-based
            line_no = len(config_file.parsed_lines) - rev_no
            yield (config_file, line_no, line)


def mangle_flag(config_files: list[ConfigFile],
                package: str,
                prefix: typing.Optional[str],
                name: str,
                new_state: bool,
                ) -> None:
    pkg_is_wildcard = "*" in package

    # TODO
    assert prefix is None, "not implemented yet"

    def try_inplace() -> bool:
        for config_file, line_no, line in match_packages(config_files, package,
                                                         pkg_is_wildcard):
            # TODO
            assert not line.grouped_flags, "not implemented yet"

            for index, line_flag in enumerate(line.flat_flags):
                line_flag = line_flag.lstrip("-")
                # FIXME: package files only support '*' after '_'
                # (or in group)
                if fnmatch.fnmatch(name, line_flag):
                    debug_common = (
                        f"Match found: {config_file.path}:{line_no} "
                        f"{line.package} {line.flat_flags[index]}")
                    # if this was an exact match, we can mangle it in place
                    if line.package == package and line_flag == name:
                        logging.debug(f"{debug_common}, updating in place")
                        line.flat_flags[index] = (
                            name if new_state else f"-{name}")
                        # 0-based
                        config_file.modified_lines.add(line_no - 1)
                        return True
                    logging.debug(
                        f"{debug_common}, cannot update in place")
                    # otherwise, we can't update in-place -- we need to add
                    # after this wildcard
                    return False
        return False

    if try_inplace():
        return

    assert False, "not implemented yet"
