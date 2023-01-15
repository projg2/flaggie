# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import argparse

import pytest

from flaggie.__main__ import (split_arg_sets, split_op,
                              namespace_into_token_group,
                              )
from flaggie.config import TokenType


@pytest.mark.parametrize(
    "args,expected",
    [(["+foo", "-bar"], [([], ["+foo", "-bar"])]),
     (["dev-foo/bar", "+foo"], [(["dev-foo/bar"], ["+foo"])]),
     (["dev-foo/bar", "baz", "-foo"],
      [(["dev-foo/bar", "baz"], ["-foo"])]),
     (["+foo", "dev-foo/*", "-foo"],
      [([], ["+foo"]), (["dev-foo/*"], ["-foo"])]),
     ([">=dev-foo/bar-11-r1", "+foo"], [([">=dev-foo/bar-11-r1"], ["+foo"])]),
     (["<bar-11", "+foo"], [(["<bar-11"], ["+foo"])]),
     (["~dev-foo/bar-21", "+foo"], [(["~dev-foo/bar-21"], ["+foo"])]),
     (["=bar-14*", "+foo"], [(["=bar-14*"], ["+foo"])]),
     ])
def test_split_arg_sets(args, expected):
    argp = argparse.ArgumentParser()
    assert list(split_arg_sets(argp, args)) == expected


@pytest.mark.parametrize(
    "args",
    [[""],
     ["dev-foo/bar"],
     ["dev-foo/*", "baz", "+flag", "pkg"],
     ])
def test_split_arg_sets_invalid(args):
    argp = argparse.ArgumentParser()
    with pytest.raises(SystemExit):
        list(split_arg_sets(argp, args))


@pytest.mark.parametrize(
    "op,expected",
    [("+foo", ("+", None, "foo")),
     ("-use::foo", ("-", "use", "foo")),
     ("%", ("%", None, None)),
     ])
def test_split_op(op, expected):
    assert split_op(op) == expected


@pytest.mark.parametrize(
    "arg,expected",
    [("use", (TokenType.USE_FLAG, None)),
     ("kw", (TokenType.KEYWORD, None)),
     ("PYTHON_TARGETS", (TokenType.USE_FLAG, "PYTHON_TARGETS")),
     ])
def test_namespace_into_token_group(arg, expected):
    assert namespace_into_token_group(arg) == expected
