# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import typing

from pathlib import Path

import pytest

from flaggie.config import ConfigFile, ConfigLine, parse_config_file
from flaggie.mangle import mangle_flag, WildcardEntryError


def get_config(raw_data: list[str]) -> list[ConfigFile]:
    return [ConfigFile(Path("test.conf"), list(parse_config_file(raw_data)))]


def get_modified_line_nos(config_file: ConfigFile) -> frozenset[int]:
    def inner() -> typing.Generator[int, None, None]:
        for line_no, line in enumerate(config_file.parsed_lines):
            if line._raw_line is None:
                yield line_no

    assert config_file.modified
    return frozenset(inner())


@pytest.mark.parametrize("old", ["-foo", "foo"])
@pytest.mark.parametrize("new", ["-foo", "foo"])
@pytest.mark.parametrize("package", ["dev-foo/foo", "dev-bar/*"])
def test_toggle_flag(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {old} bar",
                         "dev-foo/bar foo",
                         f"{package} baz",
                         ])
    mangle_flag(config, package, None, "foo", not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [new, "bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["baz"]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
@pytest.mark.parametrize("package", ["dev-foo/foo", "dev-bar/*"])
def test_toggle_flag_append(new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} bar",
                         "dev-foo/bar foo",
                         f"{package} baz",
                         f"{package} GROUP: other",
                         ])
    mangle_flag(config, package, None, "foo", not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {4}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, ["bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["baz", new]),
        ConfigLine(package, [], [("GROUP", ["other"])]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
@pytest.mark.parametrize("package", ["dev-foo/foo", "dev-bar/*"])
def test_toggle_flag_append_to_group(new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} GROUP: bar",
                         "dev-foo/bar foo",
                         f"{package} group_baz",
                         ])
    mangle_flag(config, package, "group", "foo", not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [], [("GROUP", ["bar", new])]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["group_baz"]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
def test_toggle_flag_new_entry(new):
    config = get_config(["*/* foo",
                         "dev-foo/bar foo",
                         ])
    mangle_flag(config, "dev-foo/foo", None, "foo", not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine("dev-foo/foo", [new]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
def test_toggle_flag_new_entry_global(new):
    config = get_config(["dev-foo/bar foo",
                         ])
    mangle_flag(config, "*/*", None, "foo", not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {0}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", [new]),
        ConfigLine("dev-foo/bar", ["foo"]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
def test_toggle_flag_new_entry_wildcard(new):
    config = get_config(["dev-foo/bar foo",
                         ])
    with pytest.raises(WildcardEntryError):
        mangle_flag(config, "dev-foo/*", None, "foo", not new.startswith("-"))


@pytest.mark.parametrize("new", ["-foo", "foo"])
@pytest.mark.parametrize("package", ["dev-foo/foo", "dev-bar/*", "*/*"])
def test_toggle_flag_new_entry_because_of_group(new, package):
    config = get_config([f"{package} GROUP: baz",
                         "dev-foo/bar foo",
                         ])
    mangle_flag(config, package, None, "foo", not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {1}
    assert config[0].parsed_lines == [
        ConfigLine(package, [], [("GROUP", ["baz"])]),
        ConfigLine(package, [new]),
        ConfigLine("dev-foo/bar", ["foo"]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
@pytest.mark.parametrize("package", ["dev-foo/foo", "dev-bar/*", "*/*"])
def test_toggle_flag_new_entry_group(new, package):
    config = get_config([f"{package} group_baz",
                         "dev-foo/bar foo",
                         ])
    mangle_flag(config, package, "group", "foo", not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {1}
    assert config[0].parsed_lines == [
        ConfigLine(package, ["group_baz"]),
        ConfigLine(package, [], [("GROUP", [new])]),
        ConfigLine("dev-foo/bar", ["foo"]),
    ]


@pytest.mark.parametrize("old", ["-group_foo", "group_foo"])
@pytest.mark.parametrize("new", ["-group_foo", "group_foo"])
@pytest.mark.parametrize("package", ["dev-foo/foo", "dev-bar/*"])
def test_toggle_flag_in_group(old, new, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {old} group_bar",
                         "dev-foo/bar foo",
                         f"{package} GROUP: baz",
                         ])
    mangle_flag(config, package, "group", "foo", not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [new, "group_bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, [], [("GROUP", ["baz"])]),
    ]


@pytest.mark.parametrize("old", ["-foo", "foo"])
@pytest.mark.parametrize("new", ["-foo", "foo"])
@pytest.mark.parametrize("group", ["Group", "GROUP"])
@pytest.mark.parametrize("package", ["dev-foo/foo", "dev-bar/*"])
def test_toggle_flag_in_group_verbose(old, new, group, package):
    config = get_config(["*/* foo",
                         "",
                         f"{package} {group}: {old} bar",
                         "dev-foo/bar foo",
                         f"{package} group_baz",
                         ])
    mangle_flag(config, package, "group", "foo", not new.startswith("-"))
    assert get_modified_line_nos(config[0]) == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine(package, [], [(group, [new, "bar"])]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine(package, ["group_baz"]),
    ]
