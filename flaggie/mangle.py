# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import fnmatch
import logging
import typing

from flaggie.config import ConfigFile


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
        for config_file in reversed(config_files):
            for line_no, line in enumerate(reversed(config_file.parsed_lines)):
                if line.package is None:
                    continue

                if pkg_is_wildcard:
                    # if we are mangling a wildcard, require exact match --
                    # we want to modify exactly the wildcard requested
                    # by the user
                    if line.package != package:
                        continue
                else:
                    # otherwise, allow a wildcard entry to match
                    # FIXME: fnmatch() is more permissive than package.* files
                    if not fnmatch.fnmatch(package, line.package):
                        continue

                # TODO
                assert not line.grouped_flags, "not implemented yet"

                for index, line_flag in enumerate(line.flat_flags):
                    line_flag = line_flag.lstrip("-")
                    # FIXME: package files only support '*' after '_'
                    # (or in group)
                    if fnmatch.fnmatch(name, line_flag):
                        debug_common = (
                            f"Match found: {config_file.path}, "
                            f"line {len(config_file.parsed_lines) - line_no}, "
                            f"{line.package} {line.flat_flags[index]}")
                        # if this was an exact match, we can mangle it in place
                        if line.package == package and line_flag == name:
                            logging.debug(f"{debug_common}, updating in place")
                            line.flat_flags[index] = (
                                name if new_state else f"-{name}")
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