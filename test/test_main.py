# (c) 2023 Michał Górny
# Released under the terms of the MIT license

import argparse

import pytest

from flaggie.__main__ import split_arg_sets


@pytest.mark.parametrize(
    "args,expected",
    [(["+foo", "-bar"], [([], ["+foo", "-bar"])]),
     (["dev-foo/bar", "+foo"], [(["dev-foo/bar"], ["+foo"])]),
     (["dev-foo/bar", "baz", "-foo"],
      [(["dev-foo/bar", "baz"], ["-foo"])]),
     (["+foo", "dev-foo/*", "-foo"],
      [([], ["+foo"]), (["dev-foo/*"], ["-foo"])]),
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
