"""guard_probes の述語の仕様。

フック本体を subprocess 起動せず、共有層を直接 import して検査する。副作用 (print /
sys.exit) を持たない層なので、この形で仕様を読める。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import guard_probes
import guard_resolve
import pytest
from conftest import bash_symlink_pairs, git_scope_free_env, make_git_repo


def test_shim_へ解決すれば健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim = tmp_path / "libexec" / "apm"
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\n", encoding="utf-8")
    shim.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "apm").symlink_to(shim)

    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(shim))

    result = guard_probes.probe_apm()

    assert guard_resolve.shim_resolves() is True
    assert result.healthy is True
    assert result.detail == ""


def _apm_elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """shim ではない実体の apm だけが PATH に載っている状態を作る。

    沈黙の理由を「shim があるか」の 1 点だけに絞るための共通の土台。PATH 側を各テストで
    作り分けると、落ちたときにどちらの条件が効いたのか読めなくなる。
    """
    other = tmp_path / "bin" / "apm"
    other.parent.mkdir(parents=True)
    other.write_text("#!/bin/sh\n", encoding="utf-8")
    other.chmod(0o755)
    monkeypatch.setenv("PATH", str(other.parent))


def test_shim_は配置済みで_PATH_に載っていなければ起動元のシェルを告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2026-08-31 に実際に起きた状態。bootstrap.sh を勧めてはならない。

    shim は配置されているのに Claude Code の PATH へ載っていない。原因は起動元のシェルが
    古いことで、bootstrap.sh は何も直さない。実際にこの状態で bootstrap.sh と Claude Code
    の再起動を勧める文面に従い、1 往復を空振りさせた。
    """
    shim = tmp_path / "libexec" / "apm"
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\n", encoding="utf-8")
    _apm_elsewhere(tmp_path, monkeypatch)
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(shim))

    assert guard_resolve.shim_exists() is True
    assert guard_resolve.shim_resolves() is False
    result = guard_probes.probe_apm()
    assert result.healthy is False
    assert guard_resolve.APM_REMEDY_STALE_SHELL in result.detail
    assert guard_resolve.APM_REMEDY_MISSING_SHIM not in result.detail


def test_shim_が未配置なら配置からやり直すよう告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """shim の実体が無い状態。ここでだけ bootstrap.sh が手当てになる。"""
    _apm_elsewhere(tmp_path, monkeypatch)
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(tmp_path / "nonexistent" / "apm"))

    assert guard_resolve.shim_exists() is False
    result = guard_probes.probe_apm()
    assert result.healthy is False
    assert guard_resolve.APM_REMEDY_MISSING_SHIM in result.detail
    assert guard_resolve.APM_REMEDY_STALE_SHELL not in result.detail


def test_辿れない_symlink_の_shim_は未配置として扱う(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """symlink はあるが実体が無い状態。shim は symlink として配置されるので実際に起きうる。

    リポジトリを移動したあとや bootstrap.sh を通す前がこれにあたる。symlink の存在だけを
    見ると配置済みと読めてしまい、起動元のシェルを疑わせる誤った手当てへ倒れる。
    """
    shim = tmp_path / "libexec" / "apm"
    shim.parent.mkdir(parents=True)
    shim.symlink_to(tmp_path / "nonexistent" / "apm")
    _apm_elsewhere(tmp_path, monkeypatch)
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(shim))

    assert shim.is_symlink()
    assert guard_resolve.shim_exists() is False
    assert guard_resolve.APM_REMEDY_MISSING_SHIM in guard_probes.probe_apm().detail


def test_PATH_に_apm_が無ければ沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(tmp_path / "nonexistent" / "apm"))

    assert guard_resolve.shim_resolves() is False
    assert guard_probes.probe_apm().healthy is False


