# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import logging
import typing

from pathlib import Path

from flaggie.config import TokenType
from flaggie.mangle import is_wildcard_package


if typing.TYPE_CHECKING:
    import gentoopm


def match_package(pm: typing.Optional["gentoopm.basepm.PMBase"],
                  package_spec: str,
                  ) -> str:
    """
    Match package spec against the repos

    Match the package specification against the repositories provided
    by the package manager instance.  Returns the (possibly expanded)
    package specification or raises an exception.
    """

    if pm is None or is_wildcard_package(package_spec):
        # if PM is not available or we're dealing with wildcards,
        # just perform basic validation
        # TODO: better validation?
        if package_spec.count("/") != 1:
            raise ValueError("Not a valid category/package spec")
        return package_spec

    parsed = pm.Atom(package_spec)
    match = pm.stack.select(parsed)
    if parsed.key.category is None:
        # if user did not specify the category, copy it from the match
        # TODO: have gentoopm provide a better API for modifying atoms?
        return package_spec.replace(str(parsed.key.package),
                                    str(match.key))

    return package_spec


def get_valid_values(pm: "gentoopm.basepm.PMBase",
                     package_spec: str,
                     token_type: TokenType,
                     group: typing.Optional[str],
                     ) -> typing.Optional[set[str]]:
    """Get a list of valid values for (package, token type, group)"""

    # env files are global by design
    if token_type == TokenType.ENV_FILE:
        env_dir = Path(pm.config_root or "/") / "etc/portage/env"
        if not env_dir.is_dir():
            logging.debug(f"{env_dir} is not a directory, no valid "
                          f"{token_type.name} values")
            return None
        values = set(path.name for path in env_dir.iterdir() if path.is_file())
        logging.debug(f"Valid values for {token_type.name}: {values}")
        return values

    # TODO: support global values
    if package_spec == "*/*":
        return None

    # wildcard packages not supported
    if is_wildcard_package(package_spec):
        return None

    group_match = ""
    group_len = 0
    if group is not None:
        group_match = group.lower() + "_"
        group_len = len(group_match)

    values = set()
    values.add("**" if token_type == TokenType.KEYWORD else "*")
    if token_type == TokenType.LICENSE:
        # TODO: add license groups
        pass

    for pkg in pm.stack.filter(package_spec):
        if token_type == TokenType.USE_FLAG:
            for flag in pkg.use:
                if flag.lower().startswith(group_match):
                    values.add(flag[group_len:])
        elif token_type == TokenType.KEYWORD:
            for keyword in pkg.keywords:
                if keyword.startswith("-"):
                    continue
                values.add("~*" if keyword.startswith("~") else "*")
                values.add(keyword)
        elif token_type == TokenType.LICENSE:
            # TODO: implement in gentoopm
            return None
        elif token_type == TokenType.PROPERTY:
            # TODO: implement in gentoopm
            return None
        elif token_type == TokenType.RESTRICT:
            # TODO: implement in gentoopm
            return None

    logging.debug(
        f"Valid values for {package_spec} {token_type.name} group: {group}: "
        f"{values}")
    return values
