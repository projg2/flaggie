# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import itertools
import typing

from pathlib import Path

import pytest

from flaggie.config import ConfigFile, ConfigLine, parse_config_file
from flaggie.mangle import (mangle_flag, remove_flag, WildcardEntryError,
                            package_pattern_to_re, is_wildcard_package,
                            is_wildcard_flag, insert_sorted,
                            )


def get_config(raw_data: list[str]) -> list[ConfigFile]:
    return [ConfigFile(Path("test.conf"), list(parse_config_file(raw_data)))]


def get_modified_line_nos(config_file: ConfigFile) -> frozenset[int]:
    def inner() -> typing.Generator[int, None, None]:
        for line_no, line in enumerate(config_file.parsed_lines):
            if line._raw_line is None:
                yield line_no

    assert config_file.modified
    return frozenset(inner())


def param_new() -> pytest.MarkDecorator:
    return pytest.mark.parametrize("new", ["-foo", "foo"])


def param_old_new(*, prefix: str = "", flag: str = "foo",
                  ) -> pytest.MarkDecorator:
    return pytest.mark.parametrize(
        "old,new",
        itertools.product([f"-{prefix}{flag}", f"{prefix}{flag}"], repeat=2))


def param_pkg(include_global: bool = False) -> pytest.MarkDecorator:
    return pytest.mark.parametrize(
        "package", ["dev-foo/foo", "dev-bar/*"] +
        (["*/*"] if include_global else []))


@param_old_new()
@param_pkg(include_global=True)
def test_toggle_flag(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {old} bar",
                         "dev-foo/bar foo",
                         f"{package} baz",
                         ])
    mangle_flag(config, package, None, new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [new, "bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["baz"]),
    ]


@param_new()
@param_pkg()
def test_toggle_flag_append(new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} bar",
                         "dev-foo/bar foo",
                         f"{package} baz",
                         f"{package} GROUP: other",
                         ])
    mangle_flag(config, package, None, new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {4}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, ["bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["baz", new]),
        ConfigLine(package, [], [("GROUP", ["other"])]),
    ]


@param_new()
@param_pkg(include_global=True)
def test_toggle_flag_append_to_group(new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} GROUP: bar",
                         "dev-foo/bar foo",
                         f"{package} group_baz",
                         ])
    mangle_flag(config, package, "group", new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [], [("GROUP", ["bar", new])]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["group_baz"]),
    ]


@param_new()
def test_toggle_flag_new_entry(new):
    config = get_config(["*/* foo",
                         "dev-foo/bar foo",
                         ])
    mangle_flag(config, "dev-foo/foo", None, new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine("dev-foo/foo", [new]),
    ]


@param_new()
def test_toggle_flag_new_entry_global(new):
    config = get_config(["dev-foo/bar foo",
                         ])
    mangle_flag(config, "*/*", None, new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {0}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", [new]),
        ConfigLine("dev-foo/bar", ["foo"]),
    ]


@param_new()
def test_toggle_flag_new_entry_wildcard(new):
    config = get_config(["dev-foo/bar foo",
                         ])
    with pytest.raises(WildcardEntryError):
        mangle_flag(config, "dev-foo/*", None, new.lstrip("-"),
                    not new.startswith("-"))


@param_new()
@param_pkg(include_global=True)
def test_toggle_flag_new_entry_because_of_group(new, package):
    config = get_config([f"{package} GROUP: baz",
                         "dev-foo/bar foo",
                         ])
    mangle_flag(config, package, None, new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {1}
    assert config[0].parsed_lines == [
        ConfigLine(package, [], [("GROUP", ["baz"])]),
        ConfigLine(package, [new]),
        ConfigLine("dev-foo/bar", ["foo"]),
    ]


@param_new()
@param_pkg(include_global=True)
def test_toggle_flag_new_entry_group(new, package):
    config = get_config([f"{package} group_baz",
                         "dev-foo/bar foo",
                         ])
    mangle_flag(config, package, "group", new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {1}
    assert config[0].parsed_lines == [
        ConfigLine(package, ["group_baz"]),
        ConfigLine(package, [], [("GROUP", [new])]),
        ConfigLine("dev-foo/bar", ["foo"]),
    ]


@param_old_new(prefix="group_")
@param_pkg(include_global=True)
def test_toggle_flag_in_group(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {old} group_bar",
                         "dev-foo/bar foo",
                         f"{package} GROUP: baz",
                         ])
    assert new.lstrip("-").startswith("group_")
    mangle_flag(config, package, "group", new.lstrip("-")[6:],
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [new, "group_bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, [], [("GROUP", ["baz"])]),
    ]


@param_old_new()
@pytest.mark.parametrize("group", ["Group", "GROUP"])
@param_pkg(include_global=True)
def test_toggle_flag_in_group_verbose(old, new, group, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {group}: {old} bar",
                         "dev-foo/bar foo",
                         f"{package} group_baz",
                         ])
    mangle_flag(config, package, "group", new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [], [(group, [new, "bar"])]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["group_baz"]),
    ]


@param_old_new(flag="*")
@param_pkg()
def test_toggle_wildcard_flag(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {old}",
                         ])
    mangle_flag(config, package, None, new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [new]),
    ]


@param_old_new(prefix="group_", flag="*")
@param_pkg()
def test_toggle_wildcard_flag_group(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {old}",
                         ])
    mangle_flag(config, package, "group", new.lstrip("-")[6:],
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [new]),
    ]


@param_old_new(flag="*")
@param_pkg()
def test_toggle_wildcard_flag_group_verbose(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} GROUP: {old}",
                         ])
    mangle_flag(config, package, "group", new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [], [("GROUP", [new])]),
    ]