def test_shim_の置き場が配布先と一致する() -> None:
    """bootstrap.sh の SYMLINK_PAIRS を bash 自身に解釈させて読み、定数と突き合わせる。

    どちらか片方を直しても、もう片方が古いまま実配置と食い違う。bash に解釈させる読み方は
    conftest.bash_symlink_pairs に 1 つだけ置いてあり、ここではそれを呼ぶだけで
    インライン実装を持たない。
    """
    pairs = bash_symlink_pairs()
    assert pairs, "SYMLINK_PAIRS を 1 件も読めていない"

    expected = guard_resolve.DEFAULT_SHIM_PATH.removeprefix("~/")
    targets = [line.split("|", 1)[1] for line in pairs if "|" in line]
    assert expected in targets


def _fake_tirith(path: Path, exit_code: int) -> Path:
    """指定の exit code を返す偽 tirith を作る。"""
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_tirith_が_clean_へ応答すれば健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_tirith(tmp_path / "tirith", 0)
    monkeypatch.setenv("TIRITH_BIN", str(fake))
    assert guard_probes.probe_tirith().healthy is True


def test_TIRITH_BIN_未設定で解決しなければ沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.delenv("TIRITH_BIN", raising=False)
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("HOME", str(tmp_path))

    result = guard_probes.probe_tirith()
    assert result.healthy is False
    assert "沈黙" in result.detail
    # 復旧手順を pin する。実体化経路が mise から brew へ移ったとき、案内だけが古びて誰も
    # 赤くならなかった。
    assert "brew install tirith" in result.detail
    # この分岐は「入っていない」と「入っているが PATH に載っていない」の両方で通る。この層は
    # 区別できないので、片方だけを勧めてはならない。2026-08-31 に PATH から /opt/homebrew/bin を
    # 外して実測したところ、tirith は brew で入っているのに brew install tirith だけを勧めた。
    # apm 側でも同じ形が空振りを生んだ (この PR で修正済み)。
    assert "PATH に載っていない" in result.detail
    # 強制層と同じ定数を使うことも pin する。上の 2 つは部分文字列しか見ないので、この層へ
    # 文面を literal で書き戻す変異が緑のまま通り、寄せた二重管理が静かに戻せてしまう。
    assert guard_resolve.TIRITH_REMEDY_UNRESOLVED in result.detail


def test_TIRITH_BIN_のパスが無ければ全_Bash_が止まると告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TIRITH_BIN", str(tmp_path / "nonexistent" / "tirith"))

    result = guard_probes.probe_tirith()
    assert result.healthy is False
    # "Bash" だけでは駄目: tmp_path 名がこの関数名から作られ "_Bash0" で終わるため、
    # フォールバック分岐の文面 (tirith_bin をそのまま埋め込む) にも偶然 "Bash" が含まれる。
    assert "TIRITH_BIN=" in result.detail


def test_clean_なコマンドに_clean_を返さなければ沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """応答はするが clean を clean と判定しない状態。フックは fail-closed に倒れる。"""
    fake = _fake_tirith(tmp_path / "tirith", 1)
    monkeypatch.setenv("TIRITH_BIN", str(fake))

    result = guard_probes.probe_tirith()
    assert result.healthy is False


def test_登録簿は名前と関数の組を持つ() -> None:
    """呼び出し自体が例外で落ちたときにも名前が要るので、名前は結果ではなく登録簿が持つ。"""
    names = [name for name, _ in guard_probes.PROBES]
    assert names == ["apm", "tirith", "private-ops", "task-list-id", "herdr-pane"]
    for _, probe in guard_probes.PROBES:
        assert callable(probe)


def _repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """CLAUDE_PROJECT_DIR で指させる作業ツリーを 1 つ作る。

    git init しないのは、probe が git を呼ばずに環境変数だけで根を決める規約だからである。
    git を呼ぶ形にすると、フックの cwd がリポ外だったときの挙動がテストから見えなくなる。
    """
    root = tmp_path / "repo"
    root.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    return root


def test_hidari_が無ければ対象外として健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _repo(tmp_path, monkeypatch)

    result = guard_probes.probe_private_ops()

    assert result.healthy is True
    assert result.detail == ""


