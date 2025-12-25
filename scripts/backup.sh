#!/bin/bash

# =============================================================================
# ストレージバックアップスクリプト
# =============================================================================

# ロケール設定を明示的に指定して、日本語ファイル名を正しく扱えるようにする
# ja_JP.UTF-8が利用できない環境では、UTF-8ベースの他のロケールにフォールバック
if locale -a 2>/dev/null | grep -q "ja_JP.UTF-8"; then
    export LC_ALL=ja_JP.UTF-8
    export LANG=ja_JP.UTF-8
elif locale -a 2>/dev/null | grep -q "en_US.UTF-8"; then
    export LC_ALL=en_US.UTF-8
    export LANG=en_US.UTF-8
else
    # どちらも利用できない場合は、UTF-8を明示的に指定
    export LC_ALL=C.UTF-8 2>/dev/null || export LC_ALL=C
    export LANG=C.UTF-8 2>/dev/null || export LANG=C
fi

# -----------------------------------------------------------------------------
# 設定ファイルの読み込み
# -----------------------------------------------------------------------------
# スクリプトと同じディレクトリにある backup.conf から設定を読み込む
# シンボリックリンク経由で実行された場合も、実際のスクリプトの場所を解決する
# 設定ファイルが見つからない場合は、エラーメッセージを表示して終了

# シンボリックリンクを解決してスクリプトの実際のパスを取得
# macOS 12.3+ では realpath が使えるが、古い環境でも動作するようフォールバック付き
if command -v realpath >/dev/null 2>&1; then
    SCRIPT_PATH="$(realpath "$0")"
