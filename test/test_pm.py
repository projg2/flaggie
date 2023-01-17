# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import typing

from pathlib import Path

from flaggie.config import TokenType
from flaggie.pm import match_package, get_valid_values

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


class UseExpand(typing.NamedTuple):
    name: str
    prefixed: bool
    visible: bool
    values: dict[str, typing.Any]


class MockedPM:
    def __init__(self, config_root: typing.Optional[Path] = None):
        self.config_root = config_root

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

        @property
        def keywords(self):
            if self._atom == "=app-foo/bar-1":
                return frozenset(["-*", "amd64"])
            elif self._atom == "=app-foo/bar-2":
                return frozenset(["~amd64", "~riscv"])
            return frozenset([])

        @property
        def license(self):
            return [["Apache-2.0", "MIT"], "BSD"]

        @property
        def properties(self):
            return ["live"]

        @property
        def restrict(self):
            return ["fetch", "mirror", ["test"]]

        @property
        def use(self):
            return frozenset(["foo", "-bar", "+targets_frobnicate"])

    class stack:
        @staticmethod
        def select(atom: "MockedPM.Atom") -> "MockedPM.Atom":
            if "bar" not in atom._atom:
                raise ValueError("ENOENT")
            return MockedPM.Atom("app-foo/bar")

        @staticmethod
        def filter(atom: str) -> list["MockedPM.Atom"]:
            if atom.startswith("="):
                return [MockedPM.Atom(atom)]
            return [
                MockedPM.Atom(f"={atom}-1"),
                MockedPM.Atom(f"={atom}-2"),
            ]

        global_use = {"baz": None, "fjord": None}
        use_expand = {
            "GLOBAL": UseExpand(name="GLOBAL",
                                prefixed=True,
                                visible=True,
                                values={"val1": None,
                                        "val2": None,
                                        "val3": None,
                                        }),
            "UNPREFIXED": UseExpand(name="UNPREFIXED",
                                    prefixed=False,
                                    visible=True,
                                    values={"val1": None,
                                            "val2": None,
                                            }),
        }


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


@pytest.mark.parametrize(
    "package,token_type,group,expected",
    [("app-foo/bar", TokenType.USE_FLAG, None,
      ["*", "targets_frobnicate", "foo", "bar"]),
     ("app-foo/bar", TokenType.USE_FLAG, "TARGETS",
      ["*", "frobnicate"]),
     ("app-foo/bar", TokenType.KEYWORD, None,
      ["*", "~*", "**", "~amd64", "amd64", "~riscv"]),
     ("=app-foo/bar-1", TokenType.KEYWORD, None,
      ["*", "**", "amd64"]),
     ("=app-foo/bar-2", TokenType.KEYWORD, None,
      ["~*", "**", "~amd64", "~riscv"]),
     ("=app-foo/live-1", TokenType.KEYWORD, None,
      ["**"]),
     ("=app-foo/live-1", TokenType.LICENSE, None,
      ["*", "Apache-2.0", "BSD", "MIT"]),
     ("=app-foo/live-1", TokenType.PROPERTY, None,
      ["*", "live"]),
     ("=app-foo/live-1", TokenType.RESTRICT, None,
      ["*", "fetch", "mirror", "test"]),
     ("*/*", TokenType.USE_FLAG, None,
      ["*", "baz", "fjord"]),
     ("*/*", TokenType.USE_FLAG, "GLOBAL",
      ["*", "val1", "val2", "val3"]),
     ("*/*", TokenType.USE_FLAG, "INVALID", []),
     ("*/*", TokenType.USE_FLAG, "UNPREFIXED", []),
     ])
def test_get_valid_values_pkg(package, token_type, group, expected):
    assert (get_valid_values(MockedPM(), package, token_type, group) ==
            frozenset(expected))


def test_get_valid_values_env(tmp_path):
    env_dir = tmp_path / "etc/portage/env"
    env_dir.mkdir(parents=True)
    expected = frozenset(["foo", "bar", "baz"])
    for filename in expected:
        (env_dir / filename).touch()
    assert get_valid_values(MockedPM(tmp_path), "dev-foo/bar",
                            TokenType.ENV_FILE, None) == expected
