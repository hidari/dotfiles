---
status: open
---

# refactor: cloudflare の security-audit skill を試用し重複する自作 skill を寄せる

## 背景

cloudflare/security-audit-skill の `security-audit` を apm で user スコープへ入れた (pin は `home/apm.yml`)。しばらく実際のリポジトリで使い、良ければ自作の security-blue-red-team の重複する部分をこちらへ寄せる。寄せる側の canonical は agentic-coding-tools なので、整理そのものは agentic-coding-tools への委譲になる。dotfiles で行うのは試用の記録と、寄せたあとの pin の更新まで。

### 導入時に読んだ既定の挙動 (pin した上流のコミットは2026-09-14のもので、2026-10-07に確認した時点の main 先頭)

こちらの運用と合わない既定が2つある。試用ではこれを手当てしながら回す。

- full audit の出力先の既定がホーム直下の新規ディレクトリ (`SKILL.md` の Full audit setup)。リポジトリ内で回すなら ignore 済みの `.cache/` 配下を明示して渡す
- recon・hunter・verifier を上限なしで並列に起動する。上限は予算 (budget) を指定したときだけ掛かり、既定は null。並列の本数を事前に告げて確かめる運用と衝突するので、回すときは予算を指定する

プロンプトインジェクション・隠し文字・外部通信は見つからなかった。同梱の検証スクリプト (.cjs) は引数のファイルと同梱の schema だけを読み、書き込みも子プロセスの起動もしない。

### 重複の見取り図 (導入時のスナップショット)

主に重なるのは security-blue-red-team だけで、他の自作 skill はキーワードが偶然当たっただけだった。

- red-team の Layer 1 (静的) と Layer 4 (高リスクの静的): 部分的に重複。上流は recon・カバレッジ台帳・独立検証まで持つ。寄せる第一候補
- red-team の Layer 2 / 3 (staging への受動・能動 HTTP): 衝突。上流はデプロイ済みの対象への送信を禁じる。自作に残す
- findings.json の契約 (severity の段階・fingerprint・判定): 衝突。同名のファイルで schema が噛み合わない。寄せる前にどちらかへ統一するか変換を挟む
- 出力先 (`docs/security-reviews/<日付>/`): 衝突。上流は対象の外か ignore 済みのディレクトリだけを許す。寄せるなら上流の規則に合わせる
- ヘッダ・Cookie のチェックリスト指摘: 衝突。上流はフラグの欠落だけでは脆弱性と数えない。上流の基準に寄せる
- blue-team Mode B の静的監査 (認証認可・入力検証・RLS): 部分的に重複。ログのカバレッジは上流に無い。静的な部分は寄せ、ログは残す
- blue-team Mode A (優先度と工数のトリアージ): 補完。上流は改善計画を作らない。残すが、上流の出力を読むなら変換が要る
- 本番ゲート・allow_targets・送信量の上限: 補完。上流はローカル実行の隔離だけを守る。残す
- security-cleanup・security-profile: 重複なし。残す

### 公式 plugin との比較 (2026-10-16 のスナップショット)

公式 marketplace に claude-security (0.12.0) と security-guidance (2.0.14) が出たので、上の見取り図と並べて読んだ。どちらも入れずに、ソースだけを読んだ。

claude-security は、その場で回す LLM の静的スキャナ。コンポーネントごとに脅威モデルを作り、4 つの観点 (注入、認証認可、メモリ、暗号と秘密情報) で候補を探す。候補ごとに 3 体の検証役が反証を試み、2 票以上残ったものだけを報告する。パッチの提案も持つ。

