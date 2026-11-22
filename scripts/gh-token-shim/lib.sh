# shellcheck shell=bash
# =============================================================================
# gh-token-shim の共有判定層 (source 専用。実行しない)
# bash 3.2 互換を保つ (連想配列・${var,,}・mapfile は使わない)
# =============================================================================

# gh api の引数を分類して none/read/write のいずれかを出す。
# 判定: -X/--method (連結形を含む) が GET/HEAD 以外なら write、明示が無ければ
# フィールド系フラグか --input があれば write。graphql はクエリ本文が読み取りで
# ある限りフィールドを書き込みとみなさない (変数の受け渡しに -f/-F を使うため)。
# 中身を読めない query=@file と --input は書き込みとみなす。
_ghts_classify_api() {
    local seen_api=0 method="" has_field=0 has_input=0 is_graphql=0 is_mutation=0
    local a val lowered

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
        # 値を取るその他のフラグ。値をエンドポイントと取り違えない
        -H | --header | -q | --jq | -t | --template | --cache | --hostname | -p | --preview)
            if [ $# -gt 0 ]; then shift; fi
            continue
            ;;
        -*) continue ;;
        *)
            if [ "$a" = graphql ]; then is_graphql=1; fi
            continue
            ;;
        esac

        # ここへ来るのはフィールド系のみ。query の中身で mutation を見る
        case "$val" in
        query=@*) is_mutation=1 ;;
        query=*)
            lowered=$(printf '%s' "${val#query=}" | tr '[:upper:]' '[:lower:]')
            case "$lowered" in
            *mutation*) is_mutation=1 ;;
            esac
            ;;
        esac
    done

    if [ "$is_mutation" -eq 1 ]; then
        echo write
        return 0
    fi
    if [ "$is_graphql" -eq 1 ] && [ "$has_input" -eq 1 ]; then
        echo write
        return 0
    fi

    method=$(printf '%s' "$method" | tr '[:lower:]' '[:upper:]')
    case "$method" in
    GET | HEAD) echo read ;;
    "")
        if [ "$has_input" -eq 1 ]; then
            echo write
        elif [ "$has_field" -eq 1 ] && [ "$is_graphql" -eq 0 ]; then
            echo write
        else
            echo read
        fi
        ;;
    *) echo write ;;
    esac
    return 0
}

# gh の引数を分類して none/read/write/admin のいずれか1語を出す。rc は常に 0。
# サブコマンドは最初の非フラグ、動詞はその次の非フラグ。未知の組み合わせは read。
ghts_classify() {
    local sub="" verb="" verb2="" a
    for a in "$@"; do
        case "$a" in
        -*) continue ;;
        esac
        if [ -z "$sub" ]; then
            sub=$a
        elif [ -z "$verb" ]; then
            verb=$a
        else
            verb2=$a
            break
        fi
    done

    case "$sub" in
    "" | version | help | completion | auth)
        echo none
        ;;
    api)
        _ghts_classify_api "$@"
        ;;
    pr)
        case "$verb" in
        merge) echo write ;;
        *) echo read ;;
        esac
        ;;
    release)
        case "$verb" in
        create | upload | delete | delete-asset | edit) echo write ;;
        *) echo read ;;
        esac
        ;;
    repo)
        case "$verb" in
        create | delete | edit | rename | archive | unarchive | fork)
            echo admin
            ;;
        deploy-key)
            case "$verb2" in
            add | delete) echo admin ;;
            *) echo read ;;
            esac
            ;;
        autolink)
            case "$verb2" in
            create | delete) echo admin ;;
            *) echo read ;;
            esac
            ;;
        sync) echo write ;;
        *) echo read ;;
        esac
        ;;
    workflow)
        case "$verb" in
        run | enable | disable) echo write ;;
        *) echo read ;;
        esac
        ;;
    run)
        case "$verb" in
        rerun | cancel | delete) echo write ;;
        *) echo read ;;
        esac
        ;;
    secret | variable)
        case "$verb" in
        set | delete | remove) echo write ;;
        *) echo read ;;
        esac
        ;;
    cache)
        case "$verb" in
        delete) echo write ;;
        *) echo read ;;
        esac
        ;;
    *)
        echo read
        ;;
    esac
    return 0
}

# 持ち主 (owner) として許す名前。先頭は英数字、全体で39文字まで
_GHTS_OWNER_RE='^[A-Za-z0-9]([A-Za-z0-9-]{0,38})$'

ghts_valid_owner() {
    [[ ${1-} =~ $_GHTS_OWNER_RE ]]
}

_ghts_lower() {
    printf '%s' "$1" | tr '[:upper:]' '[:lower:]'
}

