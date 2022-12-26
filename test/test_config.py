# (c) 2022 Michał Górny
# Released under the terms of the MIT license

import pytest

from flaggie.config import TokenType, find_config_file


@pytest.mark.parametrize(
    "layout,expected",
    [([], "package.use/99local.conf"),
     (["package.use"], "package.use"),
     (["package.use/a.conf", "package.use/b.conf"], "package.use/b.conf"),
     (["package.use/a/foo.conf", "package.use/b/foo.conf"],
      "package.use/b/foo.conf"),
     # even though "a+" sorts before "a/", directories take precedence
     (["package.use/a+", "package.use/a/foo.conf"], "package.use/a+"),
     ])
def test_find_config(tmp_path, layout, expected):
    for f in layout:
        path = tmp_path / "etc/portage" / f
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb"):
            pass
    assert find_config_file(tmp_path, TokenType.USE_FLAG
                            ) == tmp_path / "etc/portage" / expected
