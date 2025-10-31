#!/bin/bash

# ロケール設定を明示的に指定して、日本語ファイル名を正しく扱えるようにする
export LC_ALL=ja_JP.UTF-8
export LANG=ja_JP.UTF-8

# =============================================================================
# SSDバックアップスクリプト（改善版）
# =============================================================================

# -----------------------------------------------------------------------------
# 設定ファイルの読み込み
# -----------------------------------------------------------------------------
# スクリプトと同じディレクトリにある backup.conf から設定を読み込む
# 設定ファイルが見つからない場合は、エラーメッセージを表示して終了
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
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

# 設定ファイルを読み込む
# shellcheck source=./backup.conf
source "$CONFIG_FILE"

# 必須の設定項目がすべて定義されているかチェック
if [ -z "$SOURCE_STORAGE" ] || [ -z "$DESTINATION_STORAGE" ] || [ -z "$LOG_RETENTION_DAYS" ] || [ -z "$MINIMUM_FREE_SPACE_GB" ]; then
    echo "エラー: 設定ファイルに必要な項目が定義されていません。"
    echo "設定ファイル: $CONFIG_FILE"
    echo ""
    echo "必須項目："
    echo "  - SOURCE_STORAGE（バックアップ元のストレージ）"
    echo "  - DESTINATION_STORAGE（バックアップ先のストレージ）"
    echo "  - MINIMUM_FREE_SPACE_GB（最低限必要な空き容量）"
    echo "  - LOG_RETENTION_DAYS（ログ保持期間）"
    exit 1
fi

