# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import typing

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

    # FIXME: this catches =app-foo/bar-11*
    if pm is None or "*" in package_spec:
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