- security-audit (本 Issue の試用対象) と役割がほぼ重なる。残すのはどちらか 1 つにする
- 隔離は security-audit の方が強い。security-audit は対象のコードを動かすなら OS のサンドボックスを必須にする。claude-security の「実行しない」はプロンプトの指示で、パッチの検証では対象のテストをサンドボックス無しで動かす
- コストの上限は、claude-security が 1 回の実行あたり agent 1000 回を固定で持ち、security-audit は予算を渡したときだけ持つ。claude-security は low でも、研究役 1 本に加えて候補 1 件ごとに検証役が 3 本走り、high では数百本の規模になる
- red-team の Layer 1 / 4 と blue-team Mode B の静的な部分は、一部しか置き換えられない。claude-security は攻撃経路が成立するものだけを報告し、ヘッダや Cookie 属性の欠落のような防御の穴は設計上捨てる。依存の監査、RLS の verify_command の実行、CI の設定や .env の衛生も見ない
- 動的テスト、Mode A の改善計画、ログのカバレッジ、本番ゲートと security-cleanup に当たるものは無い
- 入れるときの条件は次のとおり
  - push と PR 作成のあとにスキャンを勧める表示が全リポジトリで出る。`CLAUDE_SECURITY_SCAN_TIP=off` で止める
  - 利用回数のテレメトリが Claude Code 経由で送られる。止めるなら `DISABLE_TELEMETRY` などを設定する
  - skill と agent の説明文が、毎セッションと subagent の起動ごとに約 2.3KB 載る。config-guard の予算は CLAUDE.md と rules しか数えないので、この増加は検査に出ない
  - 報告はリポジトリ直下の `CLAUDE-SECURITY-<時刻>/` に書かれる (中に専用の `.gitignore` を持つ)
- AskUserQuestion に掛かるフックは、自分のスキャン開始確認の文言のときだけ働き、ほかの質問には何もしない

security-guidance は入れない。自作のどれも置き換えないうえに、プロンプト・編集・コミット・Stop のたびにフックが走り、Stop とコミットでは追加のモデル呼び出しが発生する。加えて SessionStart で `claude-agent-sdk` が import できなければ、PyPI からバージョンの pin なしで専用の venv へインストールする (venv が作れない環境では `--upgrade` 付きの `--target` 導入へ落ちる)。

使用実績 (2026-07-18 から 2026-10-16 の transcript 939 本。subagent の transcript は含まない)。security-blue-red-team の command と agent を呼んだ transcript は 0 本で、security-profile.yml を持つ手元のリポジトリは 1 つだった。数え方の対照として、よく使う skill と agent を同じ方法で数え、非 0 になることを確かめてある。security-audit も 0 本だが、導入から 9 日しか経っていない。

この結果から、自作を整理するかどうかは公式 plugin より「staging への動的テストを続けるか」で決まる。`/security-vulnerability-assessment` は `/security-redteam --layer=1,2` の薄いラッパーで、公式 plugin と関係なく消せる。2026-10-16 の Hidari の判断で、自作にはいまは触らない。

## full audit の試用記録 (2026-10-20、他リポジトリのセッションからの報告)

非公開の実リポジトリで、user スコープの security-audit (pin どおりのコミット) を full audit・profile standard で最後まで回した報告を、feedbacks-box 経由で受けた。監査で見つかった弱点の中身は受け取っていない。括弧内は報告者がどこまで確かめたか。予算と出力先を指定したかは報告に無い。

### 規模と結果

- agent は45本 (偵察4、探索26、網羅の批評7、候補の検証4、記録の検証4)。subagent のトークンは合計でおよそ560万 (実測)
- 探索は6波。批評役が波ごとに1〜6単位の漏れを見つけ続け、2回続けて追加なしで収束した。重い候補の1つは第4波で初めて出た。前の探索役が守る資源を取り違えて閉じた単位を、批評役が疑い直して見つけたもの (実測)
- 対象のコードを動かす砂箱を用意できず、確定は0件で、候補はすべて要検証で止まった (実測)。砂箱は ISSUE-127 へ切り出した

### 堅牢さ

- 台帳 (coverage-ledger.json) と findings.json の検証スクリプトが、探索役の記録の欠落を3回捕まえた (実測)
- 確定を手元で再現したものに限る、見つけた人と確かめる人を分ける、の2点で誤検知が出にくい (報告者の評価)
- 前回の台帳を読んで積み上げる前提の作り。1回で見つかるのは繰り返した分の約半分という数字は上流の作者の実測で、報告者は確かめていない

