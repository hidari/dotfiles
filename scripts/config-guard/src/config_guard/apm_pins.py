"""apm.yml の依存 pin が commit SHA で固定され、群としても実配置とも揃っていることを検査する。

home/apm.yml は 1 リポジトリから複数のパッケージを取るため、同じ commit hash が
複数行に literal で並ぶ。更新は全行を揃えて動かす前提だが、1 行だけ更新し忘れても
apm install は成功し、そのパッケージだけ古い版が静かに配られる。エラーにならず
「短い正常な結果」として返るので、install ログを見ても気づけない。

この guard が見るのは 4 つ。

- ref が commit SHA で固定されているか (README が宣言する再現性の担保。ref 不在は
  既定ブランチへ浮動し、ブランチや tag は付け替えられる)
- 同一リポジトリを指す依存どうしの ref 不一致 (更新漏れ)
- apm.lock.yaml が記録する実配置との ref 不一致 (宣言だけ更新して install を忘れた形)
- どの依存指定形にも当てはまらない入力 (素通りさせず fail-closed で報告する)

群の一致検査は比較対象を要するため、単独パッケージのリポジトリを覆えない。lock との
突き合わせがその範囲を埋める (lock は 1 行 1 エントリなので比較対象が常に在る)。
2 つは別の失敗モードを見ており、片方だけでは範囲か検出力のどちらかが欠ける。

覆う依存指定形は github shorthand (`owner/repo[/path][#ref]`) だけである。apm は他に
host 付き (`gitlab.com/org/repo`)、オブジェクト形 (`git:`/`path:`/`ref:`)、local path
(`./packages/x`) も受けるが、これらが lock にどう記録されるかを実測できていないため
検査対象から外す。推測で検査を書くと、正しい manifest に偽陽性の赤を出すか、逆に
「見ているつもりで見ていない」緑を作る。always_run の pre-commit に配線されているので
偽陽性は全コミットを止める。対象外の形が manifest へ入った時点で
tests/test_apm_pins.py の対照テストが赤くなり、判断を促す形にしてある。

覆わないもの。ref が実在するか、hash が上流の最新かは静的には見えない。上流追従は
`apm outdated` の領分であって、ここは「宣言どうしの整合」と「宣言と実配置の整合」
だけを担保する。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, NamedTuple

import yaml

from config_guard.models import Finding

APM_MANIFEST_PATH = "home/apm.yml"
APM_LOCK_PATH = "home/apm.lock.yaml"

# git の完全な object name。短縮形は将来衝突しうるので受けない。lock は小文字で
# 記録するため、大文字を許すと突き合わせが文字列比較で外れる
COMMIT_SHA_PATTERN = re.compile(r"[0-9a-f]{40}")


class Dependency(NamedTuple):
    """依存指定の分解結果。

    kind は次のいずれか。
    - "github": owner/repo[/path][#ref]。この guard が覆う唯一の形
    - "hosted": host 付き (gitlab.com/org/repo)。分類のみ
    - "local":  local path (./packages/x)。ref の概念が無い。分類のみ
    - "unknown": どの形にも当てはまらない。fail-closed で報告する

    マッピング形 (git:/path:/ref:) はここへ来ない。check_apm_pins が
    parse_dependency へ渡す前に除外する。
    """

    kind: str
    repo: str | None
    path: str | None
    ref: str | None


def parse_dependency(spec: str) -> Dependency:
    """依存指定を分解し、この guard が覆う形かどうかを分類する。

    ブランチ名は slash を含みうるので最初の "#" だけを区切りとする。
    ref が無い / 空の場合は ref を None で返す。
    """
    if spec.startswith((".", "/")):
        return Dependency("local", None, None, None)

    location, _, ref = spec.partition("#")
    segments = location.split("/")
    # 先頭要素が空になる形 ("/...") は上の local 判定で既に返っているため、
    # ここで見るのは要素数と 2 番目の要素が空でないことだけでよい
    if len(segments) < 2 or not segments[1]:
        return Dependency("unknown", None, None, None)
    if "." in segments[0]:
        # GitHub の owner / org 名にドットは使えないため、先頭要素のドットは host を意味する
        return Dependency("hosted", None, None, None)

    return Dependency(
        kind="github",
        repo="/".join(segments[:2]),
        path="/".join(segments[2:]),
        ref=ref or None,
    )


def _load_apm_dependencies(manifest_path: Path) -> Any:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        return None
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict):
        return None
    return dependencies.get("apm")


def load_lock_refs(lock_path: Path) -> dict[tuple[str, str], str] | None:
    """lock を (repo_url, virtual_path) -> resolved_ref の対応へ読む。

    lock が無い場合と、在るのに形を認識できない場合を呼び出し側が区別できるよう、
    前者は空でなく「lock 不在」として扱えるように呼び出し側で is_file() を見る。
    ここでは形を認識できないときだけ None を返す。

    比較先は resolved_commit ではなく resolved_ref である。manifest が指定した ref が
    そのまま記録される側で、宣言と実配置の突き合わせにはこちらが対応する。
    """
    lock = yaml.safe_load(lock_path.read_text(encoding="utf-8"))
    if not isinstance(lock, dict):
        return None
    entries = lock.get("dependencies")
    if not isinstance(entries, list):
        return None

    refs: dict[tuple[str, str], str] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        repo = entry.get("repo_url")
        ref = entry.get("resolved_ref")
        if isinstance(repo, str) and isinstance(ref, str):
            refs[(repo, str(entry.get("virtual_path") or ""))] = ref
    return refs


def check_apm_pins(repo_root: str) -> list[Finding]:
    """apm.yml の依存 pin を検査する。

    manifest が無い (apm 未使用) 場合は検査対象なしで空を返す。manifest 由来の
    findings は apm.yml の行順を保ち、lock 由来の findings をその後ろへ連ねる。
    群の不一致は行ごとではなくリポジトリごとに 1 件へまとめる (どの行が正しいかは
    静的には決められないので、群として提示する)。
    """
    root = Path(repo_root)
    manifest_path = root / APM_MANIFEST_PATH
    if not manifest_path.is_file():
        return []

    apm_dependencies = _load_apm_dependencies(manifest_path)
    if apm_dependencies is None:
        return []
    if not isinstance(apm_dependencies, list):
        return [
            Finding(
                APM_MANIFEST_PATH,
                f"apm: {apm_dependencies!r}",
                "dependencies.apm がリストではないため pin を検査できません",
            )
        ]

    findings: list[Finding] = []
    lock_findings: list[Finding] = []

    lock_path = root / APM_LOCK_PATH
    lock_refs: dict[tuple[str, str], str] | None = None
    if lock_path.is_file():
        lock_refs = load_lock_refs(lock_path)
        if lock_refs is None:
            # 黙って突き合わせを飛ばすと「1 件も見ていない緑」になる。
            # apm の版更新でキー名が変わる経路が実在するので fail-closed にする
            lock_findings.append(
                Finding(
                    APM_LOCK_PATH,
                    "dependencies",
                    "lock の形を認識できず宣言と突き合わせできません",
                )
            )

    # 出現順を保つため dict を順序付き集合として使う。値は ref -> 件数
    refs_by_repo: dict[str, dict[str, int]] = {}

    for entry in apm_dependencies:
        if isinstance(entry, dict):
            # git:/path:/ref: のオブジェクト形。分類のみで検査対象外
            continue
        if not isinstance(entry, str):
            findings.append(
                Finding(
                    APM_MANIFEST_PATH,
                    repr(entry),
                    "依存指定が文字列でもマッピングでもなく pin を判定できません",
                )
            )
            continue

        dependency = parse_dependency(entry)
        if dependency.kind == "unknown":
            findings.append(
                Finding(
                    APM_MANIFEST_PATH,
                    entry,
                    "どの依存指定形にも当てはまらず pin を判定できません",
                )
            )
            continue
        if dependency.kind != "github":
            continue

        if dependency.ref is None:
            # 以降の検査へは渡さない。複数で報告すると同じ行が何件にもなり、
            # 原因 (浮動なのか不一致なのか) が読み取りにくい
            findings.append(
                Finding(
                    APM_MANIFEST_PATH,
                    entry,
                    "ref が指定されていません (既定ブランチへ浮動します)",
                )
            )
            continue
        if not COMMIT_SHA_PATTERN.fullmatch(dependency.ref):
            findings.append(
                Finding(
                    APM_MANIFEST_PATH,
                    entry,
                    "ref が commit SHA ではありません "
                    "(ブランチと tag は付け替えられるので再現性を担保しません)",
                )
            )
            continue

        counts = refs_by_repo.setdefault(dependency.repo or "", {})
        counts[dependency.ref] = counts.get(dependency.ref, 0) + 1

        if lock_refs is not None:
            location = f"{dependency.repo}/{dependency.path}".rstrip("/")
            locked = lock_refs.get((dependency.repo or "", dependency.path or ""))
            if locked is None:
                lock_findings.append(
                    Finding(
                        APM_LOCK_PATH,
                        location,
                        "lock に対応する項目がありません (apm install が未実行です)",
                    )
                )
            elif locked != dependency.ref:
                lock_findings.append(
                    Finding(
                        APM_LOCK_PATH,
                        f"{location}: apm.yml={dependency.ref} lock={locked}",
                        "宣言と lock の ref が違います "
                        "(配置済みの実体は lock 側の版なので、古い版が配られています)",
                    )
                )

    for repo, counts in refs_by_repo.items():
        if len(counts) > 1:
            summary = ", ".join(f"{ref} ({count})" for ref, count in counts.items())
            findings.append(
                Finding(
                    APM_MANIFEST_PATH,
                    f"{repo}: {summary}",
                    "同一リポジトリを指す依存の ref が一致しません "
                    "(1 行の更新漏れは、そのパッケージだけ古い版が静かに配られる形で壊れます)",
                )
            )
    return findings + lock_findings