# github.com の remote / Web の URL から小文字の owner を出す。それ以外は空。
# 検証はしない (呼び出し側が ghts_valid_owner で行う)。
ghts_owner_from_url() {
    # host を変数に切り出すのは、リテラルの ssh://git@host/ が gitleaks の
    # email-address に当たるのを避けるため
    local host=github.com u rest
    u=$(_ghts_lower "$1")
    case "$u" in
    git@"$host":*) rest=${u#git@"$host":} ;;
    ssh://git@"$host"/*) rest=${u#ssh://git@"$host"/} ;;
    https://"$host"/*) rest=${u#https://"$host"/} ;;
    *) return 0 ;;
    esac
    printf '%s\n' "${rest%%/*}"
}

# -R / --repo の値 (OWNER/REPO, HOST/OWNER/REPO, URL) から小文字の owner を出す
_ghts_owner_from_repo_spec() {
    local spec=$1 slashes owner
    case "$spec" in
    *://* | git@*)
        ghts_owner_from_url "$spec"
        return 0
        ;;
    esac
    slashes=${spec//[^\/]/}
    if [ "${#slashes}" -ge 2 ]; then
        # HOST/OWNER/REPO は先頭の host を落とす
        spec=${spec#*/}
    fi
    owner=${spec%%/*}
    [ -n "$owner" ] && printf '%s\n' "$(_ghts_lower "$owner")"
    return 0
}

# gh api のエンドポイントから owner を出す。repos/O/.. orgs/O/.. users/U のみ
_ghts_owner_from_endpoint() {
    local ep=${1#/} kind rest owner
    kind=${ep%%/*}
    case "$ep" in
    */*) rest=${ep#*/} ;;
    *) rest="" ;;
    esac
    owner=${rest%%/*}
    case "$kind" in
    repos | orgs | users)
        [ -n "$owner" ] && printf '%s\n' "$(_ghts_lower "$owner")"
        ;;
    esac
    return 0
}

# gh の引数から持ち主を決めて小文字で出す (決められなければ空)。rc は常に 0。
# 優先順: 1 -R/--repo、2 api のエンドポイント、2' その他の位置引数の URL / OWNER/REPO
ghts_owner_from_args() {
    local args=("$@") i=0 n=$# a repo="" sub="" endpoint="" cand="" pos=0

    while [ "$i" -lt "$n" ]; do
        a=${args[$i]}
        i=$((i + 1))
        case "$a" in
        -R | --repo)
            if [ "$i" -lt "$n" ]; then
                repo=${args[$i]}
                i=$((i + 1))
            fi
            continue
            ;;
        --repo=*)
            repo=${a#--repo=}
            continue
            ;;
        -R?*)
            repo=${a#-R}
            continue
            ;;
        esac

        if [ "$sub" = api ]; then
            case "$a" in
            # 値を取るフラグ。値をエンドポイントと取り違えない
            -X | --method | -f | -F | --field | --raw-field | --input | -H | --header | -q | --jq | -t | --template | --cache | --hostname | -p | --preview)
                i=$((i + 1))
                continue
                ;;
            -*) continue ;;
            esac
            if [ -z "$endpoint" ]; then endpoint=$a; fi
            continue
        fi

        case "$a" in
        -*) continue ;;
        esac
        pos=$((pos + 1))
        if [ "$pos" -eq 1 ]; then
            sub=$a
        elif [ "$pos" -ge 3 ] && [ -z "$cand" ]; then
            # サブコマンドと動詞の後ろの位置引数だけを対象にする。素の OWNER/REPO は
            # repo サブコマンドの動詞直後だけ (ブランチ名・パス・フラグ値と区別できない)
            case "$a" in
            *://* | git@*) cand=$(ghts_owner_from_url "$a") ;;
            */*)
                if [ "$sub" = repo ] && [ "$pos" -eq 3 ]; then
                    cand=$(_ghts_owner_from_repo_spec "$a")
                fi
                ;;
            esac
        fi
    done

    if [ -n "$repo" ]; then
        _ghts_owner_from_repo_spec "$repo"
    elif [ "$sub" = api ]; then
        [ -n "$endpoint" ] && _ghts_owner_from_endpoint "$endpoint"
    elif [ -n "$cand" ]; then
        printf '%s\n' "$cand"
    fi
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
            GHTS_DEFAULT_OWNER=$(_ghts_lower "$val")
            ;;
        owner)
            ghts_valid_owner "$val" || return 1
            GHTS_OWNERS="${GHTS_OWNERS:+$GHTS_OWNERS }$(_ghts_lower "$val")"
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
