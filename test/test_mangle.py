# (c) 2023 Michał Górny
# Released under the terms of the MIT license

from pathlib import Path

import pytest

from flaggie.config import ConfigFile, ConfigLine, parse_config_file
from flaggie.mangle import mangle_flag


def get_config(raw_data: list[str]) -> list[ConfigFile]:
    return [ConfigFile(Path("test.conf"), raw_data,
                       list(parse_config_file(raw_data)), set())]


@pytest.mark.parametrize("old", ["-foo", "foo"])
@pytest.mark.parametrize("new", ["-foo", "foo"])
def test_toggle_flag(old, new):
    config = get_config(["*/* foo",
                         "",
                         f"dev-foo/foo {old} bar",
                         "dev-foo/bar foo",
                         "dev-foo/foo baz",
                         ])
    mangle_flag(config, "dev-foo/foo", None, "foo", not new.startswith("-"))
    assert config[0].modified_lines == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine("dev-foo/foo", [new, "bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine("dev-foo/foo", ["baz"]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
def test_toggle_flag_append(new):
    config = get_config(["*/* foo",
                         "",
                         "dev-foo/foo bar",
                         "dev-foo/bar foo",
                         "dev-foo/foo baz",
                         "dev-foo/foo GROUP: other",
                         ])
    mangle_flag(config, "dev-foo/foo", None, "foo", not new.startswith("-"))
    assert config[0].modified_lines == {4}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine("dev-foo/foo", ["bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine("dev-foo/foo", ["baz", new]),
        ConfigLine("dev-foo/foo", [], [("GROUP", ["other"])]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
def test_toggle_flag_append_to_group(new):
    config = get_config(["*/* foo",
                         "",
                         "dev-foo/foo GROUP: bar",
                         "dev-foo/bar foo",
                         "dev-foo/foo group_baz",
                         ])
    mangle_flag(config, "dev-foo/foo", "group", "foo", not new.startswith("-"))
    assert config[0].modified_lines == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine("dev-foo/foo", [], [("GROUP", ["bar", new])]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine("dev-foo/foo", ["group_baz"]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
def test_toggle_flag_new_entry(new):
    config = get_config(["*/* foo",
                         "dev-foo/bar foo",
                         ])
    mangle_flag(config, "dev-foo/foo", None, "foo", not new.startswith("-"))
    assert config[0].modified_lines == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine("dev-foo/foo", [new]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
def test_toggle_flag_new_entry_because_of_group(new):
    config = get_config(["*/* foo",
                         "dev-foo/bar foo",
                         "dev-foo/foo GROUP: baz",
                         ])
    mangle_flag(config, "dev-foo/foo", None, "foo", not new.startswith("-"))
    assert config[0].modified_lines == {3}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine("dev-foo/foo", [], [("GROUP", ["baz"])]),
        ConfigLine("dev-foo/foo", [new]),
    ]


@pytest.mark.parametrize("new", ["-foo", "foo"])
def test_toggle_flag_new_entry_group(new):
    config = get_config(["*/* foo",
                         "dev-foo/foo group_baz",
                         ])
    mangle_flag(config, "dev-foo/foo", "group", "foo", not new.startswith("-"))
    assert config[0].modified_lines == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine("dev-foo/foo", ["group_baz"]),
        ConfigLine("dev-foo/foo", [], [("GROUP", [new])]),
    ]


@pytest.mark.parametrize("old", ["-group_foo", "group_foo"])
@pytest.mark.parametrize("new", ["-group_foo", "group_foo"])
def test_toggle_flag_in_group(old, new):
    config = get_config(["*/* foo",
                         "",
                         f"dev-foo/foo {old} group_bar",
                         "dev-foo/bar foo",
                         "dev-foo/foo GROUP: baz",
                         ])
    mangle_flag(config, "dev-foo/foo", "group", "foo", not new.startswith("-"))
    assert config[0].modified_lines == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine("dev-foo/foo", [new, "group_bar"]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine("dev-foo/foo", [], [("GROUP", ["baz"])]),
    ]


@pytest.mark.parametrize("old", ["-foo", "foo"])
@pytest.mark.parametrize("new", ["-foo", "foo"])
@pytest.mark.parametrize("group", ["Group", "GROUP"])
def test_toggle_flag_in_group_verbose(old, new, group):
    config = get_config(["*/* foo",
                         "",
                         f"dev-foo/foo {group}: {old} bar",
                         "dev-foo/bar foo",
                         "dev-foo/foo group_baz",
                         ])
    mangle_flag(config, "dev-foo/foo", "group", "foo", not new.startswith("-"))
    assert config[0].modified_lines == {2}
    assert config[0].parsed_lines == [
        ConfigLine("*/*", ["foo"]),
        ConfigLine(),
        ConfigLine("dev-foo/foo", [], [(group, [new, "bar"])]),
        ConfigLine("dev-foo/bar", ["foo"]),
        ConfigLine("dev-foo/foo", ["group_baz"]),
    ]
