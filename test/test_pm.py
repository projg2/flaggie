# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import typing

from flaggie.pm import match_package

import pytest


VALID_SPECS = [
    "app-foo/bar",
    ">=app-foo/bar-1-r1",
    "=app-foo/bar-29*",
    "*/*",
    "app-foo/*",
]

SHORT_SPECS = [
    "bar",
    ">=bar-11",
]


class MockedPM:
    class Atom:
        class _key(typing.NamedTuple):
            category: typing.Optional[str]
            package: str

            def __str__(self):
                return f"{self.category}/{self.package}"

        def __init__(self, atom: str) -> None:
            assert "/*" not in atom
            self._atom = atom

        @property
        def key(self):
            if "/" in self._atom:
                return self._key("app-foo", "bar")
            return self._key(None, "bar")

    class stack:
        @staticmethod
        def select(atom: "MockedPM.Atom") -> "MockedPM.Atom":
            if "bar" not in atom._atom:
                raise ValueError("ENOENT")
            return MockedPM.Atom("app-foo/bar")


@pytest.mark.parametrize("package", VALID_SPECS)
@pytest.mark.parametrize("pm", [None, MockedPM()])
def test_match_package(pm, package):
    assert match_package(pm, package) == package


@pytest.mark.parametrize("package", SHORT_SPECS)
def test_match_package_expand(package):
    assert (match_package(MockedPM(), package) ==
            package.replace("bar", "app-foo/bar"))


def test_match_package_expand_raise():
    with pytest.raises(ValueError):
        match_package(MockedPM(), "nonexistent")


@pytest.mark.parametrize("package", SHORT_SPECS + ["*"])
def test_match_package_no_pm_no_category(package):
    with pytest.raises(ValueError):
        match_package(None, package)
