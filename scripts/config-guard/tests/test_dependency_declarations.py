"""shipped tool の import が pyproject の宣言と一致していることを検査する。

src/config_guard は `[project] dependencies` に無いパッケージを import してはならない。
テストは dev グループ込みの環境で走るため、dev 専用の依存を src/ から import しても
そこでは解決でき、テストは緑のまま通る。壊れるのは dev グループを持たない配布側
(`uv sync --no-dev` / `uv tool install` / pip) だけで、しかもテスト結果にも install ログにも
出ない。実際 pyyaml が dev 専用のまま apm_pins.py へ入った。

許可する名前をここに literal で持たない。canonical な宣言は pyproject.toml であり、
再掲すると drift する。宣言名 (distribution) から import 名 (top-level module) への対応は
importlib.metadata に引く。

覆うのは ast で見える import 文だけ。importlib.import_module のような動的解決は静的には
見えないので範囲外である。
"""

from __future__ import annotations

import ast
import re
import sys
import tomllib
from importlib.metadata import packages_distributions
from pathlib import Path
from typing import Any

from tests.conftest import PACKAGE_ROOT

SOURCE_ROOT = PACKAGE_ROOT / "src" / "config_guard"

# PEP 503 の正規化。PyYAML / pyyaml / py_yaml を同じ名前へ潰す
_NORMALIZE = re.compile(r"[-_.]+")

# requirement 文字列の先頭の名前だけを取る。version 指定子 / extras / marker の手前で切れる
_REQUIREMENT_NAME = re.compile(r"^[A-Za-z0-9._-]+")


def _canonical(name: str) -> str:
    return _NORMALIZE.sub("-", name).lower()


def _requirement_name(requirement: str) -> str:
    match = _REQUIREMENT_NAME.match(requirement.strip())
    assert match is not None, f"依存宣言から名前を取れない: {requirement!r}"
    return _canonical(match.group())


