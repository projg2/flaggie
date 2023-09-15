# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import functools
import logging
import typing

from pathlib import Path

import more_itertools

from flaggie.config import TokenType
from flaggie.mangle import is_wildcard_package


if typing.TYPE_CHECKING:
    import gentoopm


class MatchError(RuntimeError):
    pass


@functools.cache
def _filter_packages(pm: "gentoopm.basepm.PMBase",
                     query: str,
                     ) -> list["gentoopm.basepm.pkg.PMPackage"]:
    return pm.stack.filter(query)


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
    matched = frozenset(str(pkg.key)
                        for pkg in _filter_packages(pm, package_spec))
    if not matched:
        raise MatchError(f"{package_spec!r} matched no packages")
    if len(matched) > 1:
        raise MatchError(
            f"{package_spec!r} is ambigous, matched {', '.join(matched)}")

    if parsed.key.category is None:
        # if user did not specify the category, copy it from the match
        # TODO: have gentoopm provide a better API for modifying atoms?
        return package_spec.replace(str(parsed.key.package), str(*matched))

    return package_spec


@functools.cache
def get_valid_values(pm: typing.Optional["gentoopm.basepm.PMBase"],
                     package_spec: str,
                     token_type: TokenType,
                     group: typing.Optional[str],
                     ) -> typing.Optional[set[str]]:
    """Get a list of valid values for (package, token type, group)"""

    if pm is None:
        return None

    # env files are global by design
    if token_type == TokenType.ENV_FILE:
        env_dir = Path(pm.config_root or "/") / "etc/portage/env"
        if not env_dir.is_dir():
            logging.debug(f"{env_dir} is not a directory, no valid "
                          f"{token_type.name} values")
            return set()
        values = set(path.name for path in env_dir.iterdir() if path.is_file())
        logging.debug(f"Valid values for {token_type.name}: {values}")
        return values

    # wildcard packages not supported
    if package_spec != "*/*" and is_wildcard_package(package_spec):
        return None

    group_match = ""
    group_len = 0
    if group is not None:
        group_match = group.lower() + "_"
        group_len = len(group_match)

    values = set()
    values.add("**" if token_type == TokenType.KEYWORD else "*")
    if token_type == TokenType.LICENSE:
        values.update(f"@{name}" for name in pm.stack.license_groups)

    if package_spec == "*/*":
        if token_type == TokenType.USE_FLAG:
            if group is not None:
                use_expand = pm.stack.use_expand.get(group)
                if use_expand is None:
                    logging.debug(
                        f"{token_type.name} group: {group} is not valid")
                    return set()
                if not use_expand.prefixed:
                    logging.debug(
                        f"{token_type.name} group: {group} is not prefixed")
                    return set()
                values.update(use_expand.values)
            else:
                # NB: we deliberately ignore use_expand, as flaggie
                # is expected to have detected it and set the group
                values.update(pm.stack.global_use)
        elif token_type == TokenType.KEYWORD:
            values.update(["*", "~*"])
            arches = pm.stack.arches.values()
            values.update(f"~{arch.name}" for arch in arches)
            values.update(arch.name for arch in arches
                          if arch.stability != "testing")
        elif token_type == TokenType.LICENSE:
            values.update(pm.stack.licenses)
        elif token_type == TokenType.PROPERTY:
            # The PMs do not keep easily accessible lists of supported
            # PROPERTIES/RESTRICT values.  We could use *-allowed
            # from layout.conf but that would limit the available set
            # to these explicitly supported in ::gentoo.  Hardcoding
            # the complete set is also easier.

            # PMS-defined values
            values.update(["interactive", "live", "test_network"])
        elif token_type == TokenType.RESTRICT:
            # PMS-defined values
            values.update(["fetch", "mirror", "strip", "test", "userpriv"])
            # Additional Portage-defined values
            values.update(["binchecks", "bindist", "installsources",
                           "network-sandbox", "preserve-libs", "primaryuri",
                           "splitdebug",
                           ])
        else:
            assert False, f"Unhandled token type {token_type.name}"
    else:
        for pkg in _filter_packages(pm, package_spec):
            if token_type == TokenType.USE_FLAG:
                for flag in pkg.use:
                    flag = flag.lstrip("+-")
                    if flag.lower().startswith(group_match):
                        values.add(flag[group_len:])
            elif token_type == TokenType.KEYWORD:
                for keyword in pkg.keywords:
                    if keyword.startswith("-"):
                        continue
                    values.add(keyword)
                    values.add("~*")
                    if not keyword.startswith("~"):
                        values.add("*")
                        # allow ~arch even if the package is stable already
                        # https://github.com/projg2/flaggie/issues/42
                        values.add(f"~{keyword}")
            elif token_type == TokenType.LICENSE:
                values.update(more_itertools.collapse(pkg.license))
            elif token_type == TokenType.PROPERTY:
                values.update(more_itertools.collapse(pkg.properties))
            elif token_type == TokenType.RESTRICT:
                values.update(more_itertools.collapse(pkg.restrict))
            else:
                assert False, f"Unhandled token type {token_type.name}"

    logging.debug(
        f"Valid values for {package_spec} {token_type.name} group: {group}: "
        f"{values}")
    return values


@functools.cache
def split_use_expand(pm: typing.Optional["gentoopm.basepm.PMBase"],
                     flag: str,
                     ) -> tuple[typing.Optional[str], str]:
    """Split given flag into (group, name) using USE_EXPAND"""

    if pm is not None:
        flag_uc = flag.upper()
        # start with longest first, in case they overlap
        for group in sorted((group.name
                             for group in pm.stack.use_expand.values()
                             if group.prefixed),
                            key=lambda x: -len(x)):
            if flag_uc.startswith(f"{group}_"):
                return (group, flag[len(group)+1:])

    return (None, flag)
