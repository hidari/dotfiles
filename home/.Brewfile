# カスタムTap
tap "hidari/tap"
tap "stripe/stripe-cli"
tap "supabase/tap"
tap "microsoft/apm"

# --- 開発ツール ---
brew "git"                                # バージョン管理システム
brew "cmake"                              # クロスプラットフォームビルドシステム
brew "icu4c@76"                           # C/C++向けUnicode,国際化,地域化ライブラリ
brew "go"                                 # Go言語
brew "deno"                               # Denoランタイム
brew "gh"                                 # GitHub CLI
brew "libpq"                              # PostgreSQL通信するクライアントライブラリ
brew "mise"                               # ランタイム/ツールバージョン管理 (pin は .config/mise/config.toml)
brew "microsoft/apm/apm"                  # Agent Package Manager (skill/plugin の宣言的配信)
brew "powershell"                         # Windows 検証 VM 向け .ps1 の Pester テスト実行に使う
brew "pnpm"                               # Node.js パッケージマネージャ (npm/npx は使わない)
brew "uv"                                 # Python パッケージ/実行管理 (pre-commit の local hook が依存)
brew "just"                               # コマンドランナー (justfile)

# --- Platform CLI
brew "stripe/stripe-cli/stripe"           # Stripe決済プラットフォームCLI
brew "supabase/tap/supabase"              # SupabaseバックエンドサービスCLI
brew "awscli"                             # AWS CLIツール
brew "cloudflared"                        # Cloudflare TunnelのCLI
brew "cloud-sql-proxy"                    # Google Cloud SQLプロキシ
cask "gcloud-cli"                         # Google Cloud Platform CLI
cask "1password-cli"                      # 1Passwordコマンドラインツール

# --- メディア処理 ---
brew "ffmpeg"                             # 動画・音声変換ツール
brew "imagemagick"                        # 画像処理ツール
brew "yt-dlp"                             # 動画ダウンローダー

# --- ユーティリティ ---
brew "jq"                                 # JSONパーサー
brew "rsync"                              # ファイル同期ツール
brew "tree"                               # ディレクトリツリー表示
brew "yusukebe/tap/ax", trusted: true     # The AI-era curl
brew "hidari/tap/rip"                     # zipアーカイバ

# --- コード品質 / セキュリティ ---
brew "pre-commit"                         # git pre-commit フック管理
brew "gitleaks"                           # secret / ユーザー名パス漏洩スキャナ
brew "ast-grep"                           # 構文木ベースの lint (rules/ で管理)
brew "shellcheck"                         # .sh の静的解析 (pre-commit local hook)
brew "tirith"                             # URL/コマンドセキュリティ CLI (zsh と Claude Code の二層で使う)
brew "bats-core"                          # bash のテストフレームワーク (scripts/tests/ をローカルで回す)

# --- フォント ---
cask "font-hackgen-nerd"                  # ターミナル用 日本語プログラミングフォント (Hack + 源柔ゴシック, Nerd Font 内蔵)
cask "font-plemol-jp-nf"                  # ターミナル用 日本語プログラミングフォント (IBM Plex Mono + IBM Plex Sans JP, Nerd Font 内蔵)

# --- Go言語ツール ---
go "golang.org/x/tools/gopls"             # Go言語サーバー（LSP）
go "honnef.co/go/tools/cmd/staticcheck"   # Go静的解析ツール