else
    # realpath がない場合は手動でシンボリックリンクを解決
    SCRIPT_PATH="$0"
    while [ -L "$SCRIPT_PATH" ]; do
        LINK_DIR="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)"
        SCRIPT_PATH="$(readlink "$SCRIPT_PATH")"
        # 相対パスの場合は絶対パスに変換
        [[ "$SCRIPT_PATH" != /* ]] && SCRIPT_PATH="$LINK_DIR/$SCRIPT_PATH"
    done
    SCRIPT_PATH="$(cd "$(dirname "$SCRIPT_PATH")" && pwd)/$(basename "$SCRIPT_PATH")"
fi
SCRIPT_DIR="$(dirname "$SCRIPT_PATH")"
CONFIG_FILE="$SCRIPT_DIR/backup.conf"

if [ ! -f "$CONFIG_FILE" ]; then
    echo "=========================================="
    echo "エラー: 設定ファイルが見つかりません"
    echo "=========================================="
    echo ""
    echo "設定ファイル: $CONFIG_FILE"
    echo ""
    echo "初めて使う場合は、以下の手順で設定ファイルを作成してください："
    echo ""
    echo "1. テンプレートをコピー："
    echo "   cp $SCRIPT_DIR/backup.example.conf $CONFIG_FILE"
    echo ""
    echo "2. 設定ファイルを編集："
    echo "   vim $CONFIG_FILE"
    echo "   （または他のエディタで編集）"
    echo ""
    echo "3. 自分の環境に合わせて、SSDのマウントポイントを設定"
    echo ""
    exit 1
fi

# 設定ファイルのパーミッションをチェック（セキュリティ対策）
# 他のユーザーが書き込み可能な場合は警告を表示
# source で読み込む前に、悪意のあるコードが含まれていないか確認するため
config_perms=$(stat -f '%A' "$CONFIG_FILE" 2>/dev/null)
if [ -n "$config_perms" ]; then
    # パーミッションの最後の桁（その他ユーザー）が2（書き込み可能）を含むかチェック
    other_write=$((config_perms % 10 & 2))
    group_write=$(((config_perms / 10) % 10 & 2))
    if [ "$other_write" -ne 0 ] || [ "$group_write" -ne 0 ]; then
        echo "=========================================="
        echo "警告: 設定ファイルのパーミッションが緩すぎます"
        echo "=========================================="
        echo ""
        echo "設定ファイル: $CONFIG_FILE"
        echo "現在のパーミッション: $config_perms"
        echo ""
        echo "セキュリティ向上のため、以下のコマンドで修正してください："
        echo "  chmod 600 $CONFIG_FILE"
        echo ""
    fi
fi

# 設定ファイルを読み込む
# shellcheck source=./backup.conf
source "$CONFIG_FILE"

# 必須設定項目のチェックは BACKUP_PAIRS の存在確認で行う

# ログファイルのパスは setup_logging 関数で動的に設定
# （拡張モードでは LOG_BASE_DIR または最初のペアのソースを使用）
LOG_DIR=""
LOG_FILE=""

# フィルタリングしたエラーを記録する一時ファイル
# mktemp を使用して安全な一時ファイルを作成（予測不可能なファイル名でセキュリティ向上）
FILTERED_ERRORS_FILE=$(mktemp)

# 除外リストの設定
# macOSが自動生成する不要なシステムファイルをバックアップから除外
EXCLUDE_LIST=(
    # === バックアップスクリプト関連 ===
    ".backup_logs"                 # このスクリプトが生成するログディレクトリ（バックアップ先にのみ存在）
    
    # === Finderとファイル管理関連 ===
    ".DS_Store"                    # Finderの表示設定ファイル（フォルダの表示方法、アイコン位置などを保存）
    "._*"                          # AppleDoubleファイル（リソースフォークやメタデータを保存）
    ".localized"                   # フォルダ名の多言語表示用ファイル（例：Documents→書類）
    ".VolumeIcon.icns"             # ボリュームのカスタムアイコンファイル
    
    # === Spotlight（検索機能）関連 ===
    ".Spotlight-V100"              # Spotlightのインデックスファイル（検索を高速化するデータベース）
    ".metadata_never_index"        # Spotlightにインデックス化を禁止するマーカーファイル
    ".metadata_never_index_unless_rootfs"  # ルートファイルシステム以外でのインデックス化を禁止
    
    # === Time Machine（バックアップ機能）関連 ===
    ".com.apple.timemachine.donotpresent"  # Time Machineのバックアップ先として使わないマーカー
    
    # === ゴミ箱と一時ファイル ===
    ".Trashes"                     # ゴミ箱の実体（削除されたファイルが一時的に保存される場所）
    ".TemporaryItems"              # macOSが作成する一時ファイル
    
    # === システムイベントとキャッシュ ===
    ".fseventsd"                   # ファイルシステムイベントのログ（ファイル変更履歴を記録）
    ".DocumentRevisions-V100"      # 自動保存とバージョン管理用の一時ファイル
    
    # === Quick Look（プレビュー機能）関連 ===
    ".ql_*"                        # Quick Lookのキャッシュファイル（サムネイル画像などを保存）
    
    # === AFP（Apple Filing Protocol）関連 ===
    ".apdisk"                      # AFPネットワークプロトコルのディスクキャッシュファイル
    
    # === インストーラー関連 ===
    ".PKInstallSandboxManager"     # パッケージインストーラーのサンドボックス管理ファイル
    ".PKInstallSandboxManager-SystemSoftware"  # システムソフトウェアインストール用
    
    # === 古いMac OS時代の遺物 ===
    ".AppleDB"                     # 旧Mac OSのデスクトップデータベース
    ".AppleDesktop"                # 旧Mac OSのデスクトップサービス情報
    
    # === Windowsシステムファイル（Windowsとのやり取りがある場合に備えて） ===
    "Thumbs.db"                    # Windowsのサムネイルキャッシュファイル
    "desktop.ini"                  # Windowsのフォルダカスタマイズ設定ファイル
)

# 設定ファイルから追加の除外パターンを読み込む
# ユーザーが ADDITIONAL_EXCLUDE を定義している場合、それを基本リストに追加する
#
# この処理の流れ：
# 1. 設定ファイルを source で読み込むと、ADDITIONAL_EXCLUDE 配列が定義される（定義されていれば）
# 2. 配列が定義されており要素数が0より大きいかをチェック
# 3. 定義されていれば、基本リストと追加リストを結合して新しい除外リストを作る
# 4. 結合には配列の展開構文 ${配列名[@]} を使用し、両方の要素を含む新しい配列を作成
#
# 追加の除外パターンが適用されたかを記録するフラグ
# （log 関数が未定義のため、ここでは記録のみ。出力は setup_logging 後に行う）
ADDITIONAL_EXCLUDE_COUNT=0

if [ "${#ADDITIONAL_EXCLUDE[@]}" -gt 0 ] 2>/dev/null; then
    # 追加の除外パターンが定義されている場合、基本リストと結合
    # ${EXCLUDE_LIST[@]} = 基本リストの全要素を展開
    # ${ADDITIONAL_EXCLUDE[@]} = 追加リストの全要素を展開
    # () = これらを新しい配列として結合
    EXCLUDE_LIST=("${EXCLUDE_LIST[@]}" "${ADDITIONAL_EXCLUDE[@]}")
    ADDITIONAL_EXCLUDE_COUNT=${#ADDITIONAL_EXCLUDE[@]}
fi

# =============================================================================
# 関数定義
# =============================================================================

# ログ出力関数
# 標準出力とログファイルの両方に出力する
log() {
    local message
    message="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo "$message"
    echo "$message" >> "$LOG_FILE"
}

# エラーログ出力関数
# エラーメッセージを出力して、スクリプトを終了する
error_exit() {
    log "エラー: $1"
    log "バックアップを中断しました。"
    exit 1
}

# マウントポイントの存在チェック関数
# 指定されたディレクトリが存在し、実際にマウントされているかを確認
check_mount() {
    local mount_point="$1"
    local name="$2"
    
    # ディレクトリの存在チェック
    if [ ! -d "$mount_point" ]; then
        error_exit "$name ($mount_point) がマウントされていません。"
    fi
    
    # macOSの場合、/Volumes配下にマウントされているかを確認
    # マウントポイントに実際にファイルシステムがマウントされているかチェック
    if ! mount | grep -q "on $mount_point "; then
        error_exit "$name ($mount_point) が正しくマウントされていません。"
    fi
    
    log "$name のマウントを確認しました: $mount_point"
}

# ディスク容量チェック関数
# バックアップ先に十分な空き容量があるかを確認
# rsyncは差分バックアップなので、2回目以降は実際に必要な容量は少ない
# そのため、最低限必要な空き容量（設定ファイルで指定）があるかをチェックする
check_disk_space() {
    local source="$1"
    local destination="$2"
    
    log "ディスク容量をチェックしています..."
    
    # バックアップ元の使用容量を取得（KB単位）
    # 2>/dev/null でエラー出力を抑制（システムディレクトリへのアクセス拒否エラーを隠す）
    local source_size
    source_size=$(du -sk "$source" 2>/dev/null | awk '{print $1}')

    # duコマンドが失敗した場合のエラーハンドリング
    if [ -z "$source_size" ] || [ "$source_size" -eq 0 ] 2>/dev/null; then
        log "警告: バックアップ元の使用容量を正確に取得できませんでした。"
        log "       容量チェックをスキップして続行します。"
        return 0
    fi
    
    # バックアップ先の空き容量を取得（KB単位）
    local dest_free
    dest_free=$(df -k "$destination" | tail -1 | awk '{print $4}')
    
    # 最低限必要な空き容量をKB単位に変換（GB→KB: ×1024×1024）
    local required_space=$((MINIMUM_FREE_SPACE_GB * 1024 * 1024))
    
    # 情報をログに出力
    # bcコマンドの代わりにawkを使用して計算（awkは標準で利用可能）
    log "バックアップ元の使用容量: $(awk -v size="$source_size" 'BEGIN {printf "%.2f", size/1024/1024}') GB"
    log "バックアップ先の空き容量: $(awk -v free="$dest_free" 'BEGIN {printf "%.2f", free/1024/1024}') GB"
    log "最低限必要な空き容量: ${MINIMUM_FREE_SPACE_GB} GB"
    
    # 空き容量が最低限必要な容量より少ない場合はエラー
    if [ "$dest_free" -lt "$required_space" ]; then
        error_exit "バックアップ先の空き容量が不足しています（最低 ${MINIMUM_FREE_SPACE_GB} GB 必要）。"
    fi
    
    log "十分な空き容量があることを確認しました。"
}

# rsync出力のフィルタリング関数
# 既知の無害なエラーメッセージ（システムディレクトリの削除失敗など）を抑制
# これにより、ログがより見やすくなり、重要なエラーに気づきやすくなる
# フィルタリングしたエラーは一時ファイルに記録し、後でサマリーを表示する
#
# パフォーマンス最適化:
# - 複数の -e オプションを単一の正規表現パターンに統合
# - Bash の [[ =~ ]] を使用してサブプロセス生成を回避
filter_rsync_output() {
    local line
    # フィルタリング対象のパターン（単一の正規表現に統合）
    # macOS が保護しているシステムディレクトリへのアクセス/削除エラーをフィルタ
    # opendir の場合は "..." で囲まれ、delete_file: rmdir の場合は (...) で囲まれる
    local filter_pattern='\.(Trashes|Spotlight-V100|fseventsd|TemporaryItems).*failed: Operation not permitted|IO error encountered -- skipping file deletion|rsync error:.*some files/attrs were not transferred.*code 23'

    while IFS= read -r line; do
        # Bash の組み込み正規表現マッチングを使用（サブプロセス生成なし）
        if [[ "$line" =~ $filter_pattern ]]; then
            # フィルタリング対象の場合、一時ファイルに記録（画面には表示しない）
            echo "$line" >> "$FILTERED_ERRORS_FILE"
        else
            # フィルタリング対象外の場合、そのまま表示
            echo "$line"
        fi
    done
}

# フィルタリングしたエラーのサマリーを表示する関数
show_filtered_errors_summary() {
    if [ -f "$FILTERED_ERRORS_FILE" ] && [ -s "$FILTERED_ERRORS_FILE" ]; then
        echo ""
        echo "----------------------------------------"
        echo "抑制されたシステムエラーのサマリー:"
        echo "----------------------------------------"

        # 各ディレクトリごとにエラーをカウント
        local trashes_count
        local spotlight_count
        local fseventsd_count
        local tempitems_count
        trashes_count=$(grep -c "\.Trashes" "$FILTERED_ERRORS_FILE" 2>/dev/null) || trashes_count=0
        spotlight_count=$(grep -c "\.Spotlight-V100" "$FILTERED_ERRORS_FILE" 2>/dev/null) || spotlight_count=0
        fseventsd_count=$(grep -c "\.fseventsd" "$FILTERED_ERRORS_FILE" 2>/dev/null) || fseventsd_count=0
        tempitems_count=$(grep -c "\.TemporaryItems" "$FILTERED_ERRORS_FILE" 2>/dev/null) || tempitems_count=0

        # カウントが0より大きいもののみ表示
        [ "$trashes_count" -gt 0 ] && echo " .Trashes: ${trashes_count}件"
        [ "$spotlight_count" -gt 0 ] && echo " .Spotlight-V100: ${spotlight_count}件"
        [ "$fseventsd_count" -gt 0 ] && echo " .fseventsd: ${fseventsd_count}件"
        [ "$tempitems_count" -gt 0 ] && echo " .TemporaryItems: ${tempitems_count}件"

        echo ""
        echo "これらはmacOSが保護しているシステムディレクトリです。"
        echo "データファイルのバックアップには影響ありません。"
    fi
}

# 古いログファイル削除関数
# LOG_RETENTION_DAYS で指定した日数より古いログファイルを自動的に削除
# これによりログディレクトリが肥大化するのを防ぐ
cleanup_old_logs() {
    # ログディレクトリが存在しない場合は何もしない
    if [ ! -d "$LOG_DIR" ]; then
        return
    fi

    log "古いログファイルのクリーンアップを実行しています..."

    # findコマンドで指定日数より古い.logファイルを検索して削除
    # -name "backup_*.log": backup_で始まる.logファイルのみを対象
    # -type f: 通常ファイルのみを対象（ディレクトリは除外）
    # -mtime +N: N日より古いファイル（+30なら30日より古い）
    # -delete: 見つかったファイルを削除
    local deleted_count
    deleted_count=$(find "$LOG_DIR" -name "backup_*.log" -type f -mtime +"$LOG_RETENTION_DAYS" -print -delete | wc -l)

    if [ "$deleted_count" -gt 0 ]; then
        log "${LOG_RETENTION_DAYS}日より古いログファイルを ${deleted_count} 個削除しました。"
    else
        log "削除対象の古いログファイルはありませんでした。"
    fi
}

# =============================================================================
# 複数ペア対応
# =============================================================================

# BACKUP_PAIRS の1要素をパースして変数に展開
# 引数: パイプ区切りの文字列
# 出力: PAIR_NAME, PAIR_SOURCE, PAIR_DEST, PAIR_EXCLUDES（配列）をグローバルに設定
parse_backup_pair() {
    local pair_string="$1"

    # パイプで分割
    PAIR_NAME="${pair_string%%|*}"
    local rest="${pair_string#*|}"
    PAIR_SOURCE="${rest%%|*}"
    rest="${rest#*|}"
    PAIR_DEST="${rest%%|*}"
    local excludes_str="${rest#*|}"

    # 除外パターンが元の文字列と同じ場合は空（区切りがなかった）
    if [ "$excludes_str" = "$PAIR_DEST" ]; then
        excludes_str=""
    fi

    # 除外パターンをカンマで分割して配列に
    PAIR_EXCLUDES=()
    if [ -n "$excludes_str" ]; then
        IFS=',' read -ra PAIR_EXCLUDES <<< "$excludes_str"
    fi

    # 前後の空白をトリム
    PAIR_NAME="${PAIR_NAME## }"
    PAIR_NAME="${PAIR_NAME%% }"
    PAIR_SOURCE="${PAIR_SOURCE## }"
    PAIR_SOURCE="${PAIR_SOURCE%% }"
    PAIR_DEST="${PAIR_DEST## }"
    PAIR_DEST="${PAIR_DEST%% }"
}

# パスの種類を判定
# 戻り値: "volume"（ボリューム直下）, "directory"（ディレクトリ）, "local"（ローカル）
get_path_type() {
    local path="$1"

    # /Volumes/XXX の形式かチェック
    if [[ "$path" =~ ^/Volumes/[^/]+$ ]]; then
        echo "volume"
    elif [[ "$path" =~ ^/Volumes/ ]]; then
        echo "directory"
    else
        # /Volumes 以外のパス（ローカルディレクトリなど）
        echo "local"
    fi
}

# パスからボリューム名を抽出
# 例: /Volumes/Luna-P/Photos → /Volumes/Luna-P
extract_volume_path() {
    local path="$1"

    if [[ "$path" =~ ^(/Volumes/[^/]+) ]]; then
        echo "${BASH_REMATCH[1]}"
    else
        echo ""
    fi
}

# 拡張版パス検証関数
# ボリューム全体の場合はマウント確認、ディレクトリの場合は親ボリューム確認＋存在確認
check_path() {
    local path="$1"
    local name="$2"
    local path_type
    path_type=$(get_path_type "$path")

    case "$path_type" in
        "volume")
            # 従来のボリュームチェック
            check_mount "$path" "$name"
            ;;
        "directory")
            # ディレクトリの場合: 親ボリュームのマウント確認 + ディレクトリ存在確認
            local volume_path
            volume_path=$(extract_volume_path "$path")

            if [ -z "$volume_path" ]; then
                error_exit "$name のボリュームパスを特定できません: $path"
            fi

            # 親ボリュームのマウント確認
            if ! mount | grep -q "on $volume_path "; then
                error_exit "$name の親ボリューム ($volume_path) がマウントされていません。"
            fi

            # ディレクトリの存在確認
            if [ ! -d "$path" ]; then
                error_exit "$name のディレクトリが存在しません: $path"
            fi

            log "$name のパスを確認しました: $path (ボリューム: $volume_path)"
            ;;
        "local")
            # ローカルパスの場合は単純にディレクトリ存在確認
            if [ ! -d "$path" ]; then
                error_exit "$name のディレクトリが存在しません: $path"
            fi
            log "$name のパスを確認しました: $path"
            ;;
    esac
}

# ロギングのセットアップ
setup_logging() {
    local base_path="$1"

    if [ -n "$LOG_BASE_DIR" ]; then
        LOG_DIR="$LOG_BASE_DIR"
    else
        LOG_DIR="$base_path/.backup_logs"
    fi

    if [ "$DRY_RUN" = false ]; then
        mkdir -p "$LOG_DIR"
        LOG_FILE="$LOG_DIR/backup_$(date +%Y%m%d_%H%M%S).log"
        cleanup_old_logs
        touch "$LOG_FILE"
        log "==================== バックアップセッション開始 ===================="
        # 追加の除外パターンが適用されていた場合、ここでログ出力
        if [ "$ADDITIONAL_EXCLUDE_COUNT" -gt 0 ]; then
            log "追加の除外パターンを ${ADDITIONAL_EXCLUDE_COUNT} 個適用しました。"
        fi
    else
        LOG_FILE="/dev/null"
    fi
}

# 全ペアの情報表示
display_all_pairs_info() {
    echo ""
    echo "=========================================="
    echo "バックアップ設定（${#BACKUP_PAIRS[@]} ペア）"
    echo "=========================================="

    local index=1
    for pair in "${BACKUP_PAIRS[@]}"; do
        parse_backup_pair "$pair"
        echo ""
        echo "[$index] $PAIR_NAME"
        echo "    source: $PAIR_SOURCE"
        echo "    destination: $PAIR_DEST"
        if [ "${#PAIR_EXCLUDES[@]}" -gt 0 ]; then
            echo "    固有の除外: ${PAIR_EXCLUDES[*]}"
        fi
        ((index++))
    done

    echo ""
    echo "Exclude List:"
    printf '%s\n' "${EXCLUDE_LIST[@]}" | sed 's/^/  - /'
}

# サマリー表示
display_summary() {
    local success=$1
    local partial=$2
    local fail=$3
    local total=$((success + partial + fail))

    echo ""
    echo "=========================================="
    echo "バックアップ結果サマリー"
    echo "=========================================="
    echo "成功: $success / $total"
    echo "部分的成功: $partial / $total"
    echo "失敗: $fail / $total"

    if [ "$fail" -gt 0 ]; then
        echo ""
        echo "警告: 一部のバックアップが失敗しました。ログを確認してください。"
    fi
}

# 終了処理
finalize_backup() {
    show_filtered_errors_summary
    rm -f "$FILTERED_ERRORS_FILE"

    if [ "$DRY_RUN" = false ]; then
        log "==================== バックアップセッション終了 ===================="
        echo ""
        echo "ログファイル: $LOG_FILE"
    fi
}

# 単一のバックアップペアを実行
# 引数: $1=ペア名, $2=ソース, $3=デスティネーション, $4...=追加除外パターン
execute_backup_pair() {
    local pair_name="$1"
    local source="$2"
    local destination="$3"
    shift 3
    local pair_excludes=("$@")

    log "========== [$pair_name] バックアップ開始 =========="
    log "source: $source"
    log "destination: $destination"

    # パス検証
    check_path "$source" "[$pair_name] "
    check_path "$destination" "[$pair_name] "

    # 容量チェック
    check_disk_space "$source" "$destination"

    # このペア用の除外リストを構築
    local current_exclude_list=("${EXCLUDE_LIST[@]}")

    # ペア固有の除外パターンを追加
    if [ "${#pair_excludes[@]}" -gt 0 ]; then
        current_exclude_list+=("${pair_excludes[@]}")
        log "ペア固有の除外パターン: ${pair_excludes[*]}"
    fi

    # 除外オプションを生成
    local exclude_opts=()
    for item in "${current_exclude_list[@]}"; do
        exclude_opts+=("--exclude=$item")
    done

    # rsyncオプションを構築
    local rsync_options=(-avh --delete --delete-excluded --progress --stats "${exclude_opts[@]}")

    if [ "$DRY_RUN" = true ]; then
        rsync_options+=(--dry-run)
    fi

    # パスの正規化
    local source_path="${source%/}/"
    local destination_path="${destination%/}"

    # rsync実行
    local start_time
    start_time=$(date +%s)

    rsync "${rsync_options[@]}" "$source_path" "$destination_path" 2>&1 | filter_rsync_output | tee -a "$LOG_FILE"
    local rsync_exit_code=${PIPESTATUS[0]}

    local end_time
    end_time=$(date +%s)
    local elapsed=$((end_time - start_time))

    # 結果を返す（0: 成功, 23: 部分的成功, その他: エラー）
    log "[$pair_name] 完了 (所要時間: $((elapsed / 60))分$((elapsed % 60))秒, 終了コード: $rsync_exit_code)"

    return $rsync_exit_code
}

# バックアップ実行（複数ペア処理）
run_backup() {
    # 必須設定のチェック
    if [ -z "$LOG_RETENTION_DAYS" ] || [ -z "$MINIMUM_FREE_SPACE_GB" ]; then
        echo "エラー: 設定ファイルに必要な項目が定義されていません。"
        echo "設定ファイル: $CONFIG_FILE"
        echo ""
        echo "必須項目："
        echo "  - MINIMUM_FREE_SPACE_GB（最低限必要な空き容量）"
        echo "  - LOG_RETENTION_DAYS（ログ保持期間）"
        exit 1
    fi

    # ログディレクトリの決定（カレントディレクトリに出力）
    setup_logging "$PWD"

    log "${#BACKUP_PAIRS[@]} 個のバックアップペアを処理します"

    # 全ペアの情報を表示
    display_all_pairs_info

    # ユーザー確認
    if [ "$DRY_RUN" = false ]; then
        echo ""
        echo "上記の設定でバックアップを実行しますか？ (y/n): "
        read -r confirm
        if [ "$confirm" != "y" ]; then
            log "ユーザーによってバックアップが中止されました。"
            exit 0
        fi
    fi

    # 各ペアを順次実行
    local success_count=0
    local fail_count=0
    local partial_count=0
    local error_behavior="${ERROR_BEHAVIOR:-continue}"

    for pair in "${BACKUP_PAIRS[@]}"; do
        parse_backup_pair "$pair"

        execute_backup_pair "$PAIR_NAME" "$PAIR_SOURCE" "$PAIR_DEST" "${PAIR_EXCLUDES[@]}"
        local exit_code=$?

        case $exit_code in
            0)
                ((success_count++))
                ;;
            23)
                ((partial_count++))
                ;;
            *)
                ((fail_count++))
                if [ "$error_behavior" = "stop" ]; then
                    log "[$PAIR_NAME] でエラーが発生したため、処理を中断します。"
                    display_summary "$success_count" "$partial_count" "$fail_count"
                    finalize_backup
                    exit 2
                fi
                log "警告: [$PAIR_NAME] でエラーが発生しましたが、次のペアを続行します。"
                ;;
        esac
    done

    # サマリー表示
    display_summary "$success_count" "$partial_count" "$fail_count"

    finalize_backup

    # 終了コードの決定
    if [ "$fail_count" -eq "${#BACKUP_PAIRS[@]}" ]; then
        exit 3  # 全て失敗
    elif [ "$fail_count" -gt 0 ]; then
        exit 2  # 一部失敗
    else
        exit 0  # 成功
    fi
}

# =============================================================================
# メイン処理
# =============================================================================

# dry-runモードのチェック
# コマンドライン引数に --dry-run または -n が指定されているかを確認
DRY_RUN=false
if [[ "$*" == *"--dry-run"* ]] || [[ "$*" == *"-n"* ]]; then
    DRY_RUN=true
    echo "=========================================="
    echo "DRY-RUNモード: 実際のコピーは行いません"
    echo "=========================================="
fi

# BACKUP_PAIRS の存在チェック
if [ "${#BACKUP_PAIRS[@]}" -eq 0 ] 2>/dev/null; then
    echo "エラー: 有効なバックアップ設定が見つかりません。"
    echo "設定ファイル: $CONFIG_FILE"
    echo ""
    echo "設定方法："
    echo "  BACKUP_PAIRS=("
    echo "      \"名前|/Volumes/Source|/Volumes/Destination\""
    echo "  )"
    echo ""
    echo "例："
    echo "  BACKUP_PAIRS=("
    echo "      \"メインSSD|/Volumes/Luna-P|/Volumes/Luna-S\""
    echo "  )"
    exit 1
fi

run_backup