### Claude Code で回すときの摩擦 (報告者が実際に踏んだもの)

- skill は parent が Task tool で子を呼ぶ形で書かれている。メインのエージェントが parent を務め、段階ごとに Workflow を回し、段階のあいだに台帳を書いて検証スクリプトを通した。そのために parent 側の補助スクリプトを4本書いた (台帳の生成、指示の組み立て、波の照合、検証の段階と報告書の生成)
- 攻撃分類のブロックを原文のまま指示へ入れる要求で、探索役1人あたり約45KB になり、12人分の Workflow の script が上限の512KB を超えた。script を分けて回した。指示は Python で生成し scriptPath で渡した
- 探索役の出力の形は skill の中で散文でしか指定されておらず、18単位のうち6単位で確認の記録のフィールドが落ちた。structured output の schema でフィールドと値を強制したら止まった
- run-metadata.json は対象の絶対パスを持つので、残すならホームディレクトリのユーザー名を落とす
- commit-and-pr-message の検査は約286KB の台帳を input-too-large で止める。skill が書く手順どおり分けて全断片を通し、断片が元のファイルを覆うことを cmp で確かめた (手順が実際に機能した例)

### 報告者の提案と、この Issue の見取り図との関係

- 補助スクリプトを、Claude Code で security-audit を回す薄い runner として agentic-coding-tools に置く。上流の skill 本体は触らず外側に置く。報告者の実装は対象固有の単位定義を含むので、写すなら単位定義を引数に出す必要がある
- security-blue-red-team は、red-team の Layer 2 / 3 (local と staging への動的な検証) と blue-team の Mode A (優先付け) に絞り、静的な層は security-audit に任せる。上の「重複の見取り図」と同じ結論で、それを実地で裏付ける1例にあたる
- 監査の記録をリポジトリに置く雛形。報告元では、まとめ役が書いた共有ファイルだけを日付ごとのディレクトリへ置き、作業場の scratch は残さず、README に「Private のあいだだけ置く。公開する前に修正するか外す」と書いた。上の見取り図にある上流の規則 (出力は対象の外か ignore 済みのディレクトリだけ) と食い違うので、寄せるならどちらに合わせるかを決める

## タスク

- [ ] 実際のリポジトリで guidance mode を数回使い、指摘の質と誤検知を記録する
- [ ] full audit を予算付き・出力先 `.cache/` 指定で1回回し、所要と指摘を記録する
- [ ] 同じリポジトリで claude-security を low か範囲を絞って 1 回回し、security-audit と指摘の質・誤検知・所要を比べる。試用は `/plugin install` を local スコープで行い、追跡下の settings.json を変えない。`CLAUDE_SECURITY_SCAN_TIP=off` とテレメトリの扱いを先に決める
- [ ] security-audit と claude-security のどちらを残すか決める (Hidari の判断)
- [ ] 採否を決める (Hidari の判断)
- [ ] 採るなら、寄せる範囲と findings.json の扱いを決めて agentic-coding-tools へ委譲する
- [ ] 採るなら、Claude Code で回す薄い runner (「full audit の試用記録」節の提案) を一緒に委譲するかを決める
- [ ] 採るなら、監査の記録をリポジトリ内に置くか、上流の出力先の規則に合わせるかを決める
- [ ] 寄せたあとの pin を dotfiles の `home/apm.yml` で更新する

## 関連

- ISSUE-40: security-blue-red-team の command と agent が二重に登録されている件。寄せるときに一緒に片付く可能性がある
- ISSUE-90: apm の依存が持ち込む常時ロード層の検知。plugin の説明文も同じく config-guard の予算の外で載る
- ISSUE-127: 監査用の砂箱イメージ。試用記録で確定まで進めなかった原因
- ISSUE-128: 同じ試用で、user スコープに入っている skill を project スコープへ重ねて apm install した件
