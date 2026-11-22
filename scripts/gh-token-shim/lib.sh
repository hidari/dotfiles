# shellcheck shell=bash
# =============================================================================
# gh-token-shim の共有判定層 (source 専用。実行しない)
# bash 3.2 互換を保つ (連想配列・${var,,}・mapfile は使わない)
# =============================================================================

# gh api のフラグが次の語を値として取るなら rc 0。gh api の --help (gh 2.102.0) の
# FLAGS から導いた。-h は gh api では定義が無い (ヘルプではない)
_ghts_api_flag_takes_value() {
    case "$1" in
    -X | --method | -f | -F | --field | --raw-field | --input | -H | --header | -q | --jq | -t | --template | --cache | --hostname | -p | --preview)
        return 0
        ;;
    esac
    return 1
}

# graphql のクエリ本文 (小文字にしたもの) が mutation を語として含むかを見る。
# 部分一致では mutationCount のようなフィールド名に当たる
_GHTS_MUTATION_RE='(^|[^a-z0-9_])mutation([^a-z0-9_]|$)'

# gh api の引数を分類して GHTS_CLASS に read/write のいずれかを入れる。
# 判定: -X/--method (連結形を含む) が GET/HEAD 以外なら write、明示が無ければ
# フィールド系フラグか --input があれば write。graphql はクエリ本文が読み取りで
# ある限りフィールドを書き込みとみなさない (変数の受け渡しに -f/-F を使うため)。
# 中身を読めない query=@file と --input は書き込みとみなす。
# query= の中身を見るのは graphql だけ (REST では query はただの検索語)。
_ghts_classify_api() {
    local seen_api=0 method="" has_field=0 has_input=0 is_graphql=0 query_mutates=0
    local a val

    while [ $# -gt 0 ]; do
        a=$1
        shift
        # 先頭の api より前のフラグ・サブコマンド自身は読み飛ばす
        if [ "$seen_api" -eq 0 ]; then
            case "$a" in
            -*) ;;
            *) seen_api=1 ;;
            esac
            continue
        fi

        val=""
        case "$a" in
        -X | --method)
            method=${1-}
            if [ $# -gt 0 ]; then shift; fi
            continue
            ;;
        --method=*)
            method=${a#--method=}
            continue
            ;;
        -X?*)
            method=${a#-X}
            continue
            ;;
        -f | -F | --field | --raw-field)
            has_field=1
            val=${1-}
            if [ $# -gt 0 ]; then shift; fi
            ;;
        --field=* | --raw-field=*)
            has_field=1
            val=${a#*=}
            ;;
        -f?* | -F?*)
            has_field=1
            val=${a#-?}
            ;;
        --input)
            has_input=1
            if [ $# -gt 0 ]; then shift; fi
            continue
            ;;
        --input=*)
            has_input=1
            continue
            ;;
        -*)
            # 値を取るその他のフラグ。値をエンドポイントと取り違えない
            if _ghts_api_flag_takes_value "$a" && [ $# -gt 0 ]; then shift; fi
            continue
            ;;
        *)
            if [ "$a" = graphql ]; then is_graphql=1; fi
            continue
            ;;
        esac

        # ここへ来るのはフィールド系のみ。query の中身で mutation を見る。
        # graphql かどうかはここでは決めない (エンドポイントがフィールドより後ろに来うる)
        case "$val" in
        query=@*) query_mutates=1 ;;
        query=*)
            _ghts_lower_into "${val#query=}"
            if [[ $_GHTS_LOWER =~ $_GHTS_MUTATION_RE ]]; then query_mutates=1; fi
            ;;
        esac
    done

    if [ "$is_graphql" -eq 1 ] && { [ "$query_mutates" -eq 1 ] || [ "$has_input" -eq 1 ]; }; then
        GHTS_CLASS="write"
        return 0
    fi

    # メソッドは大文字小文字を問わない
    case "$method" in
    [Gg][Ee][Tt] | [Hh][Ee][Aa][Dd]) GHTS_CLASS="read" ;;
    "")
        if [ "$has_input" -eq 1 ]; then
            GHTS_CLASS="write"
        elif [ "$has_field" -eq 1 ] && [ "$is_graphql" -eq 0 ]; then
            GHTS_CLASS="write"
        else
            GHTS_CLASS="read"
        fi
        ;;
    *) GHTS_CLASS="write" ;;
    esac
    return 0
}

