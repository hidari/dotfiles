"""rsync に渡す基本除外パターン。

macOS / Windows が自動生成する不要なシステムファイルをバックアップから除外する。
旧 backup.sh の EXCLUDE_LIST (108-151 行) と 1:1 に対応する。
"""

from __future__ import annotations

# バックアップスクリプト関連
_BACKUP_SCRIPT: tuple[str, ...] = (
    ".backup_logs",  # このツールが生成するログディレクトリ
)

# Finder とファイル管理関連
_FINDER: tuple[str, ...] = (
    ".DS_Store",  # Finder の表示設定ファイル
    "._*",  # AppleDouble ファイル (リソースフォーク/メタデータ)
    ".localized",  # フォルダ名の多言語表示用ファイル
    ".VolumeIcon.icns",  # ボリュームのカスタムアイコン
)

# Spotlight 関連
_SPOTLIGHT: tuple[str, ...] = (
    ".Spotlight-V100",
    ".metadata_never_index",
    ".metadata_never_index_unless_rootfs",
)

# Time Machine
_TIME_MACHINE: tuple[str, ...] = (".com.apple.timemachine.donotpresent",)

# ゴミ箱・一時ファイル
_TRASH_TEMP: tuple[str, ...] = (
    ".Trashes",
    ".TemporaryItems",
)

# システムイベント・キャッシュ
_SYSTEM_EVENTS: tuple[str, ...] = (
    ".fseventsd",
    ".DocumentRevisions-V100",
)

# Quick Look
_QUICK_LOOK: tuple[str, ...] = (".ql_*",)

# AFP (Apple Filing Protocol)
_AFP: tuple[str, ...] = (".apdisk",)

# インストーラー関連
_INSTALLER: tuple[str, ...] = (
    ".PKInstallSandboxManager",
    ".PKInstallSandboxManager-SystemSoftware",
)

# 古い Mac OS 時代の遺物
_LEGACY_MAC: tuple[str, ...] = (
    ".AppleDB",
    ".AppleDesktop",
)

# Windows システムファイル
_WINDOWS: tuple[str, ...] = (
    "Thumbs.db",
    "desktop.ini",
)

DEFAULT_EXCLUDES: tuple[str, ...] = (
    *_BACKUP_SCRIPT,
    *_FINDER,
    *_SPOTLIGHT,
    *_TIME_MACHINE,
    *_TRASH_TEMP,
    *_SYSTEM_EVENTS,
    *_QUICK_LOOK,
    *_AFP,
    *_INSTALLER,
    *_LEGACY_MAC,
    *_WINDOWS,
)