def test_private_ops_が解決すれば健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    target = tmp_path / "cloud" / "private-ops"
    target.mkdir(parents=True)
    (root / ".hidari").mkdir()
    (root / ".hidari" / "private-ops").symlink_to(target)

    result = guard_probes.probe_private_ops()

    assert result.healthy is True


def test_hidari_はあるのに_private_ops_が無ければ沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = _repo(tmp_path, monkeypatch)
    (root / ".hidari").mkdir()

    result = guard_probes.probe_private_ops()

    assert result.healthy is False
    assert "private-ops" in result.detail


def test_symlink_が切れていれば沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _repo(tmp_path, monkeypatch)
    (root / ".hidari").mkdir()
    (root / ".hidari" / "private-ops").symlink_to(tmp_path / "gone")

    result = guard_probes.probe_private_ops()

    assert result.healthy is False


def test_通常ファイルが_symlink_の代わりに置かれていれば沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """exists() は通常ファイルでも真になるので、それだけでは取り付け済みと区別できない。

    この状態では cat が指示のファイルへ到達できず、指示は載らない。probe が健全と
    答えると、検出層が存在する意味を失う。取り付け側 (repo-wiring の is_wired) は
    symlink であることを見ているので、検出側だけが緩いという非対称でもある。
    """
    root = _repo(tmp_path, monkeypatch)
    (root / ".hidari").mkdir()
    (root / ".hidari" / "private-ops").write_text("")

    result = guard_probes.probe_private_ops()

    assert result.healthy is False
    assert "private-ops" in result.detail


def test_CLAUDE_PROJECT_DIR_が無ければ対象外として健全(monkeypatch: pytest.MonkeyPatch) -> None:
    """フックの cwd がリポ外のときの実運用状態。_project_root() が None を返す枝を測る。

    他のテストはすべて _repo() 経由で CLAUDE_PROJECT_DIR を設定するため、これを欠いたまま
    走らせないとこの枝は一度も実行されない。healthy=False へ変異させても全体が緑のまま
    通り得る。
    """
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)

    result = guard_probes.probe_private_ops()

    assert result.healthy is True
    assert result.detail == ""


def test_登録簿は名前の集合で_pin_する() -> None:
    """件数ではなく名前で見る。件数だけだと差し替えを見逃す。"""
    assert {name for name, _ in guard_probes.PROBES} == {
        "apm",
        "tirith",
        "private-ops",
        "task-list-id",
        "herdr-pane",
    }


def _git_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """CLAUDE_PROJECT_DIR で指させる git の作業ツリーを 1 つ作る。"""
    root = make_git_repo(tmp_path / "myrepo")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(root))
    return root