# ghts_scan が読んだサブコマンド・動詞・その次の語から GHTS_CLASS を決める。
# 引数は gh の引数そのもの (gh api の分類だけが使う)。
# 書き込みの組、管理の組の順に引き、どちらにも無い組み合わせは read。
# --help / -h が付いた書き込みと管理の操作は read へ下げる。gh はヘルプを出すだけで
# 何も実行しないので、承認を求めるのも管理の操作として断るのも意味がない。
# none まで下げないのは、ヘルプの見分けを誤ったときにトークン無しで委譲しないため
# (トークン無しの gh は保存済みのログインで動く)。
_ghts_classify_scanned() {
    local key="$_GHTS_SUB/$_GHTS_VERB"
    case "$_GHTS_SUB" in
    "" | version | help | completion | auth)
        GHTS_CLASS="none"
        return 0
        ;;
    api)
        _ghts_classify_api "$@"
        return 0
        ;;
    esac

    # この2つの動詞は、次の語がさらに動詞になる
    case "$key" in
    repo/deploy-key | repo/autolink) key="$key/$_GHTS_VERB2" ;;
    esac
    case "$key" in
    pr/merge | \
        release/create | release/upload | release/delete | release/delete-asset | release/edit | \
        repo/sync | \
        workflow/run | workflow/enable | workflow/disable | \
        run/rerun | run/cancel | run/delete | \
        secret/set | secret/delete | secret/remove | \
        variable/set | variable/delete | variable/remove | \
        cache/delete)
        GHTS_CLASS="write"
        ;;
    repo/create | repo/delete | repo/edit | repo/rename | repo/archive | repo/unarchive | repo/fork | \
        repo/deploy-key/add | repo/deploy-key/delete | \
        repo/autolink/create | repo/autolink/delete)
        GHTS_CLASS="admin"
        ;;
    *)
        GHTS_CLASS="read"
        return 0
        ;;
    esac

    if [ "$_GHTS_ARGS_HELP" -eq 1 ]; then GHTS_CLASS="read"; fi
    return 0
}

# 持ち主 (owner) として許す名前。先頭は英数字、全体で39文字まで
_GHTS_OWNER_RE='^[A-Za-z0-9]([A-Za-z0-9-]{0,38})$'

ghts_valid_owner() {
    [[ ${1-} =~ $_GHTS_OWNER_RE ]]
}

# ASCII の英大文字を小文字にした値を _GHTS_LOWER へ入れる。呼ぶたびに子プロセスを
# 作らないよう、出力ではなく変数で返す。大文字が無ければ置換は回さない
_ghts_lower_into() {
    local pair
    _GHTS_LOWER=$1
    case "$_GHTS_LOWER" in
    *[ABCDEFGHIJKLMNOPQRSTUVWXYZ]*) ;;
    *) return 0 ;;
    esac
    for pair in Aa Bb Cc Dd Ee Ff Gg Hh Ii Jj Kk Ll Mm Nn Oo Pp Qq Rr Ss Tt Uu Vv Ww Xx Yy Zz; do
        _GHTS_LOWER=${_GHTS_LOWER//${pair%?}/${pair#?}}
    done
    return 0
}

# 小文字にしたホスト名が github.com のものなら rc 0。完全一致で見る
# (前方一致では github.com.<別ドメイン> が通る)
_ghts_is_github_host() {
    case "$1" in
    github.com | www.github.com) return 0 ;;
    esac
    return 1
}

