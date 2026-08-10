"""apm.yml の依存 pin が浮動せず、群としても実配置とも揃っていることを検査する。

home/apm.yml は 1 リポジトリから複数のパッケージを取るため、同じ commit hash が
複数行に literal で並ぶ。更新は全行を揃えて動かす前提だが、1 行だけ更新し忘れても
apm install は成功し、そのパッケージだけ古い版が静かに配られる。エラーにならず
「短い正常な結果」として返るので、install ログを見ても気づけない。

この guard が見るのは 4 つ。

- ref が指定されていない依存 (既定ブランチへ浮動し、install した時期で中身が変わる)
- 同一リポジトリを指す依存どうしの ref 不一致 (更新漏れ)
- apm.lock.yaml が記録する実配置との ref 不一致 (宣言だけ更新して install を忘れた形)
- 依存指定として分解できない形 (素通りさせず fail-closed で報告する)

群の一致検査は比較対象を要するため、単独パッケージのリポジトリを覆えない。実測では
15 行中 1 行がこれに当たった。lock との突き合わせがその範囲を埋める (lock は 1 行 1
エントリなので比較対象が常に在る)。2 つは別の失敗モードを見ており、片方だけでは
範囲か検出力のどちらかが欠ける。

覆わないもの。ref が実在するか、hash が上流の最新かは静的には見えない。上流追従は
`apm outdated` の領分であって、ここは「宣言どうしの整合」と「宣言と実配置の整合」
だけを担保する。

リポジトリ名は先頭 2 要素 (owner/repo) とする。3 要素目以降はリポジトリ内のパスで、
同一リポジトリ判定には使わないが、lock の virtual_path との突き合わせには使う。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, NamedTuple

import yaml

from config_guard.models import Finding

APM_MANIFEST_PATH = "home/apm.yml"
APM_LOCK_PATH = "home/apm.lock.yaml"


class Dependency(NamedTuple):
    """依存指定の分解結果。repo が None なら分解できなかったことを表す。"""

    repo: str | None
    path: str | None
    ref: str | None


def parse_dependency(spec: str) -> Dependency:
    """依存指定を (owner/repo, リポジトリ内パス, ref) へ分解する。

    分解できない形は全て None で返す (呼び出し側が「判定できない」として扱う)。
    ref が無い / 空の場合は ref を None で返す。ブランチ名は slash を含みうるので
    最初の "#" だけを区切りとする。
    """
    location, separator, ref = spec.partition("#")
    segments = location.split("/")
    if len(segments) < 2 or not segments[0] or not segments[1]:
        return Dependency(None, None, None)
    return Dependency(
        repo="/".join(segments[:2]),
        path="/".join(segments[2:]),
        ref=ref if separator and ref else None,
    )


def _load_apm_dependencies(manifest_path: Path) -> Any:
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        return None
    dependencies = manifest.get("dependencies")
    if not isinstance(dependencies, dict):
        return None
    return dependencies.get("apm")


def _load_lock_refs(lock_path: Path) -> dict[tuple[str, str], str] | None:
    """lock を (repo_url, virtual_path) -> resolved_ref の対応へ読む。

    lock が無い / 形が違う場合は None を返し、呼び出し側は突き合わせを飛ばす。
    lock はツールが生成するものなので、形の逸脱をこの guard の責務にはしない。
    """
    if not lock_path.is_file():
        return None
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

    manifest が無い (apm 未使用) 場合は検査対象なしで空を返す。findings は
    apm.yml の行順を保つ。群の不一致は行ごとではなくリポジトリごとに 1 件へまとめる
    (どの行が正しいかは静的には決められないので、群として提示する)。
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

    lock_refs = _load_lock_refs(root / APM_LOCK_PATH)

    findings: list[Finding] = []
    lock_findings: list[Finding] = []
    # 出現順を保つため dict を順序付き集合として使う。値は ref -> 件数
    refs_by_repo: dict[str, dict[str, int]] = {}

    for entry in apm_dependencies:
        if not isinstance(entry, str):
            findings.append(
                Finding(
                    APM_MANIFEST_PATH,
                    repr(entry),
                    "依存指定が文字列ではなく pin を判定できません",
                )
            )
            continue

        dependency = parse_dependency(entry)
        if dependency.repo is None:
            findings.append(
                Finding(
                    APM_MANIFEST_PATH,
                    entry,
                    "owner/repo の形に分解できず pin を判定できません",
                )
            )
            continue
        if dependency.ref is None:
            # 浮動として 1 件だけ報告し、以降の検査へは渡さない。複数で報告すると
            # 同じ行が何件にもなり、原因 (浮動なのか不一致なのか) が読み取りにくい
            findings.append(
                Finding(
                    APM_MANIFEST_PATH,
                    entry,
                    "ref が指定されていません (既定ブランチへ浮動します)",
                )
            )
            continue

        counts = refs_by_repo.setdefault(dependency.repo, {})
        counts[dependency.ref] = counts.get(dependency.ref, 0) + 1

        if lock_refs is not None:
            location = f"{dependency.repo}/{dependency.path}".rstrip("/")
            locked = lock_refs.get((dependency.repo, dependency.path or ""))
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
