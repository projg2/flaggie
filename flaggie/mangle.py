# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import functools
import logging
import re
import typing

from flaggie.config import ConfigFile, ConfigLine


@functools.cache
def package_pattern_to_re(pattern: str) -> re.Pattern[str]:
    """Compile regular expression from wildcard package pattern"""
    re_str = ".*".join(re.escape(x) for x in pattern.split("*"))
    return re.compile(re_str)


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
                if line.package != package:
                    continue
            elif package_pattern_to_re(line.package).match(package) is None:
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

    # FIXME: package files only support '*' after '_' (or in group)
    full_name_re = package_pattern_to_re(full_name)

    for group, flags in reversed(line.grouped_flags):
        group_lc = group.lower()
        for rev_index, group_flag in enumerate(reversed(flags)):
            group_flag = f"{group_lc}_{group_flag.lstrip('-')}"
            # FIXME: as above
            match = (
                package_pattern_to_re(group_flag).match(full_name) is not None)
            if match or full_name_re.match(group_flag) is not None:
                # 0-based
                index = len(flags) - rev_index - 1
                yield (group_lc, flags, index)

    for rev_index, line_flag in enumerate(reversed(line.flat_flags)):
        line_flag = line_flag.lstrip("-")
        # FIXME: as above
        match = (
            package_pattern_to_re(line_flag).match(full_name) is not None)
        if match or full_name_re.match(line_flag) is not None:
            # 0-based
            index = len(line.flat_flags) - rev_index - 1
            yield (None, line.flat_flags, index)


class WildcardEntryError(Exception):
    """Exception raised when trying to add a new wildcard entry"""

    def __init__(self) -> None:
        super().__init__(
            "Adding wildcard entries other than */* is not supported")


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
                    line.invalidate()
                    config_file.modified = True
                    return True
                logging.debug(
                    f"{debug_common}, non-exact match, cannot update in place")
                # otherwise, we can't update in-place -- we need to add
                # after this wildcard
                return False
        return False

    def try_appending() -> bool:
        for config_file, line_no, line in match_packages(config_files, package,
                                                         pkg_is_wildcard):
            debug_common = (
                f"Package entry found: {config_file.path}:{line_no} "
                f"{line.package}")

            # require an exact package match, we don't want to update some
            # wildcard entry
            if line.package != package:
                logging.debug(
                    f"{debug_common}, non-exact match, cannot append")
                return False

            if prefix is None:
                # if the line contains grouped flags, we need to create
                # a new line for the flat flag
                if line.grouped_flags:
                    logging.debug(
                        f"{debug_common}, ends with flag group, looking "
                        "further")
                    continue
                line.flat_flags.append(new_state_sym + full_name)
                logging.debug(
                    f"{debug_common}, appending {new_state_sym}{full_name}")
            else:
                for group, flags in line.grouped_flags:
                    if group.lower() == prefix.lower():
                        flags.append(new_state_sym + name)
                        logging.debug(
                            f"{debug_common}, group {group}, appending "
                            f"{new_state_sym}{full_name}")
                        break
                else:
                    logging.debug(
                        f"{debug_common}, prefix unmatched, looking further")
                    continue

            line.invalidate()
            config_file.modified = True
            return True
        return False

    def try_new_entry_after(new_line: ConfigLine) -> bool:
        for config_file, line_no, line in match_packages(config_files, package,
                                                         pkg_is_wildcard):
            debug_common = (
                f"Package entry found: {config_file.path}:{line_no} "
                f"{line.package}")

            # again, let's not append after wildcards
            if line.package != package:
                logging.debug(
                    f"{debug_common}, non-exact match, not appending here")
                return False

            logging.debug(
                f"Inserting new entry to {config_file.path}, "
                f"after line {line_no}: {new_line}")
            config_file.parsed_lines.insert(line_no, new_line)
            config_file.modified = True
            return True
        return False

    def try_new_entry(new_line: ConfigLine) -> bool:
        assert new_line.package is not None
        if new_line.package == "*/*":
            config_file = config_files[0]
            logging.debug(
                f"Prepending new entry to {config_file.path}: {new_line}")
            config_file.parsed_lines.insert(0, new_line)
        elif "*" in new_line.package:
            raise WildcardEntryError()
        else:
            config_file = config_files[-1]
            logging.debug(
                f"Appending new entry to {config_file.path}: {new_line}")
            config_file.parsed_lines.append(new_line)
        config_file.modified = True
        return True

    if try_inplace() or try_appending():
        return

    new_flag = new_state_sym + name
    if prefix is None:
        new_line = ConfigLine(package, [new_flag], [])
    else:
        new_line = ConfigLine(package, [], [(prefix.upper(), [new_flag])])

    try_new_entry_after(new_line) or try_new_entry(new_line)