# github.com の URL からホストより後ろ (owner/repo...) を小文字で出す。
# github.com のものでなければ rc 1。受ける形: scp 形式、ssh://、http(s):// (www. 付きを含む)。
_ghts_github_url_rest() {
    # host を変数に切り出すのは、リテラルの ssh://git@host/ が gitleaks の
    # email-address に当たるのを避けるため
    local host=github.com u rest authority
    _ghts_lower_into "$1"
    u=$_GHTS_LOWER
    case "$u" in
    git@"$host":*)
        printf '%s\n' "${u#git@"$host":}"
        return 0
        ;;
    ssh://* | http://* | https://*) ;;
    *) return 1 ;;
    esac

    rest=${u#*://}
    case "$rest" in
    */*)
        authority=${rest%%/*}
        rest=${rest#*/}
        ;;
    *)
        authority=$rest
        rest=""
        ;;
    esac
    case "$u" in
    ssh://*)
        [ "$authority" = "git@$host" ] || return 1
        ;;
    *)
        _ghts_is_github_host "$authority" || return 1
        ;;
    esac
    printf '%s\n' "$rest"
}

# github.com の remote / Web の URL から小文字の owner を出す。それ以外は空。
# 検証はしない (呼び出し側が ghts_valid_owner で行う)。
ghts_owner_from_url() {
    local rest
    rest=$(_ghts_github_url_rest "$1") || return 0
    printf '%s\n' "${rest%%/*}"
}

