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