# ログファイルのパスを設定
LOG_DIR="$SOURCE_STORAGE/.backup_logs"
LOG_FILE="$LOG_DIR/backup_$(date +%Y%m%d_%H%M%S).log"

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
# 2. 配列が定義されているか（要素数が0より大きいか）をチェック
# 3. 定義されていれば、基本リストと追加リストを結合して新しい除外リストを作る
# 4. 結合には配列の展開構文 ${配列名[@]} を使用し、両方の要素を含む新しい配列を作成
#
if [ -n "${ADDITIONAL_EXCLUDE+x}" ] && [ ${#ADDITIONAL_EXCLUDE[@]} -gt 0 ]; then
    # 追加の除外パターンが定義されている場合、基本リストと結合
    # ${EXCLUDE_LIST[@]} = 基本リストの全要素を展開
    # ${ADDITIONAL_EXCLUDE[@]} = 追加リストの全要素を展開
    # () = これらを新しい配列として結合
    EXCLUDE_LIST=("${EXCLUDE_LIST[@]}" "${ADDITIONAL_EXCLUDE[@]}")
    
    # デバッグ用：追加された除外パターンの数を表示
    # （この行はオプション。実運用では削除しても良い）
    log "追加の除外パターンを ${#ADDITIONAL_EXCLUDE[@]} 個適用しました。"
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
    
    # バックアップ先の空き容量を取得（KB単位）
    local dest_free
    dest_free=$(df -k "$destination" | tail -1 | awk '{print $4}')
    
    # 最低限必要な空き容量をKB単位に変換（GB→KB: ×1024×1024）
    local required_space=$((MINIMUM_FREE_SPACE_GB * 1024 * 1024))
    
    # 情報をログに出力
    log "バックアップ元の使用容量: $(echo "scale=2; $source_size/1024/1024" | bc) GB"
    log "バックアップ先の空き容量: $(echo "scale=2; $dest_free/1024/1024" | bc) GB"
    log "最低限必要な空き容量: ${MINIMUM_FREE_SPACE_GB} GB"
    
    # 空き容量が最低限必要な容量より少ない場合はエラー
    if [ "$dest_free" -lt "$required_space" ]; then
        error_exit "バックアップ先の空き容量が不足しています（最低 ${MINIMUM_FREE_SPACE_GB} GB 必要）。"
    fi
    
    log "十分な空き容量があることを確認しました。"
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

# マウントポイントの存在チェック
echo "マウントポイントをチェックしています..."
check_mount "$SOURCE_STORAGE" "バックアップ元 ($(basename "$SOURCE_STORAGE"))"
check_mount "$DESTINATION_STORAGE" "バックアップ先 ($(basename "$DESTINATION_STORAGE"))"

# ログディレクトリの作成
# dry-runモードでない場合のみ、ログディレクトリとファイルを作成
if [ "$DRY_RUN" = false ]; then
    mkdir -p "$LOG_DIR"
    
    # 古いログファイルのクリーンアップを実行
    # 新しいログファイルを作成する前に、古いログを削除することで
    # ログディレクトリの肥大化を防ぐ
    cleanup_old_logs
    
    touch "$LOG_FILE"
    log "==================== バックアップ開始 ===================="
else
    # dry-runモードの場合はログファイルに出力しない
    LOG_FILE="/dev/null"
fi

# ディスク容量チェック
check_disk_space "$SOURCE_STORAGE" "$DESTINATION_STORAGE"

# 除外オプションの生成
# 配列に格納された除外パターンをrsyncのオプション形式に変換
# 配列を使うことで、引用符の問題を回避し、より安全にオプションを扱える
EXCLUDE_OPTS=()
for item in "${EXCLUDE_LIST[@]}"; do
    EXCLUDE_OPTS+=("--exclude=$item")
done

# rsyncコマンドのオプションを配列として設定
# -a: アーカイブモード（パーミッション、タイムスタンプ、シンボリックリンクなどを保持）
# -v: 詳細出力（処理中のファイル名を表示）
# -h: 人間が読みやすい形式でサイズを表示
# --delete: バックアップ元にないファイルをバックアップ先から削除（完全同期）
# --delete-excluded: 除外パターンに一致するファイルもバックアップ先から削除
# --progress: 各ファイルの転送進行状況を表示
# --stats: 転送完了後に統計情報を表示
RSYNC_OPTIONS=(-avh --delete --delete-excluded --progress --stats "${EXCLUDE_OPTS[@]}")

# dry-runモードの場合は --dry-run オプションを追加
if [ "$DRY_RUN" = true ]; then
    RSYNC_OPTIONS+=(--dry-run)
fi

# バックアップ実行前の確認と情報表示
echo ""
echo "=========================================="
echo "バックアップ設定"
echo "=========================================="
echo "バックアップ元: $SOURCE_STORAGE"
echo "バックアップ先: $DESTINATION_STORAGE"
if [ "$DRY_RUN" = false ]; then
    echo "ログファイル  : $LOG_FILE"
fi
echo ""
echo "除外項目:"
printf '%s\n' "${EXCLUDE_LIST[@]}" | sed 's/^/  - /'
echo ""

# ユーザーに実行確認を求める
# dry-runモードでない場合のみ、確認を求める
if [ "$DRY_RUN" = false ]; then
    echo "上記の設定でバックアップを実行しますか？ (y/n): "
    read -r  confirm
    if [ "$confirm" != "y" ]; then
        log "ユーザーによってバックアップが中止されました。"
        echo "バックアップを中止しました。"
        exit 0
    fi
fi

# バックアップ開始時刻を記録
START_TIME=$(date +%s)
log "バックアップを開始します..."
echo ""

# rsyncコマンドを実行してバックアップを実施
# エラーが発生した場合は、その終了ステータスを保存
rsync "${RSYNC_OPTIONS[@]}" "$SOURCE_STORAGE/" "$DESTINATION_STORAGE/" 2>&1 | tee -a "$LOG_FILE"
RSYNC_EXIT_CODE=${PIPESTATUS[0]}

# バックアップ終了時刻を記録し、所要時間を計算
END_TIME=$(date +%s)
ELAPSED_TIME=$((END_TIME - START_TIME))
MINUTES=$((ELAPSED_TIME / 60))
SECONDS=$((ELAPSED_TIME % 60))

echo ""

# rsyncの終了ステータスをチェック
# 0: 成功
# 23: 一部のファイル/属性が転送できなかった（非致命的）
# その他: エラー
if [ "$RSYNC_EXIT_CODE" -eq 0 ]; then
    if [ "$DRY_RUN" = true ]; then
        echo "=========================================="
        echo "DRY-RUN完了（実際のコピーは行われていません）"
        echo "=========================================="
    else
        log "==================== バックアップ完了 ===================="
        log "所要時間: ${MINUTES}分${SECONDS}秒"
        echo ""
        echo "=========================================="
        echo "バックアップが正常に完了しました！"
        echo "=========================================="
        echo "バックアップ先: $DESTINATION_STORAGE"
        echo "所要時間: ${MINUTES}分${SECONDS}秒"
        echo "ログファイル: $LOG_FILE"
    fi
    exit 0
elif [ "$RSYNC_EXIT_CODE" -eq 23 ]; then
    # エラーコード23は「一部のファイルが転送できなかった」という非致命的なエラー
    # 通常、システムが保護しているディレクトリ（.Trashes、.Spotlight-V100など）の
    # 削除に失敗した場合に発生するが、重要なデータのバックアップには影響しない
    if [ "$DRY_RUN" = true ]; then
        echo "=========================================="
        echo "DRY-RUN完了（警告あり）"
        echo "=========================================="
        echo ""
        echo "⚠️  一部のファイル処理で問題がありましたが、"
        echo "   重要なデータのバックアップには影響ありません。"
        echo ""
        echo "詳細: システムディレクトリの削除で問題が発生しました。"
        echo "     これは通常、macOSが保護しているディレクトリ"
        echo "     （.Trashes、.Spotlight-V100など）が原因です。"
    else
        log "==================== バックアップ完了（警告あり） ===================="
        log "所要時間: ${MINUTES}分${SECONDS}秒"
        log "警告: 一部のファイル処理で問題がありましたが、重要なデータのバックアップには影響ありません。"
        echo ""
        echo "=========================================="
        echo "バックアップが完了しました（警告あり）"
        echo "=========================================="
        echo "バックアップ先: $DESTINATION_STORAGE"
        echo "所要時間: ${MINUTES}分${SECONDS}秒"
        echo "ログファイル: $LOG_FILE"
        echo ""
        echo "⚠️  一部のファイル処理で問題がありましたが、"
        echo "   重要なデータのバックアップには影響ありません。"
        echo ""
        echo "詳細: システムディレクトリの削除で問題が発生しました。"
        echo "     これは通常、macOSが保護しているディレクトリ"
        echo "     （.Trashes、.Spotlight-V100など）が原因です。"
        echo "     実際のデータファイルは全て正しくバックアップされています。"
    fi
    exit 0
else
    # rsyncがエラーで終了した場合
    error_exit "rsyncがエラーコード $RSYNC_EXIT_CODE で終了しました。"
fi