# -R / --repo の値 (OWNER/REPO, HOST/OWNER/REPO, URL) から小文字の owner を出す。
# HOST が github.com のものでなければ何も出さない (読めない名指しとして扱わせる)
ghts_owner_from_repo_spec() {
    local spec=$1 slashes
    case "$spec" in
    *://* | git@*)
        ghts_owner_from_url "$spec"
        return 0
        ;;
    esac
    slashes=${spec//[^\/]/}
    if [ "${#slashes}" -ge 2 ]; then
        # HOST/OWNER/REPO は先頭の host を確かめてから落とす
        _ghts_lower_into "${spec%%/*}"
        _ghts_is_github_host "$_GHTS_LOWER" || return 0
        spec=${spec#*/}
    fi
    _ghts_lower_into "${spec%%/*}"
    [ -n "$_GHTS_LOWER" ] && printf '%s\n' "$_GHTS_LOWER"
    return 0
}

# gh api のエンドポイントが持ち主を名指す形なら rc 0。
# 完全な URL (ホストを問わない) か、repos/ orgs/ users/ で始まるパス。
# ただしパスの持ち主がプレースホルダ {owner} のものは除く
_ghts_endpoint_names_owner() {
    local ep=$1 owner
    case "$ep" in
    *://*) return 0 ;;
    esac
    ep=${ep#/}
    ep=${ep%%\?*}
    case "$ep" in
    repos/* | orgs/* | users/*)
        owner=${ep#*/}
        # {owner} は gh が現在のリポジトリ (GH_REPO / cwd) で埋める。名指しではない
        [ "${owner%%/*}" = '{owner}' ] && return 1
        return 0
        ;;
    esac
    return 1
}

# gh api のエンドポイントから owner を出す。repos/O/.. orgs/O/.. users/U のみ。
# 完全な URL は api.github.com のものだけを読む (他のホストは空)
_ghts_owner_from_endpoint() {
    local ep=$1 authority kind rest
    case "$ep" in
    *://*)
        _ghts_lower_into "$ep"
        case "$_GHTS_LOWER" in
        http://* | https://*) ;;
        *) return 0 ;;
        esac
        authority=${_GHTS_LOWER#*://}
        authority=${authority%%/*}
        [ "$authority" = api.github.com ] || return 0
        rest=${ep#*://}
        case "$rest" in
        */*) ep=${rest#*/} ;;
        *) return 0 ;;
        esac
        ;;
    esac
    ep=${ep#/}
    # クエリ文字列は持ち主の一部ではない (orgs/acme?per_page=1)
    ep=${ep%%\?*}
    kind=${ep%%/*}
    case "$ep" in
    */*) rest=${ep#*/} ;;
    *) rest="" ;;
    esac
    case "$kind" in
    repos | orgs | users)
        _ghts_lower_into "${rest%%/*}"
        [ -n "$_GHTS_LOWER" ] && printf '%s\n' "$_GHTS_LOWER"
        ;;
    esac
    return 0
}

# gh api 以外のフラグが、サブコマンドと動詞の文脈で次の語を値として取るなら rc 0。
# 値を位置引数に数えると、--body の先頭の URL や repo sync -b の枝名を持ち主の名指しと
# 取り違える。連結形 (--flag=value, -bmain) は1語で完結するので、ここには当たらない。
# -R / --repo は持ち主の解決元なので呼び出し側が先に処理する。
#
# gh 2.102.0 の各サブコマンドの --help の FLAGS から導いた。長い名前は、書き込みの動詞の
# ものと、値が URL やスラッシュ入りの語になりうるものを載せる。載っていないフラグの値は
# 位置引数に数える。
# 短縮形は動詞ごとに意味が変わる (pr merge の -s は --squash、pr list の -s は --state)。
# 値を取らない文脈で次の語を読み飛ばすと、pr merge -s <URL> の名指しを落として
# origin の持ち主として昇格する。
_ghts_flag_takes_value() {
    local ctx="$1/$2" flag=$3
    case "$flag" in
    --comment)
        [ "$ctx" != pr/review ]
        return
        ;;
    --json)
        [ "$ctx" != workflow/run ]
        return
        ;;
    --source)
        case "$ctx" in
        repo/list | repo/ls) return 1 ;;
        esac
        return 0
        ;;
    --template)
        [ "$ctx" != repo/edit ]
        return
        ;;
    --body | --body-file | --title | --subject | --notes | --notes-file | --notes-start-tag | \
        --search | --jq | --base | --head | --branch | --description | --homepage | \
        --label | --assignee | --reviewer | --milestone | --project | --limit | --author | \
        --author-email | --state | --env | --env-file | --workflow | --commit | --job | \
        --match-head-commit | --discussion-category | --target | --tag | --ref | \
        --field | --raw-field | --app | --org | --visibility | --duplicate-of)
        return 0
        ;;
    # どの動詞でも値を取る短縮形
    -A | -B | -D | -F | -H | -L | -O | -S | -T | -b | -g | -i | -j | -k | -n | -o | -q | -t)
        return 0
        ;;
    # 以下は動詞で変わる短縮形。値を取らない文脈を挙げ、それ以外は値を取るとみなす
    -a)
        case "$ctx" in
        cache/delete | pr/review | run/list | run/ls | workflow/list | workflow/ls) return 1 ;;
        esac
        return 0
        ;;
    -c)
        case "$ctx" in
        issue/develop | issue/view | pr/review | pr/status | pr/view | repo/create | repo/new) return 1 ;;
        esac
        return 0
        ;;
    -d)
        case "$ctx" in
        pr/close | pr/create | pr/new | pr/list | pr/ls | pr/merge | pr/revert | \
            release/create | release/new | run/rerun) return 1 ;;
        esac
        return 0
        ;;
    -e)
        case "$ctx" in
        issue/comment | issue/create | issue/new | pr/comment | pr/create | pr/new) return 1 ;;
        esac
        return 0
        ;;
    -l)
        [ "$ctx" != issue/develop ]
        return
        ;;
    -m | -s)
        [ "$ctx" != pr/merge ]
        return
        ;;
    -p)
        case "$ctx" in
        release/create | release/new | ruleset/*) return 1 ;;
        esac
        return 0
        ;;
    -r)
        case "$ctx" in
        pr/merge | pr/review) return 1 ;;
        esac
        return 0
        ;;
    # 以下は値を取る文脈のほうが少ない短縮形。値を取る文脈を挙げる
    -f)
        case "$ctx" in
        secret/set | variable/set | workflow/run) return 0 ;;
        esac
        ;;
    -h)
        # ほかの動詞ではヘルプ。repo create / edit では --homepage
        case "$ctx" in
        repo/create | repo/new | repo/edit) return 0 ;;
        esac
        ;;
    -u)
        case "$ctx" in
        repo/clone | run/list | run/ls) return 0 ;;
        esac
        ;;
    -v)
        case "$ctx" in
        secret/set | variable/set) return 0 ;;
        esac
        ;;
    -w)
        # ほかの動詞では --web
        case "$ctx" in
        run/list | run/ls) return 0 ;;
        esac
        ;;
    esac
    return 1
}

# gh の引数を1回なめて、分類と持ち主の解決元を決める。rc は常に 0。設定する変数:
#   GHTS_CLASS         none/read/write/admin のいずれか
#   GHTS_OWNER_SOURCE  持ち主の解決元のうち、最初に「ある」もの
#     args    引数が持ち主を名指している (読めるかどうかは問わない)
#     gh_repo 環境変数 GH_REPO が空でない
#     none    どちらも無い (cwd の origin を見るかどうかは呼び出し側が決める)
#   GHTS_ARGS_OWNER    引数から読めた小文字の owner (読めなければ空)
# 分類と持ち主が同じサブコマンドと動詞を見るよう、両方をここで決める。別々に数えると、
# -R の値やフラグの値を片方だけが動詞に数え、書き込みを読み取りとして通す。
# gh api 以外では、--help / -h がフラグとして立っているかも見る。フラグの値として
# 渡された --help (--body --help) は数えない。
# 「ある」と「読めた」を分けるのは、名指しはあるのに読めない引数 (-R /x など) を
# 「引数に指定が無い」と同じに扱うと、呼び出し側が次の解決元の持ち主で昇格するため。
# 引数の中の優先順: 1 -R/--repo、2 api のエンドポイント、2' その他の位置引数
ghts_scan() {
    local args=("$@") i=0 n=$# a rest
    local has_repo=0 repo="" sub="" verb="" endpoint="" pos=0 pos_present=0 cand=""
    # 分類は空で始める。決まる前に読まれても none (トークン無しの委譲) にはならない
    GHTS_CLASS=""
    GHTS_OWNER_SOURCE=""
    GHTS_ARGS_OWNER=""
    _GHTS_VERB2=""
    _GHTS_ARGS_HELP=0

    while [ "$i" -lt "$n" ]; do
        a=${args[$i]}
        i=$((i + 1))
        case "$a" in
        -R | --repo)
            has_repo=1
            if [ "$i" -lt "$n" ]; then
                repo=${args[$i]}
                i=$((i + 1))
            fi
            continue
            ;;
        --repo=*)
            has_repo=1
            repo=${a#--repo=}
            continue
            ;;
        -R?*)
            has_repo=1
            repo=${a#-R}
            continue
            ;;
        esac

        if [ "$sub" = api ]; then
            case "$a" in
            -*)
                # 値を取るフラグ。値をエンドポイントと取り違えない
                if _ghts_api_flag_takes_value "$a"; then i=$((i + 1)); fi
                continue
                ;;
            esac
            if [ -z "$endpoint" ]; then endpoint=$a; fi
            continue
        fi

        case "$a" in
        -*)
            # 値を取るフラグ。値を位置引数と取り違えない
            if _ghts_flag_takes_value "$sub" "$verb" "$a"; then
                i=$((i + 1))
            elif [ "$a" = --help ] || [ "$a" = -h ]; then
                _GHTS_ARGS_HELP=1
            fi
            continue
            ;;
        esac
        pos=$((pos + 1))
        case "$pos" in
        1)
            sub=$a
            continue
            ;;
        2)
            verb=$a
            continue
            ;;
        3) _GHTS_VERB2=$a ;;
        esac
        if [ "$pos_present" -eq 0 ]; then
            # サブコマンドと動詞の後ろの位置引数だけを対象にする。
            # github.com の URL はどのサブコマンドでも持ち主の名指しとみなす。それ以外の
            # URL やスラッシュ入りの語は、ブランチ名・パス・フラグの値と区別できない
            if rest=$(_ghts_github_url_rest "$a"); then
                pos_present=1
                cand=${rest%%/*}
            elif [ "$sub" = repo ] && [ "$pos" -eq 3 ]; then
                # repo サブコマンドの動詞直後はリポジトリの名指し (形を問わない)。
                # 下の動詞は次の語がさらに動詞か名前で、リポジトリではない
                case "$verb" in
                deploy-key | autolink | gitignore | license) ;;
                *)
                    pos_present=1
                    case "$a" in
                    */*) cand=$(ghts_owner_from_repo_spec "$a") ;;
                    esac
                    ;;
                esac
            fi
        fi
    done

    if [ "$has_repo" -eq 1 ]; then
        GHTS_OWNER_SOURCE=args
        GHTS_ARGS_OWNER=$(ghts_owner_from_repo_spec "$repo")
    elif [ "$sub" = api ]; then
        if [ -n "$endpoint" ] && _ghts_endpoint_names_owner "$endpoint"; then
            GHTS_OWNER_SOURCE=args
            GHTS_ARGS_OWNER=$(_ghts_owner_from_endpoint "$endpoint")
        fi
    elif [ "$pos_present" -eq 1 ]; then
        GHTS_OWNER_SOURCE=args
        GHTS_ARGS_OWNER=$cand
    fi
    if [ -z "$GHTS_OWNER_SOURCE" ]; then
        if [ -n "${GH_REPO:-}" ]; then
            GHTS_OWNER_SOURCE=gh_repo
        else
            GHTS_OWNER_SOURCE=none
        fi
    fi

    _GHTS_SUB=$sub
    _GHTS_VERB=$verb
    _ghts_classify_scanned "$@"
    return 0
}

