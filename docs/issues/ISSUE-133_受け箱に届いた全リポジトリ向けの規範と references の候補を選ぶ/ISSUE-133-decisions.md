# ISSUE-133 の採否 (2026-11-15 に判断の保存先から写した)

この表は `knowledge_ledger.records` が台帳の判断の保存先から生成する。手で直さない。記号の意味は ISSUE-146-spec.md の判定表が持ち、理由の文面は判断の保存先が持つ。

| 件 | 箇条の冒頭 | 採否 | 判断した側 | 記号 | 反映先 |
| --- | --- | --- | --- | --- | --- |
| K133-001 | 独自ヘッダで秘密を送る配線 (認証プロキシの service token など)… | 採る | 人 |  |  |
| K133-002 | 秘密の値を会話・ログ・subagent に出さないため、書き捨てのシェルスクリプ… | 採る | 人 |  |  |
| K133-003 | 値の形に関する自分の知識も、仕様を引くまでは未確認の前提として扱う。秘密の形式が… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-004 | 秘密が漏れた範囲を確かめるとき、元の transcript から値をメモリの上で… | 採る | 人 |  |  |
| K133-005 | 利用者に DevTools のスクリーンショットを頼むと、リクエストヘッダの `… | 採る | Claude | M | K133-178 に統合 |
| K133-006 | ブラウザ自動化の拡張機能が開いた新しいタブには、利用者が別のタブで通した HTT… | 採らない | Claude | R6 |  |
| K133-007 | 長さの検査より前に全文へ走る正規化を足すと、それまで有界だった入力に無界の処理が… | 採る | Claude | 14 | ~/.claude/references/security.md の新しい節「正規化と検査の順序」 |
| K133-008 | 反証役が「今の設定では到達しない」と判定したセキュリティの指摘でも、多層防御とし… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-009 | URL からホストを `split("://")` と `split("/")`… | 保留 | Claude | H6 |  |
| K133-010 | Make の `$(filter prefix_%,$(VAR))` で名前空間… | 採る | Claude | D | ~/.claude/references/security.md の「charset 検証を名前空間の検証と兼用した事故」節へ実例を足す |
| K133-011 | 多層防御のつもりで、下の層の判定 (テナントの一致) に渡す2つのラベルを同じ値… | 採る | Claude | 14 | ~/.claude/references/security.md の新しい節「層の入力の出所」 |
| K133-012 | 認可の経路を、構築子を private にした証人型で表し、照合を通った値でしか… | 保留 | Claude | H6 |  |
| K133-013 | 端末に出す外から来た値は、制御文字だけでなく Unicode の書式文字 (bi… | 採る | Claude | 14 | ~/.claude/references/security.md の新しい節「見えない文字と書式文字」 |
| K133-014 | 本番で確かめるための一時的なエンドポイントは、本物の状態とは別の鍵だけを扱い、本… | 採らない | Claude | R4 |  |
| K133-015 | 削除した API トークンの失効を、値を画面に出さずに HTTP のステータスだ… | 採る | Claude | M | K133-016 に統合 |
| K133-016 | 401という数字だけでは「失効したトークンを拒んだ」と「トークンが届いていない」… | 採る | Claude | 14 | ~/.claude/references/security.md の新しい節「秘密の値を会話に出さずに扱う」 |
| K133-017 | 1Password CLI の `op read` の失敗の理由は stderr… | 保留 | Claude | H6 |  |
| K133-018 | シークレットマネージャの CLI で値を変数に読み、ログに秘匿値が含まれないこと… | 採る | 人 |  |  |
| K133-019 | 巨大な書き出しの SVG を追跡下へ入れる前の全文の確認は、座標データ (d・t… | 保留 | Claude | H1 |  |
| K133-020 | 経路に依存する測定 (WebSocket のアイドル切断など) は、測定の前後で… | 保留 | Claude | H3 |  |
| K133-021 | 空のダッシュボードを読む前に、その構成で何が記録される設定かを確かめる。記録を設… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-022 | fail-open の作りの機構で「拒否が出ない」は、機構の不在とも窓の境界とも… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-023 | ビルドのログの警告を語 (warning) で数えると、コンパイラのコマンドライ… | 保留 | Claude | H3 |  |
| K133-024 | E2E の失敗が症状ばらばらでも、テストが作るデータに埋まった時刻と backe… | 採らない | Claude | R4 |  |
| K133-025 | E2E の list reporter のログからテストごとの最後の結果を (状… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-026 | GitHub の jobs API が、needs で後続を持つ集約ジョブを i… | 採る | 人 |  |  |
| K133-027 | 接続の寿命の合否を、接続の生存時間ではなく upgrade の成立 (HTTP … | 採る | Claude | M | K133-028 に統合 |
| K133-028 | 接続が想定外の時刻に切れたとき、同じ経路と同じ時刻に「同じ keepalive … | 採る | Claude | D | ~/.claude/references/observation.md の「対照側も同じだけ壊れる」節 |
| K133-029 | 1回だけの測定で「keepalive で接続が保たれる」と書きかけ、2回目の測定… | 採る | Claude | M | K133-030 に統合 |
| K133-030 | 測定の結果を文書へ書くとき、ログに無い時刻を推定で書いたり、区間を取り違えたりし… | 採る | 人 |  |  |
| K133-031 | PR の本文に数値を写すとき、測り方 (どの版か、単独か通しか) を落とすと、数… | 採る | Claude | M | K133-030 に統合 |
| K133-032 | macOS で処理の wall clock の時間が普段の10倍に跳ねたら、原因… | 採る | Claude | M | K133-065 に統合 |
| K133-033 | 長時間の E2E が1件だけ時間切れで落ちたとき、trace の通信記録から「今… | 採らない | Claude | R4 |  |
| K133-034 | 要素の数で書いた a11y の検査 (`getByRole("status")`… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-035 | LLM の評価は1回ごとに揺れるので、不合格の顔ぶれを2回分並べて「同じケースが… | 採らない | Claude | R4 |  |
| K133-036 | E2E の line reporter のログからテストの ID の集合を作ると… | 採らない | Claude | R6 |  |
| K133-037 | CI のログを grep した件数は、テスト名や、Actions がログに出すス… | 保留 | Claude | M | K133-023 に統合 |
| K133-038 | Monitor の grep に `failed` のような一般の語を入れると、… | 保留 | Claude | M | K133-023 に統合 |
| K133-039 | グローバルの CLAUDE.md の観測のカテゴリにある「0件・空・緑を健全の根… | 採らない | 人 |  |  |
| K133-040 | 配信の前後で E2E の実行テストの集合を突き合わせるとき、キーを「projec… | 採らない | Claude | R4 |  |
| K133-041 | `vitest list --json` の件数は、実際に実行されたテストの数と… | 採る | Claude | 14 | ~/.claude/references/tool-vitest.md (新規) |
| K133-042 | 応答は成功だが遅い依存先 (scale to zero の cold start… | 採らない | Claude | R4 |  |
| K133-043 | サーバーの側で backend を呼び、結果を包んで返す同一オリジンの経路は、失… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-044 | 本番のログの雑音を探針や CI に帰属させるとき、探針の件数と本番のログの件数を… | 採らない | Claude | R4 |  |
| K133-045 | 本番のレート制限の実効は、handler が DB を触る前に400で弾く入力で… | 採らない | Claude | R4 |  |
| K133-046 | TTL の消滅を本番で確かめるときは、書いた直後に読むだけでは足りず、期限の手前… | 保留 | Claude | M | K133-020 に統合 |
| K133-047 | 置き換え前の結果を golden set として採り、1ページ目で打ち切られる結… | 採らない | Claude | R4 |  |
| K133-048 | 外部 API の採取で、採り直した結果のうち前回と重なる組を並びまで cmp す… | 採らない | Claude | R4 |  |
| K133-049 | ログの検索 API の1回の上限に当たった窓を、上限を下回るまで半分に割って読み… | 保留 | Claude | H3 |  |
| K133-050 | 観察期間とログの保存期間が同じ長さだと、期間の終わりに一度に数えた時点で、期間の… | 採らない | Claude | R4 |  |
| K133-051 | 道具やスクリプトを書き換えたあと、書き換える前の全出力を残して流し直し、全ファイ… | 採る | 人 |  |  |
| K133-052 | フォーマッタの更新で設定ファイルの引用符が変わったとき、変更前後を YAML の… | 採る | Claude | M | K133-051 に統合 |
| K133-053 | ソースの木に紛れたゴミ (.DS_Store、余計なサブディレクトリ) への耐性… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-054 | コミットの後に gitleaks を回すなら `gitleaks git --l… | 採る | Claude | 14 | ~/.claude/references/tool-gitleaks.md (新規) |
| K133-055 | 差分ベースの lint (`origin/main...HEAD` を見るもの)… | 保留 | Claude | H3 |  |
| K133-056 | git grep は未追跡のファイルを見ないので、まだ add していない新しい… | 採る | Claude | 14 | ~/.claude/references/tool-git.md (新規) |
| K133-057 | 読み取り専用の SQL の probe を本番系へ流す前に、ローカルで書いてから… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-058 | 計画の決定事項を implementer に渡すため、計画のファイルから番号で … | 採らない | Claude | R1 | ~/.claude/references/observation.md |
| K133-059 | テストの掃除の helper が一覧の失敗を `let Ok(..) else … | 採る | Claude | D | ~/.claude/rules/testing-practices.md の置き換えの項と ~/.claude/references/testing.md |
| K133-060 | 判定の意味を変えたとき、その出力を「保存が済んだ」などの証拠に使っていた手の s… | 採らない | Claude | R4 |  |
| K133-061 | 揺れの原因を推測して印を付ける仕組みを作ったが、その現象は起きておらず、仕組みの… | 採らない | Claude | R4 |  |
| K133-062 | ランタイムの意味論の問い (削除が予約を消すか、再試行の回数と予約の扱い) は、… | 採らない | Claude | R4 |  |
| K133-063 | ログを出さない内部の同期が、別の処理の結果を変えていた。再試行で通った理由がログ… | 採らない | Claude | R4 |  |
| K133-064 | 設定の読み出しを「確認済み」として文書に書いたが、時刻を並べると、変更 (一時的… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-065 | 実ビルドを走らせる vitest が5000msのタイムアウトに5348msで落… | 採る | 人 |  |  |
| K133-066 | 一斉に赤くなった E2E を見て、既知の似た罠 (許可の外れ) に飛びつくと誤診… | 採らない | Claude | R4 |  |
| K133-067 | ローカルの E2E の失敗が今回の変更のせいかを切り分けるとき、既知の flak… | 保留 | Claude | H3 |  |
| K133-068 | UI Automation の要素名の部分一致で状態を判定すると、画面上のデータ… | 採らない | Claude | R4 |  |
| K133-069 | 統合テストが外部依存の不在を `println!` で知らせて早期 return… | 採る | Claude | D | ~/.claude/references/observation.md の「非 0 件も証明にならない」節 |
| K133-070 | 結果の置き場 (ログと xcresult) を同じパスへ上書きするテストのレシピ… | 採らない | Claude | R4 |  |
| K133-071 | `git grep -E` は POSIX ERE なので `\b` を単語境界… | 採る | 人 |  |  |
| K133-072 | bash の `set -e` は、`cd "$(git rev-parse -… | 採る | Claude | 14 | ~/.claude/references/tool-bash.md (新規) |
| K133-073 | `make -n` は再帰の `$(MAKE)` を含む行とその中で呼ばれるコマ… | 採る | Claude | 14 | ~/.claude/references/tool-make.md (新規) |
| K133-074 | macOS の zsh には `timeout` コマンドが無い (実測)。do… | 採らない | Claude | R5 |  |
| K133-075 | zsh で `=` から始まる語を引数に置くと、`=cmd` のコマンドパス展開… | 採る | 人 |  |  |
| K133-076 | `git rev-parse --short A B` のように `--shor… | 採らない | Claude | R5 |  |
| K133-077 | `until ! pgrep -f "<コマンド>"; do sleep N; … | 採る | 人 |  |  |
| K133-078 | 同じ生成物ディレクトリを作り直す2つのタスクランナーの recipe (全体のゲ… | 採らない | Claude | R4 |  |
| K133-079 | Edit ツールは new_string の中の `\uXXXX` を JSON… | 採る | Claude | 14 | ~/.claude/references/tool-claude-code.md (新規) |
| K133-080 | zsh ではクォートしないグロブ (`grep -r --include=*.t… | 採る | 人 |  |  |
| K133-081 | zsh で小文字の `path` を変数名に使うと PATH と結びついて上書き… | 採る | 人 |  |  |
| K133-082 | zsh で `${(...)//:/ }` のような配列の分割でコマンドの引数を… | 採らない | Claude | R4 |  |
| K133-083 | macOS の標準の bash は3.2なので、`${var^^}` や連想配列… | 採る | Claude | 14 | ~/.claude/references/tool-bash.md (新規) |
| K133-084 | macOS の `mktemp -d` (テンプレートなし) は TMPDIR … | 採る | Claude | 14 | ~/.claude/references/tool-macos.md (新規) |
| K133-085 | BSD grep の `-E` は、繰り返しの上限 `{0,N}` の N が2… | 採らない | Claude | R5 |  |
| K133-086 | `set -euo pipefail` の bash スクリプトで `trap … | 採らない | Claude | R6 |  |
| K133-087 | `git rm` 済みのパスを `git add` に渡すと pathspec … | 採らない | Claude | R5 |  |
| K133-088 | 利用者に頼んだコマンドを `;` で繋ぐと、前段が一時的な切断で落ちても後段が走… | 採らない | Claude | R1 | ~/.claude/references/observation.md |
| K133-089 | `pre-commit install` に `-q` を付けると unreco… | 採らない | Claude | R6 |  |
| K133-090 | サブシェルの中で `$PWD/../x.json` を出力先にしたら、ルートで実… | 採らない | Claude | R4 |  |
| K133-091 | squash マージではローカルのブランチが `git branch -d` で… | 採る | Claude | D | ~/.claude/references/git-workflow.md の「squash マージ後の取り込み確認」節 |
| K133-092 | `git ls-remote --tags` の注釈付きタグは `<name>^… | 採らない | Claude | R4 |  |
| K133-093 | `perl -CSD` だけだと、コマンドに書いた日本語がバイト列のままで、日本… | 採る | 人 |  |  |
| K133-094 | perl の `s\|\|\|` で区切りに `\|` を使い、置換の文字列にクロージャ… | 採る | Claude | 14 | ~/.claude/references/tool-perl.md (新規) |
| K133-095 | Makefile のターゲットを「`<target>: ##` の最初の出現から… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-096 | ファイルを書き込むツールが「先に読め」で失敗したのを確かめないまま、同じ応答で後… | 採らない | Claude | R5 |  |
| K133-097 | SessionStart hook の command を `{ cd "$CL… | 採らない | Claude | R4 |  |
| K133-098 | hook の設定を読んでその command 文字列をテストから `sh -c`… | 採る | Claude | D | ~/.claude/references/observation.md の「プローブの構造上の位置」節 |
| K133-099 | 同じ作業木で2つの implementer を並列に動かすとき、brief にフ… | 採る | 人 |  |  |
| K133-100 | 設計書を書いたあと、別の subagent に「計画を立てるのに足りない点」だけ… | 採る | Claude | 14 | ~/.claude/references/delegation.md に新しい節「設計書を点検させる観点」 |
| K133-101 | コードレビューの委譲先が confidence 88 で指摘した退行は、検査対象… | 採る | 人 |  |  |
| K133-102 | 調査に前提を疑う役を1体入れて初めて、「Node 製の CLI」と思っていたもの… | 採る | 人 |  |  |
| K133-103 | 実装の前に、呼び出し箇所、実行系、backend の側、前提を疑う、の4観点の読… | 採る | Claude | M | K133-102 に統合 |
| K133-104 | サブエージェントの Web 調査が「確認済み」とした記述 (出典のページに無い言… | 採る | 人 |  |  |
| K133-105 | サブエージェントが `.test.ts` を除外した grep で検索し、共有モ… | 採らない | Claude | R5 |  |
| K133-106 | docs だけの PR でも simplify の4観点とボーイスカウトを回した… | 採らない | Claude | R1 | ~/.claude/skills/pre-merge-quality-gate/SKILL.md |
| K133-107 | 最終レビューを「観点ごとの reviewer 4体と、観点ごとに1体の反証役」の… | 採る | 人 |  |  |
| K133-108 | Workflow の結果の通知が指す出力ファイルを JSON として読むと Ex… | 採る | Claude | 14 | ~/.claude/references/tool-claude-code.md (新規) の Workflow の節 |
| K133-109 | Workflow で走っている読み取り専用の subagent に、ユーザーが … | 採らない | Claude | R6 |  |
| K133-110 | レビューを「書いた直後」と「レビューを反映した後の差分だけ」の2回に分けると、反… | 採る | 人 |  |  |
| K133-111 | タスクごとのレビューを全部通ったあとでも、ブランチ全体の最終レビューを最上位のモ… | 採らない | Claude | R4 |  |
| K133-112 | タスクごとの implementer と、秘密情報を扱うタスクだけ上位のモデルの… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-113 | simplify の altitude の観点が、緑で変異注入まで済んだ実装に「… | 採らない | Claude | R4 |  |
| K133-114 | 設計案を並列で出させる前に、前提となるツールの挙動を1体の probe エージェ… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-115 | 同じ問いを2つの担当に別の測り方 (高頻度の poll と間隔の途中の標本、ログ… | 採らない | Claude | R4 |  |
| K133-116 | 外向けの報告文の下書きを、行ごとに subagent に一次資料で反証させると、… | 採らない | Claude | R4 |  |
| K133-117 | 探索で状態を変える subagent の前後に DB の該当行をスナップショット… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-118 | レビュアーの「RLS のポリシーが X を許す」という指摘を、migration… | 採る | Claude | M | K133-101 に統合 |
| K133-119 | Bash を持たないレビュー役は条件付きの OK を返した。実測した出力 (rc… | 採らない | Claude | R4 |  |
| K133-120 | 変異注入の json を implementer に書かせておくと、コントローラ… | 採らない | Claude | R4 |  |
| K133-121 | 長時間のゲートをコントローラで回し、implementer には移したテストの名… | 採らない | Claude | R4 |  |
| K133-122 | subagent への dispatch に「コミットして」と書き、共通の制約の… | 採らない | Claude | R4 |  |
| K133-123 | 委譲の規範か `references/delegation.md` に、「Min… | 採らない | Claude | R4 |  |
| K133-124 | 最上位のモデルの subagent が利用上限 (429) で落ちたとき、作業ツ… | 採る | 人 |  |  |
| K133-125 | 長い Workflow の subagent が上限で失敗すると、Workflo… | 採らない | Claude | R6 |  |
| K133-126 | Workflow の再開を scriptPath と resumeFromRun… | 採らない | Claude | R6 |  |
| K133-127 | Workflow の isolation: worktree は、作業ブランチの… | 採らない | Claude | R6 |  |
| K133-128 | worktree の中の subagent は、本体の checkout の側の… | 採らない | Claude | R5 |  |
| K133-129 | `.cache/` の下の隔離コピーや複製は、`.cache/` が ignor… | 採らない | Claude | R4 |  |
| K133-130 | Playwright の webServer を固定のポートかつ `reuseE… | 採らない | Claude | R5 |  |
| K133-131 | 1回最大45秒の承認待ちを同じ hook の中で2回以上重ねると、hook の時… | 採らない | Claude | R6 |  |
| K133-132 | JavaScript で描画する公式ヘルプのページは、WebFetch と cu… | 採らない | Claude | R6 |  |
| K133-133 | 出力の言語を日本語に指定していても、英語の subagent の報告を読んだ直後… | 保留 | Claude | H5 |  |
| K133-134 | 背景のプロセスの起動、子プロセス、kill を1つの Bash コマンドに詰めず… | 採る | 人 |  |  |
| K133-135 | リリースの手順を just の recipe に閉じ込め、その recipe の… | 採る | Claude | 14 | ~/.claude/references/tool-claude-code.md (新規) の auto mode の節 |
| K133-136 | トークンや API の権限を探るためにエンドポイントを続けて叩くと、分類器が資格… | 採らない | 人 |  |  |
| K133-137 | パスワードマネージャの CLI で項目の一覧をタイトルとカテゴリに絞ると通った。… | 保留 | Claude | H1 |  |
| K133-138 | 書き捨てのスクリプトで `op read` の値を変数に取るプローブは、分類器が… | 保留 | Claude | M | K133-137 に統合 |
| K133-139 | 分類器が判定を返さない (no verdict の一時エラー) 状態が5回続いた… | 採らない | Claude | R6 |  |
| K133-140 | 2026-11-04の仕分けで、別のリポジトリから、auto mode では `… | 採らない | Claude | R6 |  |
| K133-141 | /goal の Stop hook は DoD の各項目を transcript… | 採る | Claude | 14 | ~/.claude/references/tool-claude-code.md (新規) の /goal の節 |
| K133-142 | マージが利用者の `!` の操作のリポジトリでは、goal の実行中にマージを待… | 採る | Claude | M | K133-141 に統合 |
| K133-143 | 条件に CI のステップの分布を書く前に、`gh run view --json… | 採らない | Claude | R4 |  |
| K133-144 | /goal に貼った条件文の中ほどが欠落した。2450文字で上限 (4000) … | 採らない | Claude | R6 |  |
| K133-145 | DoD に「作業ツリーはクリーン」と「記録の追記のコミットは人の指示を待つ」を同… | 採る | Claude | M | K133-141 に統合 |
| K133-146 | DoD の「止まってよい条件」を待ちの原因の種類 (承認のタイムアウト) で書い… | 採る | Claude | M | K133-141 に統合 |
| K133-147 | DoD の止まってよい条件に「auto mode の分類器が必要な操作を止めた」… | 採る | Claude | M | K133-141 に統合 |
| K133-148 | 条件文で CI を `gh pr checks <N> --watch; ech… | 採らない | Claude | R1 | ~/.claude/references/observation.md |
| K133-149 | 単体バイナリで配られる CLI を pin するとき、中身のランタイム (`de… | 採らない | Claude | R4 |  |
| K133-150 | lockfile で依存を固めた日に、推移的な依存に公開から日の浅い版が混ざる。… | 採る | Claude | 14 | ~/.claude/references/tool-pnpm.md (新規) |
| K133-151 | 長時間の外部プロセスを回すタスクランナーには、既定でプロセスグループ単位の時間の… | 採る | Claude | D | ~/.claude/references/observation.md の「live smoke」節 |
| K133-152 | Homebrew の自動更新で手元の just がリポジトリの canonica… | 採る | Claude | 14 | ~/.claude/references/tool-just.md (新規) |
| K133-153 | 依存の版を選ぶときのクールダウンを、mise のツールにも `mise late… | 採らない | Claude | R4 |  |
| K133-154 | mise の aqua backend で checksum だけのツールは、h… | 採らない | Claude | R6 |  |
| K133-155 | just と pre-commit の GitHub Release には上流の… | 採らない | Claude | R6 |  |
| K133-156 | ローカルのサービスのポートを固定するとき、既定のポートや OS の一時ポートの範… | 採る | 人 |  |  |
| K133-157 | グローバル CLAUDE.md の「完了前に `.cache/` の書き捨てを消… | 保留 | 人 |  |  |
| K133-158 | repository ruleset はブランチとタグで target が別系統… | 保留 | Claude | H3 |  |
| K133-159 | 文書や設定のコメントに「既定でこう上書きされる」のような未検証の断定を書くと、レ… | 採らない | Claude | R4 |  |
| K133-160 | release note を tag の push 前に書き手自身が読み直すと、… | 採らない | Claude | R4 |  |
| K133-161 | 他のリポジトリのセッションへの依頼の本文に、受け手の現在値 (受け手の apm.… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-162 | dotfiles のメモリにはあるが、他のリポジトリのセッションには届かない知見… | 採る | 人 |  |  |
| K133-163 | 「index の件数が0なら全件の同期、そうでなければ差分の同期」という判定は、… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-164 | 消す前の worktree の確認で、ahead/behind がどちらも0で … | 採らない | Claude | R4 |  |
| K133-165 | 常時ロードの索引を縮めるとき、行を言い換えずに子の索引へ逐語で移し、移動先に1回… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-166 | 重複を消すために2つの実測を1つの文へ畳んだら、どの日にどの値を読んだか、どの変… | 採る | Claude | D | ~/.claude/references/canonical.md の「散文を参照へ書き換えたあとの検算」節 |
| K133-167 | 複数のファイルへの書き捨ての置換や差分の適用は、置換ごとに元の文字列 (原文の抜… | 採る | 人 |  |  |
| K133-168 | 既存の関数の doc コメントと関数の間に新しい関数を挿すと、既存の doc が… | 採らない | Claude | R4 |  |
| K133-169 | 「セッションの終了時に起動したコンテナを落とすか確かめる」規則をあるリポジトリの… | 採る | Claude | 14 | ~/.claude/references/host-environment.md に新しい節「起動したものを使い終わったら落とす」 |
| K133-170 | 本番の DB の読み取りが分類器に止められたとき、迂回せず利用者に `!` で実… | 採らない | Claude | R4 |  |
| K133-171 | 利用者に `!` で回してもらうコマンドにプレースホルダ (`<...>`) を… | 採らない | Claude | R4 |  |
| K133-172 | 利用者が `!` で打った長いコマンドは120秒で裏へ回り、利用者には失敗に見え… | 採らない | Claude | R6 |  |
| K133-173 | Claude Code の `!` の前置で `sudo <bin> &` のよ… | 採らない | Claude | R6 |  |
| K133-174 | AskUserQuestion で「Other に入力して」という選択肢を置くと… | 採らない | Claude | R6 |  |
| K133-175 | メールの確認コードは10分程度で失効する。利用者に入力を頼むときは、入力欄に入れ… | 採らない | Claude | R4 |  |
| K133-176 | トークンの回し方の手順には、計画して回す場合 (新しいトークンで確かめてから古い… | 採らない | Claude | R4 |  |
| K133-177 | 非公開のリポジトリの一部を、履歴を持たない別のリポジトリへ byte 一致で一方… | 採らない | Claude | R4 |  |
| K133-178 | 設定の画面のスクリーンショットで、画面に文字で並んでいた Webhook の U… | 採る | Claude | 14 | ~/.claude/CLAUDE.md の「攻撃者が使える面を最小に保ち防御を 1 層に頼らない」カテゴリ (予算に入らなければ references/security.md の新しい節) |
| K133-179 | advisory の URL の owner が見慣れない形 (本家の org … | 採らない | Claude | R4 |  |
| K133-180 | 依存を上げたあとの E2E の失敗は、上げる前の lock に一部だけ戻す A/… | 保留 | Claude | M | K133-067 に統合 |
| K133-181 | GitHub の runner の apt の詰まりは、成功した基準の job … | 採らない | Claude | R4 |  |
| K133-182 | 配信の前後で公開ページの本文が違ったとき、配信をまたがない2回の採取を対照にして… | 採らない | Claude | R4 |  |
| K133-183 | trace が無くても、backend の SQL のデバッグログの rows_… | 採らない | Claude | R4 |  |
| K133-184 | 「戻った」を判定する探針は、新しい版で ok を返すことと、古い版の期待を当てた… | 採る | Claude | D | ~/.claude/references/observation.md の「何を何件見たか」節 |
| K133-185 | `xcodebuild test -only-testing:<Target>/… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-186 | 変更の前後で成果物 (xcresult から作った JSON) を比べたとき、変… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-187 | 検証用の手順書を書く前提のスパイクでは、挙動を変えるガード (二重入力を止めるな… | 採らない | Claude | R4 |  |
| K133-188 | 「作られないはず」のファイル (SQLite を EXCLUSIVE で開いたと… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-189 | 測定値がおかしいとき (読み直し27万回、メモリ16.9GB) は、件数を期待値… | 採らない | Claude | R4 |  |
| K133-190 | 変換の規則をコードから導いて予測するより、今配信中の成果物の設定ファイルを AP… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-191 | 自動化したブラウザでどのサイトを開いても、同じ origin のランダムなパスへ… | 採らない | Claude | R4 |  |
| K133-192 | ビルド成果物のバイト数の差を測るときは、対照を同じディレクトリで作る。別のパス … | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-193 | 計画の前提 (外部 SaaS の API の振る舞い) を、実装の前に実サービス… | 採らない | Claude | R4 |  |
| K133-194 | distroless イメージの CA バンドルを取り出して数えるとき (対照の… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-195 | 一次資料そのものも版と日付で古びる。2026-11-10の仕分けで、同じリポジト… | 採る | 人 |  |  |
| K133-196 | `git mv` の直後に `git stash` と `git stash p… | 採らない | Claude | R4 |  |
| K133-197 | `kill(pid, 0)` は zombie に成功を返す。自分の直接の子を … | 採る | Claude | 14 | ~/.claude/references/tool-posix.md (新規) |
| K133-198 | ホストの `sed` が GNU のとき、BSD 流の `sed -i '' <… | 採らない | Claude | R5 |  |
| K133-199 | 逆向きに、macOS の BSD sed は BRE の `\?` を解釈しない… | 採らない | Claude | R1 | ~/.claude/references/observation.md |
| K133-200 | `git grep` には `-s` オプションが無い (実測)。grep の癖… | 採らない | Claude | R5 |  |
| K133-201 | バックグラウンドの Bash の中で `&` を付けて見張りを切り離すと、親の終… | 採らない | Claude | R6 |  |
| K133-202 | Bash ツールの run_in_background の完了通知の終了コードは… | 採る | 人 |  |  |
| K133-203 | `git ls-tree -r` の pathspec は、ファイル名の接頭辞に… | 採る | Claude | 14 | ~/.claude/references/tool-git.md (新規) |
| K133-204 | 実行の権限が無い git hook は、git が hint を1行出すだけで飛… | 採る | Claude | 14 | ~/.claude/references/tool-git.md (新規) |
| K133-205 | `git ls-remote origin refs/heads/main` の… | 採らない | Claude | R4 |  |
| K133-206 | zsh で `"$rev:<path>"` のように変数のすぐ後ろに `:` が… | 採らない | Claude | R1 | ~/.claude/references/observation.md |
| K133-207 | レビュー役に隔離コピーでのビルドと変異注入を許すと、ビルド成果物 (`targe… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-208 | 網羅の検査役は、領域の担当が報告したファイルの一覧を渡して「grep に当たるの… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-209 | simplify の4観点 (再利用、簡素化、効率、高さ) の並列レビューで、高… | 採らない | Claude | R1 | ~/.claude/skills/pre-merge-quality-gate/SKILL.md |
| K133-210 | レビューの指摘をそれぞれ反証させる検証役を並べたら、27件中27件が「本物」と返… | 採る | Claude | D | ~/.claude/references/delegation.md の「反証者への既定値の指示」節 |
| K133-211 | 反証レビューの観点を「障害がいちばん困るタイミングで手順に従ったら」にすると、漏… | 採らない | Claude | R4 |  |
| K133-212 | critic に「書いてあるログの文言が、手順どおりに操作したときに本当に出るか… | 採らない | Claude | R4 |  |
| K133-213 | PostToolUse の hook がファイルを整形し直しても、Claude … | 採らない | Claude | R4 |  |
| K133-214 | worktree では ignore したディレクトリ (道具の置き場など) が… | 採らない | Claude | R4 |  |
| K133-215 | 報告者の提案は、共通の規範に、PreToolUse の柵の hook には `o… | 保留 | Claude | H3 |  |
| K133-216 | Workflow で一次情報の調べものを3本並べて合成させる形は速くて広いが、合… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-217 | 「各 Task のテストが実装の前に赤、後に緑だったことをコントローラ自身が確か… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-218 | 推測の仮説が3つ外れた時点で止め、「一時的なログ・trace・ユニットでの再現で… | 採らない | Claude | R4 |  |
| K133-219 | レビューが「未測定の前提」を指摘したら、議論せず実測で決着させる (同じリポジト… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-220 | 「読むだけ」の allowlist に入れがちな道具にも書き込む引数がある。`r… | 保留 | Claude | H6 |  |
| K133-221 | PreToolUse の hook の ask は、settings の per… | 採らない | Claude | R6 |  |
| K133-222 | Bash ツールの安全検査は、zsh の入れ子のパラメータ展開 (`${${x#… | 採らない | Claude | R5 |  |
| K133-223 | `gh extension install` は auto mode の分類器に… | 採る | Claude | M | K133-135 に統合 |
| K133-224 | /goal の評価器は DoD の停止条件も文言で判定する。AskUserQue… | 採る | Claude | M | K133-141 に統合 |
| K133-225 | /goal の DoD に「公開ページの前後一致」と書くと、仕組み上ゆれるページ… | 採る | Claude | M | K133-141 に統合 |
| K133-226 | 新しいリポジトリの土台づくりで、バージョンマネージャーを使わず、版と sha25… | 採らない | Claude | R4 |  |
| K133-227 | 報告者の提案は、依存の更新の triage の手順に「落ちたテストは、テストを直… | 採らない | Claude | R4 |  |
| K133-228 | ホスティング事業者の公式 CLI を REST の直叩きへ置き換える前に、nod… | 採らない | Claude | R4 |  |
| K133-229 | `docker volume prune -f` は現行の Docker では匿… | 採らない | Claude | R6 |  |
| K133-230 | dangling な匿名ボリュームの出所は、使い捨てのコンテナを `debian… | 採る | Claude | 14 | ~/.claude/references/tool-docker.md (新規) |
| K133-231 | `docker image prune -a` は、registry から pu… | 採らない | Claude | R4 |  |
| K133-232 | 報告者の提案は、ホスト全体に効く掃除 (Docker の匿名ボリュームと未使用イ… | 採らない | Claude | R4 |  |
| K133-233 | 短いコンテナの peak は、until ループで `docker stats … | 採らない | Claude | R4 |  |
| K133-234 | `op` の存在を冒頭で要求する Makefile は CI の runner … | 採らない | Claude | R5 |  |
| K133-235 | 利用者が料金の前提で決めた直後に、決定の根拠を一次資料で読み直して誤りを見つけ、… | 採らない | Claude | R4 |  |
| K133-236 | レビューが足した方針は、決定の棚へ入れる前にユーザーへ「足した方針として決定にし… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-237 | 書式の規約 (squash の subject の番号の形など) をリポジトリの… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-238 | skill の規約から外れる例外を「このリポジトリは前提 X を持たないので射程… | 採らない | Claude | R4 |  |
| K133-239 | 要件の文面から「導ける」と判断して実装した挙動が、別の読みも成り立つと crit… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-240 | 修正の波で型の断言 (`as`) を型ガードに替えると、起動時の取得が形の違う行… | 採らない | Claude | R1 | ~/.claude/rules/testing-practices.md |
| K133-241 | 画面のスクリーンショット (screencapture) と osascript… | 採らない | Claude | R5 |  |
| K133-242 | 自分の検算で、一覧をファイル名から上端・下端に振り分けた記述は、宣言の top … | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-243 | 赤のテストの数が多いときは、失敗の理由の文字列を数えて分類してから原因を決める。… | 採らない | Claude | R4 |  |
| K133-244 | E2E のログに転送されたブラウザの console の行で、既存の警告が変更か… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-245 | `git diff <base>..HEAD` (2点) を PR の差分として… | 採らない | Claude | R4 |  |
| K133-246 | `git diff --name-only ... \| xargs wc -l`… | 採らない | Claude | R4 |  |
| K133-247 | 長い検証 (ローカルの全件ゲート) をバックグラウンドで回している間に git … | 採らない | Claude | M | K133-078 に統合 |
| K133-248 | `git commit --only -- <paths>` を使うと、inde… | 採らない | Claude | R4 |  |
| K133-249 | E2E の対話用に VM への SSH のポート転送 (`ssh -f -N -… | 保留 | Claude | H5 |  |
| K133-250 | auto mode では、自分の settings.local.json の M… | 採る | Claude | M | K133-135 に統合 |
| K133-251 | DoD の「X を最終報告へ写してから Y を消す」を、最終報告でまとめて写すつ… | 採る | Claude | M | K133-141 に統合 |
| K133-252 | 未追跡のファイルが cherry-pick 先のパスと重なったので、先に `.c… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-253 | push されずにローカルにだけ残っていた古いブランチの2コミットを、新しいブラ… | 採る | Claude | 14 | ~/.claude/references/git-workflow.md に新しい節「hook が走らない取り込みの経路」 |
| K133-254 | ユーザーがエディタで開いていた下書きを、ignore された `.cache/`… | 採る | Claude | 14 | ~/.claude/references/host-environment.md に新しい節「利用者が開いているファイルを動かさない」 |
| K133-255 | 2026-11-13の仕分けで、別のリポジトリから届いた。Makefile のレ… | 採らない | Claude | R4 |  |
| K133-256 | 2026-11-13の仕分けで、別のリポジトリから届いた。`printf '%s… | 保留 | Claude | H6 |  |
| K133-257 | トークンを作り直したかの確認は、シークレットの一覧の更新日時だけでは「古いトーク… | 採る | Claude | 14 | ~/.claude/references/tool-1password.md のトークンの回し方の節 |
| K133-258 | 公開されたサプライチェーン攻撃の記事の IOC (ブランチ名・PR のタイトル・… | 採る | Claude | 14 | ~/.claude/references/tool-gh.md (新規) |
| K133-259 | 2026-11-13の仕分けで、別のリポジトリから届いた。staging 向けの… | 保留 | Claude | M | K133-067 に統合 |
| K133-260 | 環境変数で値を受けるだけの just のレシピを、値を gh で引いた run … | 採らない | Claude | R4 |  |
| K133-261 | タイムゾーンに依る不具合のベースラインを、手元のタイムゾーンに加えて UTC と… | 保留 | Claude | H3 |  |
| K133-262 | 同じコミットで必須でない CI の同じテストが落ち、必須の CI では通っていた… | 保留 | Claude | M | K133-067 に統合 |
| K133-263 | 2026-11-13の仕分けで、別のリポジトリから届いた。Makefile の変… | 採る | Claude | 14 | ~/.claude/references/tool-posix.md (新規) |
| K133-264 | リポジトリ全体の監査を、互いに重ならない範囲を受け持つ読み取り専用の finde… | 採らない | Claude | R4 |  |
| K133-265 | 並行する PR を先に squash マージしたあとで、push 済みの別の P… | 採る | Claude | M | K133-135 に統合 |
| K133-266 | 依存を上げたあと、「ライブラリの内部を読んで確かめた」と版つきで書いたコメントの… | 採る | Claude | D | ~/.claude/CLAUDE.md の前提「コメントとテストコードは drift しやすく気づきづらい」項 (予算に入らなければ references/premises.md) |
| K133-267 | 依存の公開からの猶予 (クールダウン) を強めるときは、値をそろえるだけで終えず… | 採らない | Claude | R4 |  |
| K133-268 | gitleaks の generic-api-key が、テストの作り物の値 (… | 採らない | Claude | R6 |  |
| K133-269 | 外部コマンドの失敗の理由を下の層で長さの上限で切り、秘密の値を上の層 (呼び出し… | 採る | Claude | 14 | ~/.claude/CLAUDE.md の「攻撃者が使える面を最小に保ち防御を 1 層に頼らない」カテゴリ (予算に入らなければ references/security.md の新しい節) |
| K133-270 | 2026-11-15の仕分けで、別のリポジトリから届いた。gitleaks の既… | 採らない | Claude | R5 |  |
| K133-271 | デプロイ後の AI 探索型のモンキーテスト (section ごとに explo… | 採らない | Claude | R4 |  |
| K133-272 | クライアントでだけ描かれる文字列 (i18n のカタログなど) の配信を本番で確… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-273 | ユニットテストを持たない shell-out の殻 (秘密の値を URL に入れ… | 採る | Claude | D | ~/.claude/references/observation.md の「live smoke」節 |
| K133-274 | 変異注入のスクリプトで「変異が当たったか」を見る `cmp` を `$(case… | 採らない | Claude | R6 |  |
| K133-275 | 2026-11-15の仕分けで、別のリポジトリから届いた。zsh で `echo… | 採る | Claude | D | ~/.claude/references/observation.md の「成否が隠れる」節 |
| K133-276 | 2026-11-15の仕分けで、別のリポジトリから届いた。利用者の答えを設計の … | 採らない | Claude | R4 |  |
| K133-277 | 2026-11-15の仕分けで、別のリポジトリから届いた。レビュー役と反証役に、… | 採らない | Claude | R4 |  |
| K133-278 | 2026-11-15の仕分けで、別のリポジトリから届いた。並列レビューのレーンが… | 採らない | Claude | R1 | ~/.claude/references/observation.md |
| K133-279 | 2026-11-15の仕分けで、別のリポジトリから届いた。監査役と反証役の2票が… | 採る | Claude | D | ~/.claude/references/delegation.md の「反証者への既定値の指示」節 |
| K133-280 | 2026-11-15の仕分けで、別のリポジトリから届いた。Workflow の実… | 採る | Claude | 14 | ~/.claude/references/delegation.md に新しい節「fan-out の間の作業ツリー」 |
| K133-281 | /goal の Stop hook は DoD の文面を字句どおりに判定する。レ… | 採る | Claude | M | K133-141 に統合 |
| K133-282 | 2026-11-15の仕分けで、別のリポジトリから届いた。報告者の提案: 無人の… | 採る | Claude | M | K133-141 に統合 |
| K133-283 | 2026-11-15の仕分けで、別のリポジトリから届いた。言語の処理系の版をリポ… | 採る | Claude | 14 | ~/.claude/references/observation.md の「0 件・空・緑を健全と読む」節に新しい項 |
| K133-284 | 2026-11-15の仕分けで、上の項と同じまとめから届いた。処理系の版のガード… | 採る | Claude | M | K133-283 に統合 |
| K133-285 | 2026-11-15の仕分けで、別のリポジトリから届いた。並列の簡素化レビューで… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-286 | 2026-11-15の仕分けで、別のリポジトリから届いた。規約に沿っているかの散… | 採らない | Claude | R1 | ~/.claude/rules/markdown-practices.md |
| K133-287 | 2026-11-15の仕分けで、別のリポジトリから届いた。別のリポジトリの形を下… | 保留 | Claude | H3 |  |
| K133-288 | 2026-11-15の仕分けで、別のリポジトリから届いた。マージ前のレビューで、… | 採らない | Claude | R1 | ~/.claude/CLAUDE.md |
| K133-289 | 2026-11-15の仕分けで、別のリポジトリから届いた。文書が引く他ファイルの… | 採らない | Claude | R4 |  |
