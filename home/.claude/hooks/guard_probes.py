"""セッションが正しい前提の上に乗っているかを見る述語と、その登録簿。

出発点は検査層の生存だった。PreToolUse の 2 つのガードは、どちらも自分が機能していない状態を
検出できない。検出できている箇所はあるが、射程が実態より狭い。この層はセッション頭でそれを
測るためのものである。

射程はそこから広がっている。運用指示が読めているか、掴んでいるタスクリストが作業ディレクトリと
整合しているか、といった「検査層ではないがセッションの前提にあたるもの」も述語に含む。判定は
対象が検査層かどうかではなく、壊れていても実行が続いてしまうかどうかで行う。

述語をここへ集めるのは、同じ判定を 2 箇所へ書くと片方だけ直したときに沈黙して食い違う
ためである。それはこの層が扱っている欠陥そのものなので、canonical を 1 つにする。

print と sys.exit は持たない。副作用を持ち込むとこの層だけを直接テストできなくなる
(pretooluse.py と同じ規則)。subprocess は持つので純関数ではない。

shim / tirith バイナリの解決そのものは guard_resolve.py (leaf) が持つ。あちらは
PreToolUse (強制層) がホットパスで import するため軽量に保つ必要があり、こちらは
SessionStart (セッションに 1 回) からしか呼ばれないので subprocess / dataclasses を
import してよい。

フックからは sys.path[0] (スクリプトのディレクトリ) 経由で解決される。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import guard_resolve
import hook_git

# tirith の応答検査に流すコマンド。副作用が無く、検出されないことを実測で確かめたもの。
# 検出される文字列を選ぶと監査カウンタの blocked が呼び出しごとに 1 増え、tirith が
# 働いているかを判断する材料そのものを、この検査が壊す (実測)。
TIRITH_PROBE_COMMAND = "ls -la"

# 応答検査のタイムアウト (秒)。通常の応答は数十ミリ秒のオーダーだが、この値は
# 「応答しない」を判定するための上限であって通常経路の待ち時間ではない。
TIRITH_PROBE_TIMEOUT = 5.0

# ペイン一覧の取得の上限 (秒)。同じく「応答しない」の判定に使う上限である。
HERDR_PROBE_TIMEOUT = 5.0


@dataclass(frozen=True)
class ProbeResult:
    """プローブ 1 件の結果。detail は沈黙しているときだけ意味を持つ。

    名前を持たないのは、登録簿が名前と関数の組で持つためである。プローブの呼び出し自体が
    例外で落ちたときにも名前が要るので、結果側ではなく登録簿側が名前を持つ。
    """

    healthy: bool
    detail: str = ""


def probe_apm() -> ProbeResult:
    """apm ガードの shim が実際に横取りする位置にあるか。

    フックが見る PATH を測っている。フックは Claude Code のプロセスから起動されるので、
    対話シェルの PATH に載っていても Claude Code の PATH に載っていなければ守っていない。

    Claude Code は PATH を自分で作らず、起動元のシェルから継承する。shim を PATH へ足す行が
    入るより前から生きているシェルから起動すると載らず、Claude Code だけを起動し直しても
    継承元が同じなので直らない (2026-08-31 に ps で祖先を辿って実測)。

    手当ての文面と、原因 2 通りのどちらを選ぶかは guard_resolve が持つ。強制層の deny も同じ
    ものを使う。
    """
    if guard_resolve.shim_resolves():
        return ProbeResult(healthy=True)
    return ProbeResult(
        healthy=False,
        detail=(
            f"PATH 上の apm が {guard_resolve.shim_path()} へ解決されないため、apm ガードは"
            "横取りしていない。フックが自力で捕まえる形 (素の apm / 絶対パス / PATH の一時"
            "差し替え) は deny されるが、包み込みや変数間接や xargs の形は無音で素通りする。"
            f"{guard_resolve.apm_remedy()}"
        ),
    )


def probe_tirith() -> ProbeResult:
    """tirith が解決し、clean なコマンドへ clean と応答するか。

    フックと同一のフラグと環境で呼ぶ (guard_resolve.tirith_child_env /
    tirith_check_argv)。呼び方が違うとデーモンを経由するかどうかが変わり、フックが通る
    経路とは別のものを測ることになる。

    「起動するが何も検出しない」状態はここでは覆わない。覆うには検出される文字列を流す
    陰性対照が要るが、それは監査カウンタの blocked を呼び出しごとに 1 増やし、tirith が
    働いているかを判断する材料そのものを壊す (実測)。
    """
    tirith_bin = guard_resolve.resolve_tirith_bin()

    try:
        result = subprocess.run(
            guard_resolve.tirith_check_argv(tirith_bin, TIRITH_PROBE_COMMAND),
            capture_output=True,
            text=True,
            timeout=TIRITH_PROBE_TIMEOUT,
            env=guard_resolve.tirith_child_env(),
        )
    except FileNotFoundError:
        if os.environ.get("TIRITH_BIN"):
            # 明示したパスが無い = 設定ミス。フックは fail-closed に倒れるので静かではないが、
            # 原因をここで名指しできる。
            return ProbeResult(
                healthy=False,
                detail=(
                    f"TIRITH_BIN={tirith_bin} が存在しないため、すべての Bash 呼び出しが "
                    "ブロックされる。パスを直すか TIRITH_BIN を解除する。"
                ),
            )
        return ProbeResult(
            healthy=False,
            detail=(
                f"{tirith_bin} が見つからないため、tirith の検査は沈黙している。"
                "コマンドは検査されないまま通る。"
                f"{guard_resolve.TIRITH_REMEDY_UNRESOLVED}"
            ),
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(
            healthy=False,
            detail=(
                f"{tirith_bin} が {TIRITH_PROBE_TIMEOUT} 秒以内に応答しないため、"
                "すべての Bash 呼び出しがブロックされる。"
            ),
        )
    except OSError as exc:
        return ProbeResult(
            healthy=False,
            detail=f"{tirith_bin} を起動できない ({exc})。すべての Bash 呼び出しがブロックされる。",
        )

    if result.returncode != 0:
        return ProbeResult(
            healthy=False,
            detail=(
                f"{tirith_bin} が無害なコマンドを clean と判定しない (exit {result.returncode})。"
                "この状態ではすべての Bash 呼び出しがブロックされる。"
            ),
        )
    return ProbeResult(healthy=True)


def _project_root() -> Path | None:
    """フックから見た作業ツリーの根。決められなければ None。

    git を呼ばず環境変数だけで決める。フックの cwd はリポ外のこともあり、そこで
    git を呼ぶと「リポではない」と「指示が無い」が同じ失敗の形をとる。
    """
    root = os.environ.get("CLAUDE_PROJECT_DIR")
    return Path(root) if root else None


def probe_private_ops() -> ProbeResult:
    """運用指示の実体へ到達できるか。

    .hidari/ の存在を opt-in マーカーとして使う。このディレクトリはユーザーが個人の
    メモを置く場所として全リポで運用しており、新しい状態を増やさずに「対象かどうか」を
    表せる。無いリポは対象外なので健全として通す。

    一覧は読まない。一覧は外部ストレージにあり到達経路がこの symlink なので、symlink が
    無いリポでは一覧そのものが読めない。読めない状態を沈黙として報告すると、対象外の
    リポで常に鳴ることになる。一覧との突き合わせは棚卸し側 (repo-wiring --check) が持つ。

    exists() は symlink を辿るので、切れたリンクは False になる。外部ストレージが
    未マウントで実体へ届かない状態もここで捕まる。ただし exists() だけでは通常
    ファイルも真になるため、symlink であることも併せて見る。取り付け側
    (repo-wiring の is_wired) が symlink を要求しているので、検出側だけが緩いと
    「取り付けは拒むが検出は沈黙する」非対称ができる。
    """
    root = _project_root()
    if root is None:
        return ProbeResult(healthy=True)

    hidari = root / ".hidari"
    if not hidari.is_dir():
        return ProbeResult(healthy=True)

    link = hidari / "private-ops"
    if link.is_symlink() and link.exists():
        return ProbeResult(healthy=True)

    return ProbeResult(
        healthy=False,
        detail=(
            f"{link} が解決しないため、このリポジトリの運用指示は読み込まれていない。"
            "外部ストレージが未マウントか、symlink が張られていない。"
            "repo-wiring を実行すると張り直せる。"
        ),
    )


def _session_directory() -> Path:
    """このセッションの作業ディレクトリ。決められなければフックの cwd に落とす。

    _project_root() と違って None を返さない。あちらは opt-in マーカーを探す側なので
    「対象かどうか分からない」を表す必要があるが、こちらは導出元が要るだけで、
    どのディレクトリで起動していても必ず 1 つ決まる。
    """
    return _project_root() or Path.cwd()


def derive_task_list_id(directory: str | Path) -> str:
    """作業ディレクトリからタスクリスト識別子を導出する。

    `.zshrc` の `_claude_task_list_id` と同じ規則で、git の作業ツリーならルートの名前、
    そうでなければ実体パスの名前になる。両者が同じ値を返すことは bats 側の対照テストが
    pin する。規則が 2 言語にまたがるので、片方を読んだだけでは食い違いに気づけない。

    先に実体パスへ寄せるのは、シェル側がフォールバックで `pwd -P` を使うためである。
    寄せないと、symlink 経由で入ったセッションを汚染として報告する。
    """
    return hook_git.repo_root(Path(directory).resolve()).name


def _main_worktree_name(directory: Path) -> str | None:
    """linked worktree が属する本体の作業ツリーの名前。決められなければ None。

    `--git-common-dir` は linked worktree でも本体の `.git` を返す (実測)。本体の中では
    自分の `.git` を返すので、どちらから呼んでも同じ値になる。

    導出そのものには使わない。シェル側は worktree の名前を返すので、こちらを導出値にすると
    同値でなくなる。ここで足すのは「本体の名前を名乗るセッションも正しい」という許容だけで、
    別プロジェクトの名前はどちらの正解にも当たらないため検出は緩まない。
    """
    common = hook_git.rev_parse(directory, "--git-common-dir")
    if common is None:
        return None

    # 相対で返ることがある。その場合は -C で渡した側から解決する。
    path = Path(common)
    if not path.is_absolute():
        path = directory / path
    return path.resolve().parent.name


def probe_task_list_id() -> ProbeResult:
    """CLAUDE_CODE_TASK_LIST_ID が作業ディレクトリと整合しているか。

    daemon は起動を速くするため事前にウォームした worker を claim して割り当てるが、
    claim で差し替わらない環境変数は worker を spawn した時点の値のまま残る。この変数は
    差し替わらない側にあるので、別プロジェクトで起こされた daemon の worker を掴むと
    そちらの名前を着たまま起動する。

    汚染された値は空でも不正でもなく実在する別プロジェクトの名前なので、タスク管理の
    ツールを使うとそのプロジェクトの生きたバックログへ書き込む。失敗がもっともらしい成功
    として返る形なので、使うまで気づけない。

    未設定は対象外として通す。ランチャを通さない起動では設定されず、その場合は Claude Code
    の既定に任せている状態であって汚染ではない。

    前置での明示指定 (`CLAUDE_CODE_TASK_LIST_ID=<名前> claude`) はランチャの仕様として
    支持されており、その起動でも導出値と食い違う。汚染と明示をここで区別する手段は無い。
    ランチャが目印を export しても spare 経由で同じように継承されるためである。区別できない
    以上は両方の可能性を文面へ書き、判断を読み手へ渡す。
    """
    declared = os.environ.get("CLAUDE_CODE_TASK_LIST_ID")
    if not declared:
        return ProbeResult(healthy=True)

    directory = _session_directory()
    expected = derive_task_list_id(directory)
    if declared == expected:
        return ProbeResult(healthy=True)

    if declared == _main_worktree_name(directory):
        return ProbeResult(healthy=True)

    return ProbeResult(
        healthy=False,
        detail=(
            f"CLAUDE_CODE_TASK_LIST_ID={declared} は、作業ディレクトリから導出される "
            f"{expected} と食い違う。起動時に前置で明示した覚えが無いなら、別プロジェクトの"
            "タスクリストを掴んでいる。タスク管理のツールを使う前に Claude Code を"
            "起動し直すこと。"
        ),
    )


# 継承した ID のうち、ペインの所属として一覧から照合できるもの。HERDR_PANE_ID は照合の起点
# なのでここには入らない。
_HERDR_MEMBERSHIP_IDS: tuple[tuple[str, str], ...] = (
    ("HERDR_TAB_ID", "tab_id"),
    ("HERDR_WORKSPACE_ID", "workspace_id"),
)


def _herdr_bin() -> str | None:
    """herdr の実体。herdr の中で起動していれば HERDR_BIN_PATH が指す。

    同じディレクトリの herdr-agent-state.sh は socket へ直接話しかけるが、あちらは herdr が
    統合を入れ直すたびに上書きする管理下のファイルである。上書きされる側の実装に合わせず、
    公開された CLI を使う。

    guard_resolve.resolve_tirith_bin と同じ形をしているが、あちらへは寄せない。canonical を
    1 つにする価値があるのは片方を直したときにもう片方が古びる情報で、HERDR_BIN_PATH と
    TIRITH_BIN は互いに独立している。guard_resolve は強制層がホットパスで import する leaf と
    して射程を apm と tirith に絞っており、herdr は強制層が使わない。失敗の返し方も違う
    (あちらは見つからなくても文字列を返して呼び出し側の FileNotFoundError へ委ねるが、こちらは
    None を返して対象外として通す)。
    """
    return os.environ.get("HERDR_BIN_PATH") or shutil.which("herdr")


def _herdr_unverified(pane_id: str, subject: str, reason: str) -> ProbeResult:
    """照合できなかったことを、何が確かめられなかったかとともに告げる。

    「確かめられなかった」と「食い違っている」を同じ文面にしない。前者は herdr 側の問題で、
    後者はセッション側の問題なので、読み手が取る手当てが違う。

    subject を呼び出し側から受けるのは、一覧そのものが引けない状態 (実在が不明) と、一覧は
    引けたがペインが所属を持たない状態 (所属が不明) を区別するためである。同じ文面へ潰すと、
    herdr が応答しないことと応答の形が変わったことが読み手から見て同じになる。
    """
    return ProbeResult(healthy=False, detail=f"{reason}。{pane_id} の{subject}は未確認。")


def probe_herdr_ids() -> ProbeResult:
    """継承した herdr の ID が同じペインを指しているか。

    これらの変数も claim で差し替わらない側にあり、既に閉じられたペインや別のセッションの
    ものを指すことがある。その場合はエージェントの状態通知が黙って捨てられ、ユーザーからは
    動いていないように見える。

    照合は HERDR_PANE_ID を起点にする。一覧の応答では各ペインが自分の tab_id と workspace_id を
    持つので、1 回の呼び出しで 3 つとも見られる。tab と workspace の一覧を別に引く形は採らない。
    呼び出しが増えるとセッション頭の待ちの上限がそのぶん伸びる。ペインを起点にすると、ペインを
    持たない workspace や tab が一覧に現れるかどうかにも依存しない。

    HERDR_PANE_ID が未設定なら何も見ない。3 つは herdr が同時に設定するので、起点が無い状態で
    残りだけを検査するには別の呼び出しが要る。tab と workspace が個別に未設定のときは、その
    変数だけを対象外として通す。

    herdr が設定する変数はこの 3 つだけではないが、残りは対象にしない (2026-09-07 に全数を
    確かめた)。在否のフラグ、socket の固定パス、バイナリのパスはいずれもセッションではなく
    マシンを指すので、spare 経由で継承されても汚染にならない。汚染が意味を持つのは、値が
    セッションごとに変わりかつ実在する別のものを指しうる識別子に限られる。

    未設定と herdr 不在は対象外として通す。herdr を使わない環境で常に鳴らすと、この層の
    出力そのものが読まれなくなる。あるのに応答しないのは対象外ではないので沈黙として扱う。
    """
    pane_id = os.environ.get("HERDR_PANE_ID")
    if not pane_id:
        return ProbeResult(healthy=True)

    herdr_bin = _herdr_bin()
    if not herdr_bin:
        return ProbeResult(healthy=True)

    try:
        result = subprocess.run(
            [herdr_bin, "pane", "list"],
            capture_output=True,
            text=True,
            timeout=HERDR_PROBE_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return _herdr_unverified(pane_id, "実在", f"{herdr_bin} がペイン一覧を返さない ({exc})")

    if result.returncode != 0:
        return _herdr_unverified(
            pane_id, "実在", f"{herdr_bin} がペイン一覧を返さない (exit {result.returncode})"
        )

    try:
        payload = json.loads(result.stdout)
    except ValueError as exc:
        return _herdr_unverified(
            pane_id, "実在", f"ペイン一覧を読めない ({exc})。応答の形が変わった"
        )

    # herdr は不在も誤用も exit 0 で返し、失敗は応答の中の error に入る (2026-09-07 実測)。
    # 終了コードだけを見ていると、この形が「応答した」として後段のパースへ流れる。
    error = payload.get("error") if isinstance(payload, dict) else None
    if error:
        return _herdr_unverified(pane_id, "実在", f"{herdr_bin} がエラーを返した ({error})")

    try:
        panes = payload["result"]["panes"]
        pane = next((entry for entry in panes if entry["pane_id"] == pane_id), None)
    except (LookupError, TypeError) as exc:
        return _herdr_unverified(
            pane_id, "実在", f"ペイン一覧を読めない ({exc})。応答の形が変わった"
        )

    if pane is None:
        return ProbeResult(
            healthy=False,
            detail=(
                f"HERDR_PANE_ID={pane_id} は実在しないペインを指している。"
                "エージェントの状態通知は届かないまま捨てられる。"
            ),
        )

    for var, key in _HERDR_MEMBERSHIP_IDS:
        declared = os.environ.get(var)
        if not declared:
            continue
        try:
            actual = pane[key]
        except LookupError as exc:
            # TypeError は並べない。ここへ来る pane は上の next() で pane_id の添字を通って
            # いるので dict に限られ、起こるのはキーの欠落だけである。到達しない型を書くと、
            # 読み手が「添字の通らない pane がここまで来る」と誤読する。
            return _herdr_unverified(
                pane_id, "所属", f"ペインの所属を読めない ({exc})。応答の形が変わった"
            )
        if declared != actual:
            return ProbeResult(
                healthy=False,
                detail=(
                    f"{var}={declared} は、{pane_id} が実際に属する {actual} と食い違う。"
                    "別のセッションの値を着たまま起動している。"
                ),
            )

    return ProbeResult(healthy=True)


# プローブの登録簿。名前を結果ではなくここが持つのは、プローブの呼び出し自体が例外で
# 落ちたときにも名前が要るためである。名前が無いと「検査できなかった」を報告できない。
PROBES: tuple[tuple[str, Callable[[], ProbeResult]], ...] = (
    ("apm", probe_apm),
    ("tirith", probe_tirith),
    ("private-ops", probe_private_ops),
    ("task-list-id", probe_task_list_id),
    ("herdr-ids", probe_herdr_ids),
)
