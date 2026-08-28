# shellcheck shell=bash
# apm install の可否判定。bootstrap.sh と PATH shim の両方が source する。
#
# 判定を 1 ファイルへ寄せているのは、同じ規則を 2 箇所に書くと片方だけ直したときの差が
# 「エラー」ではなく「判定の食い違い」として静かに現れるため。両者が同じ木に対して同じ答えを
# 返すことは scripts/claude-hooks/tests/test_apm_install_guard.py の cross-pin テストが見る。
#
# bash 専用である。read -r -d '' とプロセス置換と ${var:offset:length} を使うので、
# POSIX sh (macOS の /bin/sh を含む) では動かない。sh で source すると read -d が黙って
# 効かなくなり、dirty な木でブロッカー 0 件という「正常に見える結果」が返る。

# パスが apm install の入出力なら真。これらだけが変更された状態は正常な中間状態であり、
# 例外が無いと pin を更新するたびにガードが手順を止める。
apm_io_path() {
    case "${1##*/}" in
        apm.yml | apm.lock.yaml) return 0 ;;
    esac
    return 1
}

# apm install を阻む未コミットの変更を列挙する（1 行 1 パス。無ければ何も出さない）。
#
# apm install は deploy 先を rsync --delete 相当で書き換え、tracked file も黙って上書きし、
# パッケージに含まれないファイルを削除する。しかもログには (files unchanged) と出るため
# 差分に気づけない。ツリーが clean なら apm が何を壊しても git から戻せるので、目的は
# 破壊の防止ではなく復旧可能性の確保になる。この整理から検査範囲は deploy 先ではなく
# リポジトリ全体になる。
# git リポジトリでなければ「git から戻す」前提そのものが無いので検査しない。
# パスは NUL 区切りで受け取る。空白や日本語を含むパスを空白分割すると分断され、落ちた分は
# 「エラー」ではなく「短い正常な結果」として返るため出力を見ても気づけない。
# 検査できなかったときは 1 を返す。git の失敗を空出力へ潰すと clean と区別できず、
# bootstrap が新規マシン（git が壊れやすい環境）で無防備に apm install を走らせる。
apm_install_blockers() {
    local repo="$1"
    local entry status path from

    # リポジトリ外は検査対象外。この判定を先に置かないと、下の status 失敗検査が
    # 「リポジトリ外」を「検査できなかった」と取り違える。
    if ! git -C "$repo" rev-parse --show-toplevel > /dev/null 2>&1; then
        return 0
    fi
    # NUL 区切りの出力はコマンド置換では失われる（bash が NUL を捨てる）ためプロセス置換で
    # 読む。その形では git の exit code を受け取れないので、成否だけを別呼び出しで確かめる。
    if ! git -C "$repo" status --porcelain -z > /dev/null 2>&1; then
        return 1
    fi

    while IFS= read -r -d '' entry; do
        # porcelain の各エントリは "XY <path>" 形式。先頭 3 文字が状態フィールド
        status="${entry:0:2}"
        path="${entry:3}"
        from=""
        # rename と copy だけは "XY <to>\0<from>\0" の 2 チャンクで返る。from 側は状態
        # フィールドを持たないので、同じ規則で切ると実在しないパスになる。
        case "$status" in
            *R* | *C*) IFS= read -r -d '' from || from="" ;;
        esac
        # 1 つの記録が指すパスがすべて apm の入出力のときだけ許可する。移動先が apm.yml でも
        # 移動元が違えば、それは失われうる変更である。
        if apm_io_path "$path" && { [ -z "$from" ] || apm_io_path "$from"; }; then
            continue
        fi
        printf '%s\n' "$path"
    done < <(git -C "$repo" status --porcelain -z)
}

# 引数列が読み取り専用の apm 呼び出しなら真。
#
# 「止めるものを並べる」denylist ではなく「通すものを並べる」allowlist に置く。apm は
# pre-1.0 でサブコマンドが増え続けるため、denylist は上流が増えるたびに黙って穴が開き、
# しかも漏れは「何も起きない」形で返るのでガードの主張が偽になったことに気づけない。
# 通しすぎの失敗は「コミットするか stash する」という可視で安価な失敗で済む。
#
# 名前と性質の canonical はここではなく home/.claude/hooks/apm-install-guard.py の
# READONLY_COMMANDS で、両者が一致していることは scripts/claude-hooks/tests/
# test_apm_install_guard.py の cross-pin テストが見る。片方だけへ追加すると、差は「エラー」
# ではなく「片方の層だけが止める」という静かな食い違いとして出る。
# 1 要素 1 呼び出し。空白区切りはサブコマンドの語の並び（apm deps list など）。
# case の literal ではなく配列で持つのは、cross-pin テストが bash 側を列挙できるようにする
# ため。列挙できないと「Python 側の要素が bash でも真か」しか見られず、bash 側だけが広い
# という危険な向きの drift が素通りする（主網は shim = bash 側なので、そちらが広いと
# 破壊的なサブコマンドが検査なしで通る）。
APM_READONLY_COMMANDS=(
    audit
    doctor
    find
    list
    outdated
    policy
    preview
    search
    targets
    view
    "deps list"
    "deps tree"
)

apm_is_readonly_invocation() {
    local arg entry head=""
    local -a positional=()

    for arg in "$@"; do
        case "$arg" in
            -*) continue ;;
        esac
        positional+=("$arg")
    done

    # サブコマンドを伴わない呼び出し（apm / apm --help / apm --version）は help を出すだけ。
    if [ ${#positional[@]} -eq 0 ]; then
        return 0
    fi

    # 要素の語数だけ先頭から突き合わせる（Python 側の args[:len(readonly)] と同じ規則）。
    if [ ${#positional[@]} -ge 2 ]; then
        head="${positional[0]} ${positional[1]}"
    fi
    for entry in "${APM_READONLY_COMMANDS[@]}"; do
        if [ "$entry" = "${positional[0]}" ] || [ "$entry" = "$head" ]; then
            return 0
        fi
    done
    return 1
}
