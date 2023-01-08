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
            # FIXME: fnmatch() is more permissive than package.* files
            elif not fnmatch.fnmatch(package, line.package):
                continue

            # 1-based
            line_no = len(config_file.parsed_lines) - rev_no
            yield (config_file, line_no, line)


def match_flags(line: ConfigLine,
                full_name: str,
                ) -> typing.Generator[tuple[typing.Optional[str], list[str],
                                            int], None, None]:
    """
    Yield matching flags from specified config line

    Iterate over flags on the config line, in reverse order and match them
    against specified full_name ([<prefix>_]<name>).

    Yields a tuple of (matched group name, list instance, list index).
    """

    for rev_index, line_flag in enumerate(reversed(line.flat_flags)):
        line_flag = line_flag.lstrip("-")
        # FIXME: package files only support '*' after '_'
        # (or in group)
        if fnmatch.fnmatch(full_name, line_flag):
            # 0-based
            index = len(line.flat_flags) - rev_index - 1
            yield (None, line.flat_flags, index)

    for group, flags in reversed(line.grouped_flags):
        group_lc = group.lower()
        for rev_index, group_flag in enumerate(reversed(flags)):
            group_flag = f"{group_lc}_{group_flag.lstrip('-')}"
            # FIXME: package files only support '*' after '_'
            # (or in group)
            if fnmatch.fnmatch(full_name, group_flag):
                # 0-based
                index = len(flags) - rev_index - 1
                yield (group_lc, flags, index)


def mangle_flag(config_files: list[ConfigFile],
                package: str,
                prefix: typing.Optional[str],
                name: str,
                new_state: bool,
                ) -> None:
    pkg_is_wildcard = "*" in package
    full_name = name if prefix is None else f"{prefix.lower()}_{name}"
    new_state_sym = "" if new_state else "-"

    def try_inplace() -> bool:
        for config_file, line_no, line in match_packages(config_files, package,
                                                         pkg_is_wildcard):
            for group_prefix, flag_list, index in match_flags(line, full_name):
                debug_common = (
                    f"Match found: {config_file.path}:{line_no} "
                    f"{line.package} group: {group_prefix} {flag_list[index]}")
                # if this was an exact match, we can mangle it in place
                matched_name = flag_list[index].lstrip("-")
                matched_flag = (matched_name if group_prefix is None
                                else f"{group_prefix}_{matched_name}")
                if line.package == package and matched_flag == full_name:
                    logging.debug(f"{debug_common}, updating in place")
                    flag_list[index] = new_state_sym + matched_name
                    # 0-based
                    config_file.modified_lines.add(line_no - 1)
                    return True
                logging.debug(f"{debug_common}, cannot update in place")
                # otherwise, we can't update in-place -- we need to add
                # after this wildcard
                return False
        return False

    def try_appending() -> bool:
        assert prefix is None, "TODO"
        for config_file, line_no, line in match_packages(config_files, package,
                                                         pkg_is_wildcard):
            # require an exact package match, we don't want to update some
            # wildcard entry
            if line.package != package:
                return False

            # if the line contains grouped flags, we need to create a new one
            if line.grouped_flags:
                return False

            line.flat_flags.append(new_state_sym + full_name)
            config_file.modified_lines.add(line_no - 1)
            return True
        return False

    def try_new_entry() -> bool:
        assert False, "not implemented yet"

    try_inplace() or try_appending() or try_new_entry()
