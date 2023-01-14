# (c) 2022-2023 Michał Górny
# Released under the terms of the MIT license

import dataclasses
import os
import stat

import pytest

from flaggie.config import (TokenType, ConfigLine, find_config_files,
                            parse_config_file, dump_config_line,
                            ConfigFile, read_config_files, save_config_files,
                            )


@pytest.mark.parametrize(
    "layout,expected",
    [([], ["package.use/99local.conf"]),
     (["package.use"], None),
     (["package.use/a.conf", "package.use/b.conf"], None),
     (["package.use/a/foo.conf", "package.use/b/foo.conf"], None),
     # even though "a+" sorts before "a/", directories take precedence
     (["package.use/a/foo.conf", "package.use/a+"], None),
     # hidden and backup files should be ignored
     (["package.use/.foo", "package.use/foo.conf", "package.use/foo.conf~"],
      ["package.use/foo.conf"]),
     # corner case: package.use yielding no valid files
     (["package.use/.foo"], ["package.use/99local.conf"]),
     ])
def test_find_config(tmp_path, layout, expected):
    confdir = tmp_path / "etc/portage"
    for f in layout:
        path = confdir / f
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb"):
            pass
    if expected is None:
        expected = layout
    assert find_config_files(tmp_path, TokenType.USE_FLAG
                             ) == [confdir / x for x in expected]


TEST_CONFIG_FILE = [
    "#initial comment\n",
    "  # comment with whitespace\n",
    "\n",
    "*/* foo bar baz # global flags\n",
    "*/* FROBNICATE_TARGETS: frob1 frob2\n",
    "  dev-foo/bar weird#flag other # actual comment # more comment\n",
    "dev-foo/baz mixed LONG: too EMPTY:\n"
]

PARSED_TEST_CONFIG_FILE = [
    ConfigLine(comment="initial comment"),
    ConfigLine(comment=" comment with whitespace"),
    ConfigLine(),
    ConfigLine("*/*", ["foo", "bar", "baz"], [], " global flags"),
    ConfigLine("*/*", [], [("FROBNICATE_TARGETS", ["frob1", "frob2"])]),
    ConfigLine("dev-foo/bar", ["weird#flag", "other"], [],
               " actual comment # more comment"),
    ConfigLine("dev-foo/baz", ["mixed"], [("LONG", ["too"]), ("EMPTY", [])]),
]

for raw_line, line in zip(TEST_CONFIG_FILE, PARSED_TEST_CONFIG_FILE):
    line._raw_line = raw_line


def test_parse_config_file():
    assert list(parse_config_file(TEST_CONFIG_FILE)) == PARSED_TEST_CONFIG_FILE


def test_dump_config_line():
    assert [dump_config_line(x) for x in parse_config_file(TEST_CONFIG_FILE)
            ] == [x.lstrip(" ") for x in TEST_CONFIG_FILE]


def test_read_config_files(tmp_path):
    with open(tmp_path / "config", "w") as f:
        f.write("".join(TEST_CONFIG_FILE))
    with open(tmp_path / "config2", "w") as f:
        pass

    assert list(read_config_files([tmp_path / "config", tmp_path / "config2"])
                ) == [
        ConfigFile(tmp_path / "config", PARSED_TEST_CONFIG_FILE),
        ConfigFile(tmp_path / "config2", []),
    ]


def test_save_config_files_no_modification(tmp_path):
    config_files = [
        ConfigFile(tmp_path / "config", PARSED_TEST_CONFIG_FILE),
        ConfigFile(tmp_path / "config2", []),
    ]

    save_config_files(config_files)
    assert all(not config_file.path.exists() for config_file in config_files)


def invalidate_config_lines(lines: list[ConfigLine],
                            *line_nos: int,
                            ) -> list[ConfigLine]:
    out = list(lines)
    for x in line_nos:
        out[x] = dataclasses.replace(out[x])
        out[x].invalidate()
    return out


@pytest.mark.parametrize("write", [False, True])
def test_save_config_files(tmp_path, write):
    config_files = [
        ConfigFile(tmp_path / "config",
                   invalidate_config_lines(PARSED_TEST_CONFIG_FILE, 1, 5),
                   modified=True),
        ConfigFile(tmp_path / "config2",
                   [ConfigLine("dev-foo/bar", ["new"], [])],
                   modified=True),
        ConfigFile(tmp_path / "config3", []),
    ]

    for conf in config_files:
        with open(conf.path, "w") as f:
            os.fchmod(f.fileno(), 0o400)
            f.write("<original content>")
    save_config_files(config_files,
                      confirm_cb=lambda orig_file, temp_file: write)

    expected = ["<original content>" for _ in config_files]
    if write:
        expected[:2] = [
            "".join(x.lstrip(" ") for x in TEST_CONFIG_FILE),
            "dev-foo/bar new\n",
        ]

    assert [conf.path.read_text() for conf in config_files] == expected
    assert [stat.S_IMODE(os.stat(conf.path).st_mode) for conf in config_files
            ] == [0o400 for _ in config_files]