def test_タスクリスト識別子がリポジトリ名と一致すれば健全(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    _git_project(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "myrepo")

    result = guard_probes.probe_task_list_id()

    assert result.healthy is True
    assert result.detail == ""


def test_タスクリスト識別子が食い違えば両方の値を添えて沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """汚染された値は空でも不正でもなく、実在する別プロジェクトの名前である。

    どちらが宣言でどちらが導出かを文面が持たないと、受け取った側はどちらへ寄せるべきか
    決められない。
    """
    _git_project(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "someone-elses-project")

    result = guard_probes.probe_task_list_id()

    assert result.healthy is False
    assert "someone-elses-project" in result.detail
    assert "myrepo" in result.detail


def test_食い違いの文面は前置での明示指定にも触れる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """前置での明示指定はランチャの仕様なので、汚染していなくてもここへ到達する。

    プローブからは汚染と明示を区別できない。文面が汚染だけを断定すると、正しく明示した
    ユーザーが毎回「起動し直せ」と言われ、しかも起動し直しても同じ告知が出る。
    """
    _git_project(tmp_path, monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "someone-elses-project")

    assert "前置" in guard_probes.probe_task_list_id().detail


def test_タスクリスト識別子が未設定なら対象外として健全(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """ランチャを通さない起動では設定されない。既定に任せている状態なので汚染ではない。"""
    _git_project(tmp_path, monkeypatch)
    monkeypatch.delenv("CLAUDE_CODE_TASK_LIST_ID", raising=False)

    result = guard_probes.probe_task_list_id()

    assert result.healthy is True
    assert result.detail == ""


def test_導出はサブディレクトリでもリポジトリルートの名前を返す(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """導出を直接見る。プローブ越しでは worktree の許容が壊れた導出を救ってしまう。

    プローブは「本体の作業ツリーの名前」も正解として通すので、導出がサブディレクトリの名前を
    返すよう壊れても、通常のリポジトリでは本体名と一致して健全のまま通る。導出の規則を pin
    するには、許容の手前にあるこの関数を直接呼ぶしかない。
    """
    root = _git_project(tmp_path, monkeypatch)
    deep = root / "frontend" / "src"
    deep.mkdir(parents=True)

    assert guard_probes.derive_task_list_id(deep) == "myrepo"


def test_リポジトリのサブディレクトリでもルートの名前で判定する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """サブディレクトリの名前で判定すると、正しいセッションを汚染として報告する。"""
    root = _git_project(tmp_path, monkeypatch)
    deep = root / "frontend" / "src"
    deep.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(deep))
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "myrepo")

    assert guard_probes.probe_task_list_id().healthy is True


def test_git_の作業ツリー外では作業ディレクトリの名前で判定する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    plain = tmp_path / "plain-dir"
    plain.mkdir()
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(plain))
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "plain-dir")

    assert guard_probes.probe_task_list_id().healthy is True


def test_CLAUDE_PROJECT_DIR_が無ければフックの作業ディレクトリから導出する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """他のテストはすべて CLAUDE_PROJECT_DIR を設定するため、この枝は一度も通らない。

    本番では settings.json 側が git のルートへフォールバックしているので、環境変数が
    無い経路は実在する。
    """
    plain = tmp_path / "plain-dir"
    plain.mkdir()
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    monkeypatch.chdir(plain)
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "plain-dir")

    assert guard_probes.probe_task_list_id().healthy is True


def test_symlink_経由で入っても同じ識別子へ解決する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """`.zshrc` 側が pwd -P で実体へ寄せるので、こちらも寄せないと経路違いを汚染と読む。"""
    real = tmp_path / "real-dir"
    real.mkdir()
    link = tmp_path / "link-dir"
    link.symlink_to(real)
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(link))
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "real-dir")

    assert guard_probes.probe_task_list_id().healthy is True


def _worktree(root: Path, name: str) -> Path:
    """root の linked worktree を 1 つ作って返す。"""
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"],
        cwd=root,
        check=True,
        capture_output=True,
        env={**git_scope_free_env(), "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com"},
    )
    worktree = root.parent / name
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", name, str(worktree)],
        cwd=root,
        check=True,
        capture_output=True,
        env=git_scope_free_env(),
    )
    return worktree


def test_worktree_では本体の名前を名乗っても健全(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """worktree のセッションは環境変数を親から引き継ぐことがあり、宣言値が本体の名前になる。

    worktree の名前だけを正解にすると、正しいセッションを汚染として報告する。
    """
    root = _git_project(tmp_path, monkeypatch)
    worktree = _worktree(root, "wt-feature")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(worktree))
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "myrepo")

    assert guard_probes.probe_task_list_id().healthy is True


def test_worktree_で自分の名前を名乗っても健全(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """ランチャ経由で worktree の中から起動すると、宣言値は worktree の名前になる。"""
    root = _git_project(tmp_path, monkeypatch)
    worktree = _worktree(root, "wt-feature")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(worktree))
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "wt-feature")

    assert guard_probes.probe_task_list_id().healthy is True


def test_worktree_で第三の名前を名乗れば沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, git_location_vars_stripped: None
) -> None:
    """worktree の許容は 2 つの正解を足すだけで、汚染の検出を緩めない。"""
    root = _git_project(tmp_path, monkeypatch)
    worktree = _worktree(root, "wt-feature")
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(worktree))
    monkeypatch.setenv("CLAUDE_CODE_TASK_LIST_ID", "someone-elses-project")

    assert guard_probes.probe_task_list_id().healthy is False