def _pyproject() -> dict[str, Any]:
    """宣言の canonical。テストは値を再掲せずここから読む。"""
    return tomllib.loads((PACKAGE_ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def _declared_distributions() -> set[str]:
    """[project] dependencies が宣言する distribution 名を正規化して返す。"""
    requirements: list[str] = _pyproject()["project"]["dependencies"]
    return {_requirement_name(requirement) for requirement in requirements}


def _dev_only_distributions() -> set[str]:
    """dev グループにしか無い distribution 名。許可集合の負の対照に使う。"""
    requirements: list[str] = _pyproject()["dependency-groups"]["dev"]
    declared = _declared_distributions()
    return {_requirement_name(requirement) for requirement in requirements} - declared


def _modules_of(distributions: set[str]) -> set[str]:
    """distribution 名が提供する top-level module 名を、入っている環境から引く。"""
    return {
        module
        for module, providers in packages_distributions().items()
        if any(_canonical(provider) in distributions for provider in providers)
    }


def _allowed_modules() -> set[str]:
    """src/ が import してよい top-level module 名。"""
    return set(sys.stdlib_module_names) | {"config_guard"} | _modules_of(_declared_distributions())


def _python_sources(root: Path) -> list[Path]:
    """検査対象の .py を再帰で集める。

    非再帰だとサブパッケージを足した時点でそこだけ黙って無検査になる。範囲の穴は
    「検査を壊すと赤くなるか」では見えない (どの変異も範囲内でしか効かない)。
    """
    return sorted(root.rglob("*.py"))


def _imported_top_level_modules(source: Path) -> set[str]:
    """ファイル内の絶対 import の top-level module 名を集める (関数内 import も含む)。"""
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            modules.add(node.module.split(".")[0])
    return modules


def test_source_imports_nothing_beyond_stdlib_and_declared_dependencies() -> None:
    # 検出したい本体。dev 専用依存が src/ へ入った形
    allowed = _allowed_modules()
    sources = _python_sources(SOURCE_ROOT)
    # 走査が空振りしていたら「未宣言 0 件」は健全ではなく「1 件も見ていない」
    assert len(sources) >= 2, f"src/config_guard の走査が空振りしている: {SOURCE_ROOT}"

    undeclared = sorted(
        f"{source.name}: {module}"
        for source in sources
        for module in _imported_top_level_modules(source)
        if module not in allowed
    )

    assert not undeclared, (
        f"[project] dependencies に無い import がある: {undeclared} "
        "(dev グループ込みのテスト環境では解決できるが、配布側で ModuleNotFoundError になる)"
    )


def test_the_scan_sees_at_least_one_third_party_import() -> None:
    # 上の検査が対象ゼロで緑になっていないことの対照。src/ が全て stdlib なら
    # 宣言との突き合わせは何も見ておらず、「未宣言 0 件」は健全を意味しない
    imported = {
        module
        for source in _python_sources(SOURCE_ROOT)
        for module in _imported_top_level_modules(source)
    }
    third_party = imported - set(sys.stdlib_module_names) - {"config_guard"}

    assert third_party, "src/ に外部 import が無く、宣言との突き合わせが対象ゼロで緑になっている"


def test_dev_only_distributions_never_enter_the_allowed_set() -> None:
    # 許可集合の負の対照。上の 2 つの対照は「対象ゼロ」と「宣言が解決できない」を見るので、
    # 集合が広すぎる方向の壊れ方は原理的に検出できない。実際 _modules_of の絞り込みを
    # 外しても全テストが緑のままだった (許可集合が全 module になり検査が無効化される)
    dev_only = _modules_of(_dev_only_distributions())
    leaked = dev_only & _allowed_modules()

    assert dev_only, "dev 専用 distribution の module を 1 件も解決できず対照が空回りしている"
    assert not leaked, f"dev 専用依存の module が許可集合へ漏れている: {sorted(leaked)}"


def test_every_declared_dependency_resolves_to_an_import_name() -> None:
    # 宣言側の対照。distribution 名から module 名を引けないと allowed へ何も足されず、
    # 正しい import まで未宣言として赤くなる (逆に宣言が空だと突き合わせる相手が居ない)
    declared = _declared_distributions()

    assert declared, "[project] dependencies が空で、突き合わせる宣言が無い"
    for distribution in sorted(declared):
        assert _modules_of({distribution}), f"{distribution} が提供する module 名を解決できない"


def test_source_scan_reaches_into_subpackages(tmp_path: Path) -> None:
    # 走査の範囲。src/ が今は平坦なので実ファイルでは非再帰との差が出ず、
    # サブパッケージを足した日に黙って無検査になる形はここでしか捕まえられない
    (tmp_path / "sub").mkdir()
    (tmp_path / "top.py").write_text("", encoding="utf-8")
    (tmp_path / "sub" / "nested.py").write_text("", encoding="utf-8")

    assert [path.name for path in _python_sources(tmp_path)] == ["nested.py", "top.py"]


def test_import_scan_collects_names_from_every_import_position(tmp_path: Path) -> None:
    # 走査ヘルパの仕様。関数内 import まで拾い、相対 import は自パッケージなので拾わない
    source = tmp_path / "sample.py"
    source.write_text(
        "import yaml\n"
        "import a.b as ab\n"
        "from c.d import e\n"
        "from . import sibling\n"
        "from .models import Finding\n"
        "def f() -> None:\n"
        "    import deferred\n",
        encoding="utf-8",
    )

    assert _imported_top_level_modules(source) == {"yaml", "a", "c", "deferred"}


def test_requirement_names_are_taken_up_to_the_version_specifier() -> None:
    # 宣言の書き方は canonical 側 (pyproject) の自由。名前の切り出しがそれに追従する
    for requirement, expected in (
        ("pyyaml>=6.0", "pyyaml"),
        ("PyYAML", "pyyaml"),
        ("requests[socks]>=2", "requests"),
        ("tomli ; python_version < '3.11'", "tomli"),
        ("types_py-yaml==6.0", "types-py-yaml"),
    ):
        assert _requirement_name(requirement) == expected, requirement