# 以下の3つは ghts_scan の結果を1つずつ出す。rc は常に 0。
# 1回の起動で2つ以上要るときは ghts_scan を直接呼んで変数を読む (引数を何度もなめない)。

# 分類を1語で出す
ghts_classify() {
    ghts_scan "$@"
    echo "$GHTS_CLASS"
    return 0
}

# 引数から読めた持ち主を小文字で出す (読めなければ何も出さない)
ghts_owner_from_args() {
    ghts_scan "$@"
    [ -n "$GHTS_ARGS_OWNER" ] && printf '%s\n' "$GHTS_ARGS_OWNER"
    return 0
}

# 持ち主の解決元を1語で出す
ghts_owner_source() {
    ghts_scan "$@"
    echo "$GHTS_OWNER_SOURCE"
    return 0
}

# 設定ファイルを行ごとに読む。source はしない (値はリテラルのまま)。
# 設定する変数: GHTS_VAULT / GHTS_DEFAULT_OWNER / GHTS_OWNERS (小文字・空白区切り)
# GHTS_OWNERS は owner の行に加えて default_owner を含む
# vault と default_owner が揃い、全ての owner が正規表現に当たるとき rc 0
ghts_load_config() {
    local file=${1-} line key val
    GHTS_VAULT=""
    GHTS_DEFAULT_OWNER=""
    GHTS_OWNERS=""
    [ -r "$file" ] || return 1

    while IFS= read -r line || [ -n "$line" ]; do
        case "$line" in
        "" | "#"*) continue ;;
        *=*) ;;
        *) continue ;;
        esac
        key=${line%%=*}
        val=${line#*=}
        case "$key" in
        vault) GHTS_VAULT=$val ;;
        default_owner)
            ghts_valid_owner "$val" || return 1
            _ghts_lower_into "$val"
            GHTS_DEFAULT_OWNER=$_GHTS_LOWER
            ;;
        owner)
            ghts_valid_owner "$val" || return 1
            _ghts_lower_into "$val"
            GHTS_OWNERS="${GHTS_OWNERS:+$GHTS_OWNERS }$_GHTS_LOWER"
            ;;
        esac
    done <"$file"

    if [ -z "$GHTS_VAULT" ] || [ -z "$GHTS_DEFAULT_OWNER" ]; then
        return 1
    fi
    # 既定の持ち主は owner の行が無くても扱える持ち主に含める (重複はさせない)
    if ! ghts_has_owner "$GHTS_DEFAULT_OWNER"; then
        GHTS_OWNERS="${GHTS_OWNERS:+$GHTS_OWNERS }$GHTS_DEFAULT_OWNER"
    fi
    return 0
}

# GHTS_OWNERS (空白区切り) に含まれれば rc 0
ghts_has_owner() {
    local o
    [ -n "${1-}" ] || return 1
    for o in $GHTS_OWNERS; do
        [ "$o" = "$1" ] && return 0
    done
    return 1
}