def _fake_herdr(path: Path, stdout: str = "", exit_code: int = 0) -> Path:
    """指定の標準出力と exit code を返す偽 herdr を作る。"""
    path.write_text(
        f"#!/bin/sh\ncat <<'HERDR_PROBE_JSON'\n{stdout}\nHERDR_PROBE_JSON\nexit {exit_code}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _pane_list(*pane_ids: str) -> str:
    """herdr pane list の応答を、pane_id だけ持つ最小の形で組む。"""
    return json.dumps(
        {"result": {"type": "pane_list", "panes": [{"pane_id": p} for p in pane_ids]}}
    )


def test_HERDR_PANE_ID_が未設定なら対象外として健全(monkeypatch: pytest.MonkeyPatch) -> None:
    """herdr の外で起動したセッション。判定する対象がそもそも無い。"""
    monkeypatch.delenv("HERDR_PANE_ID", raising=False)

    result = guard_probes.probe_herdr_pane()

    assert result.healthy is True
    assert result.detail == ""


def test_pane_が一覧に含まれれば健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_herdr(tmp_path / "herdr", _pane_list("wA:p1", "wA:p2"))
    monkeypatch.setenv("HERDR_BIN_PATH", str(fake))
    monkeypatch.setenv("HERDR_PANE_ID", "wA:p2")

    result = guard_probes.probe_herdr_pane()

    assert result.healthy is True
    assert result.detail == ""


def test_pane_が一覧に無ければ沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """閉じられたペインを指したままだと、エージェントの状態通知が黙って捨てられる。"""
    fake = _fake_herdr(tmp_path / "herdr", _pane_list("wA:p1"))
    monkeypatch.setenv("HERDR_BIN_PATH", str(fake))
    monkeypatch.setenv("HERDR_PANE_ID", "wZ:p9")

    result = guard_probes.probe_herdr_pane()

    assert result.healthy is False
    assert "wZ:p9" in result.detail


def test_herdr_が見つからなければ対象外として健全(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """herdr を使わない環境で常に鳴らせば、この層ごと読まれなくなる。"""
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.delenv("HERDR_BIN_PATH", raising=False)
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("HERDR_PANE_ID", "wA:p1")

    result = guard_probes.probe_herdr_pane()

    assert result.healthy is True
    assert result.detail == ""


def test_herdr_が応答しなければ沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """あるのに答えないのは対象外ではない。判定できなかったことを健全へ潰さない。

    一覧としては読めて、しかも pane が載っている応答を返させる。読めない応答を返させると、
    終了コードを見ない実装でも後段のパースが同じ healthy=False を返すので、この検査が
    終了コードを見ているかを測れない (変異が下流に吸収される)。
    """
    fake = _fake_herdr(tmp_path / "herdr", _pane_list("wA:p1"), exit_code=1)
    monkeypatch.setenv("HERDR_BIN_PATH", str(fake))
    monkeypatch.setenv("HERDR_PANE_ID", "wA:p1")

    result = guard_probes.probe_herdr_pane()

    assert result.healthy is False
    assert "wA:p1" in result.detail


def test_pane_一覧が読めない形なら沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """応答の形が変わったときに「一覧に無い」と誤って断定しない。

    healthy が False であることだけを見ると、「読めない」と「一覧に無い」が同じ値に潰れて
    区別できない。実装が誤って不在を断定するようになっても緑で通るので、文面まで見る。
    """
    fake = _fake_herdr(tmp_path / "herdr", "not json at all")
    monkeypatch.setenv("HERDR_BIN_PATH", str(fake))
    monkeypatch.setenv("HERDR_PANE_ID", "wA:p1")

    result = guard_probes.probe_herdr_pane()

    assert result.healthy is False
    assert "実在は未確認" in result.detail
    assert "実在しないペイン" not in result.detail