@param_old_new(flag="*")
@pytest.mark.parametrize("other", ["bar", "group_foo"])
@param_pkg()
def test_toggle_wildcard_flag_non_final(old, new, other, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {old} {other}",
                         ])
    mangle_flag(config, package, None, new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [old, other, new]),
    ]


@param_old_new(flag="*")
@param_pkg()
def test_toggle_wildcard_flag_non_final_because_of_group(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {old} GROUP: bar",
                         ])
    mangle_flag(config, package, None, new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {3}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [old], [("GROUP", ["bar"])]),
        ConfigLine(package, [new]),
    ]


@param_old_new(prefix="group_", flag="*")
@param_pkg()
def test_toggle_wildcard_flag_group_non_final(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {old} bar",
                         ])
    mangle_flag(config, package, "group", new.lstrip("-")[6:],
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [new, "bar"]),
    ]


@param_old_new(flag="*")
@param_pkg()
def test_toggle_wildcard_flag_group_verbose_non_final(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} GROUP: {old}",
                         f"{package} bar",
                         ])
    mangle_flag(config, package, "group", new.lstrip("-"),
                not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [], [("GROUP", [new])]),
        ConfigLine(package, ["bar"]),
    ]


@pytest.mark.parametrize(
    "pattern,expected",
    [("dev-foo/bar", r"dev\-foo/bar"),
     ("dev-*/bar", r"dev\-.*/bar"),
     ("*/*", r".*/.*"),
     ("*/foo", r".*/foo"),
     ("x11-libs/gtk+", r"x11\-libs/gtk\+"),
     ("[0-9]+", r"\[0\-9\]\+"),
     ("?*?", r"\?.*\?"),
     ])
def test_package_pattern_to_re(pattern, expected):
    assert package_pattern_to_re(pattern).pattern == expected


@pytest.mark.parametrize(
    "package,expected",
    [("dev-foo/bar", False),
     ("dev-foo/*", True),
     ("*/*", True),
     ("=dev-foo/bar-11*", False),
     ])
def test_is_wildcard_package(package, expected):
    assert is_wildcard_package(package) == expected


@param_pkg()
def test_remove_flag(package):
    config = get_config(["*/* foo GROUP: foo",
                         "",
                         f"{package} foo bar GROUP: foo",
                         "dev-foo/bar foo",
                         f"{package} baz -foo group_foo",
                         f"{package} -foo",
                         ])
    remove_flag(config, package, None, "foo")
    assert get_modified_line_nos(config[0]) == {2, 4}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"], [("GROUP", ["foo"])]),
        ConfigLine(),
        ConfigLine(package, ["bar"], [("GROUP", ["foo"])]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["baz", "group_foo"]),
    ]


@param_pkg()
def test_remove_flag_in_group(package):
    config = get_config(["*/* foo GROUP: foo",
                         "",
                         f"{package} foo bar GROUP: foo bar GROUP: -foo",
                         "dev-foo/bar foo",
                         f"{package} baz foo group_foo",
                         f"{package} -group_foo GROUP: foo",
                         ])
    remove_flag(config, package, "group", "foo")
    assert get_modified_line_nos(config[0]) == {2, 4}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"], [("GROUP", ["foo"])]),
        ConfigLine(),
        ConfigLine(package, ["foo", "bar"], [("GROUP", ["bar"])]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["baz", "foo"]),
    ]


@param_pkg()
def test_remove_all_in_group(package):
    config = get_config(["*/* foo GROUP: foo",
                         "",
                         f"{package} foo bar GROUP: foo -bar GROUP: foo",
                         "dev-foo/bar foo",
                         f"{package} baz foo group_foo",
                         f"{package} group_foo GROUP: foo",
                         ])
    remove_flag(config, package, "group", None)
    assert get_modified_line_nos(config[0]) == {2, 4}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"], [("GROUP", ["foo"])]),
        ConfigLine(),
        ConfigLine(package, ["foo", "bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["baz", "foo"]),
    ]


@param_pkg()
def test_remove_all(package):
    config = get_config(["*/* foo GROUP: foo",
                         "",
                         f"{package} foo -bar GROUP: foo bar GROUP: foo",
                         "dev-foo/bar foo",
                         f"{package} baz -foo group_foo",
                         f"{package} group_foo GROUP: -foo",
                         ])
    remove_flag(config, package, None, None)
    assert get_modified_line_nos(config[0]) == set()
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"], [("GROUP", ["foo"])]),
        ConfigLine(),
        ConfigLine("dev-foo/bar", ["foo"]),
    ]


@pytest.mark.parametrize(
    "flag,expected",
    [("foo", False),
     ("*", True),
     ("*foo", False),
     ("foo*", False),
     ("foo_*", True),
     ("**", True),
     ("~*", True),
     ])
def test_is_wildcard_flag(flag: str, expected: bool) -> None:
    assert is_wildcard_flag(flag) == expected


@pytest.mark.parametrize(
    "flags,new_flag,expected",
    [(["a", "c", "e"], "b", ["a", "b", "c", "e"]),
     (["a", "c", "e"], "d", ["a", "c", "d", "e"]),
     (["a", "c", "e"], "f", ["a", "c", "e", "f"]),
     (["b", "c", "d"], "a", ["a", "b", "c", "d"]),
     (["b", "*", "c"], "a", ["b", "*", "a", "c"]),
     (["b", "*"], "a", ["b", "*", "a"]),
     (["*"], "a", ["*", "a"]),
     (["a"], "*", ["a", "*"]),
     (["*", "a"], "*", ["*", "a", "*"]),
     ])
def test_insert_sorted(flags: list[str],
                       new_flag: str,
                       expected: list[str],
                       ) -> None:
    insert_sorted(flags, new_flag)
    assert flags == expected
